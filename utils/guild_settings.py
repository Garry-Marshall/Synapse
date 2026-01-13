"""
Guild-specific settings management.
Handles per-server configuration like system prompts, temperature, etc.
"""
import json
import logging
import os
from typing import Dict, Optional

from config import GUILD_SETTINGS_FILE, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)

# Store guild settings
guild_settings: Dict[int, Dict] = {}


def load_guild_settings() -> None:
    """Load guild settings from file."""
    global guild_settings
    
    if os.path.exists(GUILD_SETTINGS_FILE):
        try:
            with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                guild_settings = {int(k): v for k, v in raw.items()}
            logger.info(f"Loaded settings for {len(guild_settings)} guild(s)")
        except Exception as e:
            logger.error(f"Failed to load guild settings: {e}")
            guild_settings = {}
    else:
        logger.info("Guild settings file not found. Will create on first save.")
        guild_settings = {}


def save_guild_settings() -> None:
    """Save guild settings to file."""
    try:
        with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in guild_settings.items()},
                f,
                indent=2,
                ensure_ascii=False
            )
    except Exception as e:
        logger.error(f"Failed to save guild settings: {e}")


def get_guild_setting(guild_id: Optional[int], key: str, default=None):
    """
    Get a specific setting for a guild.
    
    Args:
        guild_id: Guild ID (None for DMs)
        key: Setting key
        default: Default value if not set
        
    Returns:
        Setting value or default
    """
    if guild_id and guild_id in guild_settings:
        return guild_settings[guild_id].get(key, default)
    return default


def set_guild_setting(guild_id: int, key: str, value) -> None:
    """
    Set a specific setting for a guild.
    
    Args:
        guild_id: Guild ID
        key: Setting key
        value: Setting value
    """
    guild_settings.setdefault(guild_id, {})[key] = value
    save_guild_settings()
    logger.info(f"Updated guild {guild_id} setting: {key} = {value}")


def delete_guild_setting(guild_id: int, key: str) -> None:
    """
    Delete a specific setting for a guild.
    
    Args:
        guild_id: Guild ID
        key: Setting key
    """
    if guild_id in guild_settings:
        guild_settings[guild_id].pop(key, None)
        save_guild_settings()
        logger.info(f"Deleted guild {guild_id} setting: {key}")


def get_guild_system_prompt(guild_id: Optional[int]) -> Optional[str]:
    """Get custom system prompt for a guild."""
    return get_guild_setting(guild_id, "system_prompt")


def get_guild_temperature(guild_id: Optional[int]) -> float:
    """Get temperature setting for a guild."""
    temp = get_guild_setting(guild_id, "temperature", DEFAULT_TEMPERATURE)
    return float(temp)


def get_guild_max_tokens(guild_id: Optional[int]) -> int:
    """Get max_tokens setting for a guild."""
    tokens = get_guild_setting(guild_id, "max_tokens", DEFAULT_MAX_TOKENS)
    return int(tokens)


def is_search_enabled(guild_id: Optional[int]) -> bool:
    """Check if web search is enabled for a guild."""
    return get_guild_setting(guild_id, "search_enabled", True)


def is_debug_enabled(guild_id: Optional[int]) -> bool:
    """Check if debug logging is enabled for a guild."""
    return get_guild_setting(guild_id, "debug", True)


def get_debug_level(guild_id: Optional[int]) -> str:
    """Get debug level for a guild (info or debug)."""
    return get_guild_setting(guild_id, "debug_level", "debug")


def get_all_guild_settings(guild_id: int) -> dict:
    """
    Get all settings for a guild.
    
    Args:
        guild_id: Guild ID
        
    Returns:
        Dictionary of all settings
    """
    return guild_settings.get(guild_id, {}).copy()


def clear_guild_settings(guild_id: int) -> None:
    """
    Clear all settings for a guild.
    
    Args:
        guild_id: Guild ID
    """
    if guild_id in guild_settings:
        del guild_settings[guild_id]
        save_guild_settings()
        logger.info(f"Cleared all settings for guild {guild_id}")


# Initialize guild settings on module import
load_guild_settings()