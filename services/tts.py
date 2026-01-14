"""
Text-to-speech service using AllTalk TTS.
Converts text to audio using OpenAI-compatible API.
"""
import aiohttp
import asyncio
import logging
from typing import Optional

from config.settings import ALLTALK_URL, ALLTALK_VOICE
from config.constants import AVAILABLE_VOICES
from utils.text_utils import remove_thinking_tags

logger = logging.getLogger(__name__)


async def text_to_speech(text: str, voice: str = None) -> Optional[bytes]:
    """
    Convert text to speech using AllTalk TTS (OpenAI compatible endpoint).
    
    Args:
        text: Text to convert to speech
        voice: Voice name to use (defaults to ALLTALK_VOICE)
        
    Returns:
        Audio data as bytes, or None if failed
    """
    # Validate and set voice
    if not voice or voice not in AVAILABLE_VOICES:
        voice = ALLTALK_VOICE
    
    try:
        # Remove any remaining thinking tags or markers from the text
        clean_text = remove_thinking_tags(text)
        
        if not clean_text.strip():
            logger.warning("No text to speak after filtering")
            return None
        
        # Use OpenAI-compatible endpoint
        payload = {
            "model": "tts-1",
            "input": clean_text,
            "voice": voice
        }
        
        logger.info(f"Generating TTS with voice '{voice}': {clean_text[:100]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ALLTALK_URL}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    logger.info(f"Generated {len(audio_data)} bytes of audio")
                    return audio_data
                else:
                    error_text = await response.text()
                    logger.error(f"AllTalk TTS error: {response.status} - {error_text}")
                    return None
                    
    except asyncio.TimeoutError:
        logger.error("AllTalk TTS request timed out")
        return None
    except Exception as e:
        logger.error(f"Error generating TTS: {e}", exc_info=True)
        return None


def get_voice_description(voice: str) -> str:
    """
    Get a human-readable description of a voice.
    
    Args:
        voice: Voice name
        
    Returns:
        Description string
    """
    from config.constants import VOICE_DESCRIPTIONS
    return VOICE_DESCRIPTIONS.get(voice, "Unknown voice")


def is_valid_voice(voice: str) -> bool:
    """
    Check if a voice name is valid.
    
    Args:
        voice: Voice name to check
        
    Returns:
        True if valid
    """
    return voice in AVAILABLE_VOICES