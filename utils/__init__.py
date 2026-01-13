"""
Utils package initialization.
Exports all utility functions and managers for easy importing.
"""

# Logging utilities
from .logging_config import (
    setup_logging,
    log_effective_config,
    guild_debug_log,
    is_debug_enabled,
    get_debug_level,
)

# Text processing utilities
from .text_utils import (
    estimate_tokens,
    remove_thinking_tags,
    is_inside_thinking_tags,
    truncate_text,
    extract_urls,
    clean_discord_content,
    split_message,
)

# Statistics management
from .stats_manager import (
    conversation_histories,
    context_loaded,
    channel_stats,
    create_empty_stats,
    load_stats,
    save_stats,
    get_or_create_stats,
    update_stats,
    reset_stats,
    get_stats_summary,
    clear_conversation_history,
    add_message_to_history,
    get_conversation_history,
    is_context_loaded,
    set_context_loaded,
)

# Guild settings management
from .guild_settings import (
    load_guild_settings,
    save_guild_settings,
    get_guild_setting,
    set_guild_setting,
    delete_guild_setting,
    get_guild_system_prompt,
    get_guild_temperature,
    get_guild_max_tokens,
    is_search_enabled,
    get_all_guild_settings,
    clear_guild_settings,
)

__all__ = [
    # Logging
    'setup_logging',
    'log_effective_config',
    'guild_debug_log',
    'is_debug_enabled',
    'get_debug_level',
    
    # Text utilities
    'estimate_tokens',
    'remove_thinking_tags',
    'is_inside_thinking_tags',
    'truncate_text',
    'extract_urls',
    'clean_discord_content',
    'split_message',
    
    # Stats management
    'conversation_histories',
    'context_loaded',
    'channel_stats',
    'create_empty_stats',
    'load_stats',
    'save_stats',
    'get_or_create_stats',
    'update_stats',
    'reset_stats',
    'get_stats_summary',
    'clear_conversation_history',
    'add_message_to_history',
    'get_conversation_history',
    'is_context_loaded',
    'set_context_loaded',
    
    # Guild settings
    'load_guild_settings',
    'save_guild_settings',
    'get_guild_setting',
    'set_guild_setting',
    'delete_guild_setting',
    'get_guild_system_prompt',
    'get_guild_temperature',
    'get_guild_max_tokens',
    'is_search_enabled',
    'get_all_guild_settings',
    'clear_guild_settings',
]