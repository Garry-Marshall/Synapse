"""
LMStudio API interaction service.
Handles model fetching and query streaming.
"""
import aiohttp
import json
import logging
from typing import AsyncGenerator, List, Dict, Optional

from config import LMSTUDIO_URL, MAX_HISTORY

logger = logging.getLogger(__name__)


async def fetch_available_models() -> List[str]:
    """
    Fetch available (loaded) models from LM Studio.
    
    Returns:
        List of loaded model identifiers
    """
    try:
        base_url = (
            LMSTUDIO_URL.split('/v1/')[0]
            if '/v1/' in LMSTUDIO_URL
            else LMSTUDIO_URL.rsplit('/', 1)[0]
        )

        models_url = f"{base_url}/api/v1/models"
        logger.info(f"Fetching models from: {models_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(models_url) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to fetch models: {response.status} - {await response.text()}"
                    )
                    return []

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

    except Exception:
        logger.error("Error fetching models from LM Studio", exc_info=True)
        return []


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
    if len(api_messages) > MAX_HISTORY * 2:
        api_messages = [api_messages[0]] + api_messages[-(MAX_HISTORY * 2 - 1):]
    
    return api_messages


async def stream_completion(
    messages: List[Dict],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = -1
) -> AsyncGenerator[str, None]:
    """
    Stream a completion from LMStudio API.
    
    Args:
        messages: List of message dictionaries
        model: Model identifier to use
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate (-1 for unlimited)
        
    Yields:
        Content chunks as they arrive
    """
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
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(LMSTUDIO_URL, json=payload) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                content = data['choices'][0].get('delta', {}).get('content', '')
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                else:
                    error_text = await response.text()
                    logger.error(f"LMStudio Error {response.status}: {error_text}")
                    yield f"Error: LMStudio API returned status {response.status}"
                    
    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        yield "Error: Connection to LMStudio failed."