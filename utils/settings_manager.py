"""
Settings Manager - Centralized guild settings management.
Provides a clean interface for managing per-guild configuration with validation and caching.
"""
import json
import logging
import os
from typing import Any, Dict, Optional
from threading import Lock

from config.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    MIN_TEMPERATURE,
    MAX_TEMPERATURE,
    MAX_SYSTEM_PROMPT_LENGTH,
)
from config.settings import GUILD_SETTINGS_FILE, ENABLE_TTS, ALLTALK_VOICE

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    Centralized manager for guild-specific settings.
    
    Provides:
    - Automatic validation of setting values
    - Thread-safe operations
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
        }
    }
    
    def __init__(self):
        """Initialize the settings manager."""
        self._settings: Dict[int, Dict[str, Any]] = {}
        self._lock = Lock()
        self._load()
    
    def _load(self) -> None:
        """Load settings from persistent storage."""
        if os.path.exists(GUILD_SETTINGS_FILE):
            try:
                with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._settings = {int(k): v for k, v in raw.items()}
                logger.info(f"Loaded settings for {len(self._settings)} guild(s)")
            except Exception as e:
                logger.error(f"Failed to load guild settings: {e}")
                self._settings = {}
        else:
            logger.info("Guild settings file not found. Will create on first save.")
            self._settings = {}
    
    def _save(self) -> None:
        """Save settings to persistent storage."""
        try:
            with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {str(k): v for k, v in self._settings.items()},
                    f,
                    indent=2,
                    ensure_ascii=False
                )
        except Exception as e:
            logger.error(f"Failed to save guild settings: {e}")
    
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
        
        with self._lock:
            if guild_id in self._settings:
                return self._settings[guild_id].get(key, default)
            return default
    
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
        
        # Set
        with self._lock:
            if guild_id not in self._settings:
                self._settings[guild_id] = {}
            
            self._settings[guild_id][key] = value
            self._save()
        
        logger.info(f"Updated guild {guild_id} setting: {key} = {value}")
        return True, None
    
    def delete(self, guild_id: int, key: str) -> None:
        """
        Delete a setting for a guild.
        
        Args:
            guild_id: Guild ID
            key: Setting key
        """
        with self._lock:
            if guild_id in self._settings:
                self._settings[guild_id].pop(key, None)
                self._save()
        
        logger.info(f"Deleted guild {guild_id} setting: {key}")
    
    def get_all(self, guild_id: int) -> Dict[str, Any]:
        """
        Get all settings for a guild.
        
        Args:
            guild_id: Guild ID
            
        Returns:
            Dictionary of all settings
        """
        with self._lock:
            return self._settings.get(guild_id, {}).copy()
    
    def clear(self, guild_id: int) -> None:
        """
        Clear all settings for a guild.
        
        Args:
            guild_id: Guild ID
        """
        with self._lock:
            if guild_id in self._settings:
                del self._settings[guild_id]
                self._save()
        
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
    """Load guild settings (compatibility function)."""
    get_settings_manager()


def save_guild_settings() -> None:
    """Save guild settings (compatibility function)."""
    get_settings_manager()._save()


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


def get_all_guild_settings(guild_id: int) -> dict:
    """Get all settings (compatibility function)."""
    return get_settings_manager().get_all(guild_id)


def clear_guild_settings(guild_id: int) -> None:
    """Clear all settings (compatibility function)."""
    get_settings_manager().clear(guild_id)


# For backward compatibility, keep the old dict reference
guild_settings = {}