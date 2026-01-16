"""
LMStudio API interaction service.
Handles model fetching and query streaming.
"""
import aiohttp
import asyncio
import json
import logging
from typing import AsyncGenerator, List, Dict, Optional

from config.settings import LMSTUDIO_URL, MAX_HISTORY
from utils.logging_config import guild_debug_log
from config.constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, MIN_TEMPERATURE, MAX_TEMPERATURE, HISTORY_MULTIPLIER, LMSTUDIO_INITIAL_RETRY_DELAY, LMSTUDIO_MAX_RETRY_DELAY, LMSTUDIO_RETRY_BACKOFF_MULTIPLIER, LMSTUDIO_MAX_RETRIES


logger = logging.getLogger(__name__)


async def fetch_available_models() -> List[str]:
    """
    Fetch available (loaded) models from LM Studio with retry logic.

    Returns:
        List of loaded model identifiers
    """
    base_url = (
        LMSTUDIO_URL.split('/v1/')[0]
        if '/v1/' in LMSTUDIO_URL
        else LMSTUDIO_URL.rsplit('/', 1)[0]
    )
    models_url = f"{base_url}/api/v1/models"

    retry_delay = LMSTUDIO_INITIAL_RETRY_DELAY

    for attempt in range(LMSTUDIO_MAX_RETRIES):
        try:
            logger.info(f"Fetching models from: {models_url} (attempt {attempt + 1}/{LMSTUDIO_MAX_RETRIES})")

            async with aiohttp.ClientSession() as session:
                async with session.get(models_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch models: {response.status} - {error_text}")

                        # Don't retry on client errors (4xx)
                        if 400 <= response.status < 500:
                            return []

                        # Retry on server errors (5xx)
                        raise aiohttp.ClientError(f"Server error: {response.status}")

                    data = await response.json()
                    all_models = data.get("models", [])

                    # Only return models that are actually loaded
                    models = [
                        model["key"]
                        for model in all_models
                        if model.get("loaded_instances")
                    ]

                    if models:
                        logger.info(f"Loaded LM Studio model(s): {models}")
                    else:
                        logger.warning("No loaded models found in LM Studio")

                    return models

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < LMSTUDIO_MAX_RETRIES - 1:
                logger.warning(
                    f"Failed to fetch models (attempt {attempt + 1}/{LMSTUDIO_MAX_RETRIES}): {e}. "
                    f"Retrying in {retry_delay:.1f}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * LMSTUDIO_RETRY_BACKOFF_MULTIPLIER, LMSTUDIO_MAX_RETRY_DELAY)
            else:
                logger.error(f"Failed to fetch models after {LMSTUDIO_MAX_RETRIES} attempts", exc_info=True)
                return []
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {e}", exc_info=True)
            return []

    return []


def validate_parameters(temperature: float, max_tokens: int) -> tuple[float, int]:
    """
    Validate and clamp temperature and max_tokens to safe ranges.
    
    Args:
        temperature: Temperature parameter
        max_tokens: Max tokens parameter
        
    Returns:
        Tuple of (validated_temperature, validated_max_tokens)
    """
    # Validate temperature
    if not isinstance(temperature, (int, float)):
        logger.warning(f"Invalid temperature type: {type(temperature)}, using default")
        temperature = DEFAULT_TEMPERATURE
    elif not (MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE):
        logger.warning(f"Temperature {temperature} out of range [0.0, 2.0], clamping")
        temperature = max(MIN_TEMPERATURE, min(MAX_TEMPERATURE, temperature))
    
    # Validate max_tokens
    if not isinstance(max_tokens, int):
        logger.warning(f"Invalid max_tokens type: {type(max_tokens)}, using default")
        max_tokens = DEFAULT_MAX_TOKENS
    elif max_tokens != -1 and max_tokens <= 0:
        logger.warning(f"Invalid max_tokens {max_tokens}, using default")
        max_tokens = DEFAULT_MAX_TOKENS
    
    return temperature, max_tokens


def build_api_messages(
    conversation_history: List[Dict],
    system_prompt: str
) -> List[Dict]:
    """
    Build the message list for the API, including system prompt and deduplication.
    
    Args:
        conversation_history: List of conversation messages
        system_prompt: System prompt to prepend
        
    Returns:
        List of messages ready for API
    """
    api_messages = []
    
    # Add system prompt
    api_messages.append({"role": "system", "content": system_prompt})
    
    # Add conversation history with deduplication
    for msg in conversation_history:
        # Merge consecutive messages from the same role
        if api_messages and api_messages[-1]["role"] == msg["role"]:
            if isinstance(api_messages[-1]["content"], str) and isinstance(msg["content"], str):
                api_messages[-1]["content"] += f"\n\n{msg['content']}"
            else:
                api_messages.append(msg.copy())
        else:
            api_messages.append(msg.copy())
    
    # Limit history to prevent context overflow
    if len(api_messages) > MAX_HISTORY * HISTORY_MULTIPLIER:
        api_messages = [api_messages[0]] + api_messages[-(MAX_HISTORY * HISTORY_MULTIPLIER - 1):]
    
    return api_messages


async def stream_completion(
    messages: List[Dict],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = -1,
    guild_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Stream a completion from LMStudio API with retry logic.

    Args:
        messages: List of message dictionaries
        model: Model identifier to use
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate (-1 for unlimited)
        guild_id: Guild ID for debug logging (optional)

    Yields:
        Content chunks as they arrive
    """
    # Validate parameters
    temperature, max_tokens = validate_parameters(temperature, max_tokens)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True
    }

    logger.info(
        "LMStudio request | model=%s | messages=%d | temp=%.2f | max_tokens=%s",
        model,
        len(messages),
        temperature,
        max_tokens
    )

    guild_debug_log(guild_id, "debug", f"LMStudio API payload: {len(messages)} messages, model={model}")

    retry_delay = LMSTUDIO_INITIAL_RETRY_DELAY
    last_error = None

    for attempt in range(LMSTUDIO_MAX_RETRIES):
        try:
            timeout = aiohttp.ClientTimeout(total=300, sock_read=60)  # 5 min total, 60s read timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(LMSTUDIO_URL, json=payload) as response:
                    if response.status == 200:
                        # Read the response stream line-by-line to avoid splitting
                        # SSE frames across arbitrary chunk boundaries. Use the
                        # StreamReader.readline() coroutine which yields complete
                        # lines terminated by a newline.
                        while True:
                            line_bytes = await response.content.readline()
                            if not line_bytes:
                                break

                            # Decode with error handling
                            try:
                                line = line_bytes.decode('utf-8').strip()
                            except UnicodeDecodeError as e:
                                logger.warning(f"Received invalid UTF-8 in SSE stream: {e}")
                                continue

                            if not line:
                                continue

                            if line.startswith('data: '):
                                data_str = line[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    # Check if choices array exists and has elements
                                    if 'choices' in data and len(data['choices']) > 0:
                                        content = data['choices'][0].get('delta', {}).get('content', '')
                                        if content:
                                            yield content
                                    else:
                                        logger.warning('SSE data missing choices array')
                                except json.JSONDecodeError as e:
                                    logger.debug(f'Received non-JSON SSE data: {e}')
                                    continue
                                except (KeyError, IndexError) as e:
                                    logger.warning(f'Unexpected SSE data structure: {e}')
                                    continue

                        # Successfully completed streaming
                        return

                    elif response.status >= 500:
                        # Server error - retry
                        error_text = await response.text()
                        last_error = f"LMStudio server error {response.status}: {error_text}"
                        logger.warning(last_error)

                        if attempt < LMSTUDIO_MAX_RETRIES - 1:
                            logger.info(f"Retrying in {retry_delay:.1f}s... (attempt {attempt + 1}/{LMSTUDIO_MAX_RETRIES})")
                            await asyncio.sleep(retry_delay)
                            retry_delay = min(retry_delay * LMSTUDIO_RETRY_BACKOFF_MULTIPLIER, LMSTUDIO_MAX_RETRY_DELAY)
                            continue
                        else:
                            logger.error(f"Failed after {LMSTUDIO_MAX_RETRIES} attempts")
                            yield f"Error: LMStudio API error after {LMSTUDIO_MAX_RETRIES} retries. {last_error}"
                            return

                    else:
                        # Client error (4xx) - don't retry
                        error_text = await response.text()
                        logger.error(f"LMStudio Error {response.status}: {error_text}")
                        yield f"Error: LMStudio API returned status {response.status}"
                        return

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = str(e)

            if attempt < LMSTUDIO_MAX_RETRIES - 1:
                logger.warning(
                    f"Connection error to LMStudio (attempt {attempt + 1}/{LMSTUDIO_MAX_RETRIES}): {e}. "
                    f"Retrying in {retry_delay:.1f}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * LMSTUDIO_RETRY_BACKOFF_MULTIPLIER, LMSTUDIO_MAX_RETRY_DELAY)
            else:
                logger.error(f"Failed to connect to LMStudio after {LMSTUDIO_MAX_RETRIES} attempts", exc_info=True)
                yield f"Error: Could not connect to LMStudio after {LMSTUDIO_MAX_RETRIES} retries. Please ensure it's running."
                return

        except Exception as e:
            logger.error(f"Unexpected error in stream_completion: {e}", exc_info=True)
            yield "Error: An unexpected error occurred while processing your request."
            return