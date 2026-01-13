"""
Config package initialization.
Exports all settings and constants for easy importing.
"""

from .settings import (
    # Discord
    DISCORD_TOKEN,
    CHANNEL_IDS,
    
    # LMStudio
    LMSTUDIO_URL,
    
    # Conversation
    MAX_HISTORY,
    CONTEXT_MESSAGES,
    
    # Bot Behavior
    IGNORE_BOTS,
    ALLOW_DMS,
    
    # File Processing
    ALLOW_IMAGES,
    MAX_IMAGE_SIZE,
    ALLOW_TEXT_FILES,
    MAX_TEXT_FILE_SIZE,
    ALLOW_PDF,
    MAX_PDF_SIZE,
    
    # Model
    HIDE_THINKING,
    
    # TTS
    ENABLE_TTS,
    ALLTALK_URL,
    ALLTALK_VOICE,
    
    # File Paths
    STATS_FILE,
    GUILD_SETTINGS_FILE,
    LOG_DIR,
    
    # Search
    SEARCH_COOLDOWN,
)

from .constants import (
    # TTS
    AVAILABLE_VOICES,
    VOICE_DESCRIPTIONS,
    
    # Search
    SEARCH_TRIGGERS,
    NEGATIVE_SEARCH_TRIGGERS,
    MIN_MESSAGE_LENGTH_FOR_SEARCH,
    MAX_SEARCH_RESULTS,
    
    # File Processing
    TEXT_FILE_EXTENSIONS,
    FILE_ENCODINGS,
    MAX_PDF_CHARS,
    MAX_URL_CHARS,
    
    # Defaults
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
)

__all__ = [
    # Settings
    'DISCORD_TOKEN',
    'CHANNEL_IDS',
    'LMSTUDIO_URL',
    'MAX_HISTORY',
    'CONTEXT_MESSAGES',
    'IGNORE_BOTS',
    'ALLOW_DMS',
    'ALLOW_IMAGES',
    'MAX_IMAGE_SIZE',
    'ALLOW_TEXT_FILES',
    'MAX_TEXT_FILE_SIZE',
    'ALLOW_PDF',
    'MAX_PDF_SIZE',
    'HIDE_THINKING',
    'ENABLE_TTS',
    'ALLTALK_URL',
    'ALLTALK_VOICE',
    'STATS_FILE',
    'GUILD_SETTINGS_FILE',
    'LOG_DIR',
    'SEARCH_COOLDOWN',
    
    # Constants
    'AVAILABLE_VOICES',
    'VOICE_DESCRIPTIONS',
    'SEARCH_TRIGGERS',
    'NEGATIVE_SEARCH_TRIGGERS',
    'MIN_MESSAGE_LENGTH_FOR_SEARCH',
    'MAX_SEARCH_RESULTS',
    'TEXT_FILE_EXTENSIONS',
    'FILE_ENCODINGS',
    'MAX_PDF_CHARS',
    'MAX_URL_CHARS',
    'DEFAULT_SYSTEM_PROMPT',
    'DEFAULT_TEMPERATURE',
    'DEFAULT_MAX_TOKENS',
    'DEFAULT_MODEL',
]