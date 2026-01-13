"""
Commands package initialization.
Exports all command setup functions and shared data.
"""

from .conversation import setup_conversation_commands
from .stats import setup_stats_commands
from .voice import (
    setup_voice_commands,
    voice_clients,
    selected_voices,
    get_voice_client,
    get_selected_voice,
)
from .model import (
    setup_model_command,
    selected_models,
    available_models,
    default_model,
    get_selected_model,
    initialize_models,
)
from .config_cmd import setup_config_command
from .help import setup_help_command


def setup_all_commands(tree):
    """
    Register all commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    setup_conversation_commands(tree)
    setup_stats_commands(tree)
    setup_voice_commands(tree)
    setup_model_command(tree)
    setup_config_command(tree)
    setup_help_command(tree)


__all__ = [
    # Setup functions
    'setup_all_commands',
    'setup_conversation_commands',
    'setup_stats_commands',
    'setup_voice_commands',
    'setup_model_command',
    'setup_config_command',
    'setup_help_command',
    
    # Voice data
    'voice_clients',
    'selected_voices',
    'get_voice_client',
    'get_selected_voice',
    
    # Model data
    'selected_models',
    'available_models',
    'default_model',
    'get_selected_model',
    'initialize_models',
]