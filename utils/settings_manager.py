"""
Settings Manager - Centralized guild settings management.
Provides a clean interface for managing per-guild configuration with validation.

UPDATED: Now uses SQLite database instead of JSON files for better concurrency and reliability.
"""
import logging
from typing import Any, Dict, Optional

from config.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    MIN_TEMPERATURE,
    MAX_TEMPERATURE,
    MAX_SYSTEM_PROMPT_LENGTH,
)
from config.settings import ENABLE_TTS, ALLTALK_VOICE, ENABLE_COMFYUI

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    Centralized manager for guild-specific settings.
    
    Provides:
    - Automatic validation of setting values
    - Thread-safe operations (via SQLite)
    - Persistent storage
    - Type checking
    - Default value handling
    """
    
    # Define valid settings with their types and validators
    SETTING_SCHEMA = {
        "system_prompt": {
            "type": str,
            "default": None,
            "validator": lambda v: len(v) <= MAX_SYSTEM_PROMPT_LENGTH if v else True
        },
        "temperature": {
            "type": float,
            "default": DEFAULT_TEMPERATURE,
            "validator": lambda v: MIN_TEMPERATURE <= v <= MAX_TEMPERATURE
        },
        "max_tokens": {
            "type": int,
            "default": DEFAULT_MAX_TOKENS,
            "validator": lambda v: v == -1 or v > 0
        },
        "debug": {
            "type": bool,
            "default": True,
            "validator": None
        },
        "debug_level": {
            "type": str,
            "default": "debug",
            "validator": lambda v: v in {"info", "debug"}
        },
        "search_enabled": {
            "type": bool,
            "default": True,
            "validator": None
        },
        "tts_enabled": {
            "type": bool,
            "default": True,
            "validator": None
        },
        "selected_voice": {
            "type": str,
            "default": ALLTALK_VOICE,
            "validator": lambda v: v in ["alloy", "echo", "fable", "nova", "onyx", "shimmer"]
        },
        "comfyui_enabled": {
            "type": bool,
            "default": True,
            "validator": None
        },
        "monitored_channels": {
            "type": list,
            "default": [],
            "validator": lambda v: isinstance(v, list) and all(isinstance(x, int) for x in v)
        }
    }
    
    def __init__(self):
        """Initialize the settings manager with database backend."""
        from utils.database import get_database
        self._db = get_database()
        logger.info("SettingsManager initialized with SQLite backend")
    
    def _validate_setting(self, key: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a setting value.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if key not in self.SETTING_SCHEMA:
            return False, f"Unknown setting: {key}"
        
        schema = self.SETTING_SCHEMA[key]
        
        # Check type
        if value is not None and not isinstance(value, schema["type"]):
            return False, f"Invalid type for {key}: expected {schema['type'].__name__}, got {type(value).__name__}"
        
        # Run custom validator if exists
        if schema["validator"] is not None and value is not None:
            try:
                if not schema["validator"](value):
                    return False, f"Validation failed for {key}: value {value} not allowed"
            except Exception as e:
                return False, f"Validation error for {key}: {e}"
        
        return True, None
    
    def get(self, guild_id: Optional[int], key: str, default: Any = None) -> Any:
        """
        Get a setting value for a guild.
        
        Args:
            guild_id: Guild ID (None for global/DM)
            key: Setting key
            default: Default value if not set
            
        Returns:
            Setting value or default
        """
        # Use schema default if no explicit default provided
        if default is None and key in self.SETTING_SCHEMA:
            default = self.SETTING_SCHEMA[key]["default"]
        
        if guild_id is None:
            return default
        
        return self._db.get_setting(guild_id, key, default)
    
    def set(self, guild_id: int, key: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Set a setting value for a guild with validation.
        
        Args:
            guild_id: Guild ID
            key: Setting key
            value: Setting value
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate
        valid, error = self._validate_setting(key, value)
        if not valid:
            logger.warning(f"Invalid setting for guild {guild_id}: {error}")
            return False, error
        
        # Set in database
        try:
            self._db.set_setting(guild_id, key, value)
            logger.info(f"Updated guild {guild_id} setting: {key} = {value}")
            return True, None
        except Exception as e:
            logger.error(f"Failed to set setting {key} for guild {guild_id}: {e}", exc_info=True)
            return False, str(e)
    
    def delete(self, guild_id: int, key: str) -> None:
        """
        Delete a setting for a guild.
        
        Args:
            guild_id: Guild ID
            key: Setting key
        """
        self._db.delete_setting(guild_id, key)
        logger.info(f"Deleted guild {guild_id} setting: {key}")
    
    def get_all(self, guild_id: int) -> Dict[str, Any]:
        """
        Get all settings for a guild.
        
        Args:
            guild_id: Guild ID
            
        Returns:
            Dictionary of all settings
        """
        return self._db.get_all_settings(guild_id)
    
    def clear(self, guild_id: int) -> None:
        """
        Clear all settings for a guild.
        
        Args:
            guild_id: Guild ID
        """
        self._db.clear_all_settings(guild_id)
        logger.info(f"Cleared all settings for guild {guild_id}")
    
    # Convenience methods for common settings
    
    def get_temperature(self, guild_id: Optional[int]) -> float:
        """Get temperature setting."""
        return float(self.get(guild_id, "temperature", DEFAULT_TEMPERATURE))
    
    def get_max_tokens(self, guild_id: Optional[int]) -> int:
        """Get max_tokens setting."""
        return int(self.get(guild_id, "max_tokens", DEFAULT_MAX_TOKENS))
    
    def get_system_prompt(self, guild_id: Optional[int]) -> Optional[str]:
        """Get system prompt setting."""
        return self.get(guild_id, "system_prompt")
    
    def is_debug_enabled(self, guild_id: Optional[int]) -> bool:
        """Check if debug logging is enabled."""
        return bool(self.get(guild_id, "debug", True))
    
    def get_debug_level(self, guild_id: Optional[int]) -> str:
        """Get debug level."""
        return str(self.get(guild_id, "debug_level", "debug"))
    
    def is_search_enabled(self, guild_id: Optional[int]) -> bool:
        """Check if web search is enabled."""
        return bool(self.get(guild_id, "search_enabled", True))
    
    def is_tts_enabled(self, guild_id: Optional[int]) -> bool:
        """Check if TTS is enabled."""
        if not ENABLE_TTS:
            return False
        if guild_id is None:
            return False
        return bool(self.get(guild_id, "tts_enabled", True))

    def get_voice(self, guild_id: Optional[int]) -> str:
        """Get selected TTS voice."""
        return str(self.get(guild_id, "selected_voice", ALLTALK_VOICE))

    def is_comfyui_enabled(self, guild_id: Optional[int]) -> bool:
        """Check if ComfyUI image generation is enabled."""
        if not ENABLE_COMFYUI:
            return False
        if guild_id is None:
            return False
        return bool(self.get(guild_id, "comfyui_enabled", True))


# Global instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """
    Get the global settings manager instance.
    
    Returns:
        SettingsManager instance
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


# Backward compatibility functions for existing code
def load_guild_settings() -> None:
    """Load guild settings (compatibility function - now no-op)."""
    get_settings_manager()


def save_guild_settings() -> None:
    """Save guild settings (compatibility function - now no-op, auto-saved to DB)."""
    pass  # Database auto-commits


def get_guild_setting(guild_id: Optional[int], key: str, default=None):
    """Get a guild setting (compatibility function)."""
    return get_settings_manager().get(guild_id, key, default)


def set_guild_setting(guild_id: int, key: str, value) -> None:
    """Set a guild setting (compatibility function)."""
    success, error = get_settings_manager().set(guild_id, key, value)
    if not success:
        logger.error(f"Failed to set {key} for guild {guild_id}: {error}")


def delete_guild_setting(guild_id: int, key: str) -> None:
    """Delete a guild setting (compatibility function)."""
    get_settings_manager().delete(guild_id, key)


def get_guild_temperature(guild_id: Optional[int]) -> float:
    """Get temperature setting (compatibility function)."""
    return get_settings_manager().get_temperature(guild_id)


def get_guild_max_tokens(guild_id: Optional[int]) -> int:
    """Get max_tokens setting (compatibility function)."""
    return get_settings_manager().get_max_tokens(guild_id)


def get_guild_system_prompt(guild_id: Optional[int]) -> Optional[str]:
    """Get system prompt (compatibility function)."""
    return get_settings_manager().get_system_prompt(guild_id)


def is_debug_enabled(guild_id: Optional[int]) -> bool:
    """Check if debug is enabled (compatibility function)."""
    return get_settings_manager().is_debug_enabled(guild_id)


def get_debug_level(guild_id: Optional[int]) -> str:
    """Get debug level (compatibility function)."""
    return get_settings_manager().get_debug_level(guild_id)


def is_search_enabled(guild_id: Optional[int]) -> bool:
    """Check if search is enabled (compatibility function)."""
    return get_settings_manager().is_search_enabled(guild_id)


def is_tts_enabled_for_guild(guild_id: int) -> bool:
    """Check if TTS is enabled (compatibility function)."""
    return get_settings_manager().is_tts_enabled(guild_id)


def get_guild_voice(guild_id: Optional[int]) -> str:
    """Get TTS voice (compatibility function)."""
    return get_settings_manager().get_voice(guild_id)


def is_comfyui_enabled_for_guild(guild_id: int) -> bool:
    """Check if ComfyUI is enabled (compatibility function)."""
    return get_settings_manager().is_comfyui_enabled(guild_id)


def get_all_guild_settings(guild_id: int) -> dict:
    """Get all settings (compatibility function)."""
    return get_settings_manager().get_all(guild_id)


def clear_guild_settings(guild_id: int) -> None:
    """Clear all settings (compatibility function)."""
    get_settings_manager().clear(guild_id)


# For backward compatibility, keep the old dict reference (empty)
guild_settings = {}

# ============================================================================
# MONITORED CHANNELS MANAGEMENT
# ============================================================================

def get_monitored_channels(guild_id: int) -> set[int]:
    """
    Get the set of monitored channel IDs for a guild.
    
    Args:
        guild_id: Guild ID
        
    Returns:
        Set of channel IDs where the bot should listen
    """
    channels = get_settings_manager().get(guild_id, "monitored_channels", [])
    return set(channels) if channels else set()


def add_monitored_channel(guild_id: int, channel_id: int) -> bool:
    """
    Add a channel to the monitored channels list for a guild.
    
    Args:
        guild_id: Guild ID
        channel_id: Channel ID to add
        
    Returns:
        True if channel was added, False if already exists
    """
    channels = get_monitored_channels(guild_id)
    
    if channel_id in channels:
        return False
    
    channels.add(channel_id)
    set_guild_setting(guild_id, "monitored_channels", list(channels))
    logger.info(f"Added channel {channel_id} to monitored list for guild {guild_id}")
    return True


def remove_monitored_channel(guild_id: int, channel_id: int) -> bool:
    """
    Remove a channel from the monitored channels list for a guild.
    
    Args:
        guild_id: Guild ID
        channel_id: Channel ID to remove
        
    Returns:
        True if channel was removed, False if not in list
    """
    channels = get_monitored_channels(guild_id)
    
    if channel_id not in channels:
        return False
    
    channels.remove(channel_id)
    set_guild_setting(guild_id, "monitored_channels", list(channels))
    logger.info(f"Removed channel {channel_id} from monitored list for guild {guild_id}")
    return True


def is_channel_monitored(guild_id: int, channel_id: int) -> bool:
    """
    Check if a channel is being monitored in a guild.
    
    Args:
        guild_id: Guild ID
        channel_id: Channel ID to check
        
    Returns:
        True if channel is monitored
    """
    channels = get_monitored_channels(guild_id)
    return channel_id in channels