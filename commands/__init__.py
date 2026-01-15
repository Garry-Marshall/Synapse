"""
Commands package initialization.
Exports all command setup functions and shared data.
"""

from commands.stats import setup_stats_commands
from commands.voice import setup_voice_commands, voice_clients, get_voice_client
from commands.model import setup_model_command, selected_models, available_models, default_model, get_selected_model, initialize_models
from commands.config_cmd import setup_config_command
from commands.help import setup_help_command
from commands.status import setup_status_command
from commands.context_cmd import setup_context_command


def setup_all_commands(tree):
    """
    Register all commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    setup_stats_commands(tree)
    setup_voice_commands(tree)
    setup_model_command(tree)
    setup_config_command(tree)
    setup_help_command(tree)
    setup_status_command(tree)
    setup_context_command(tree)


__all__ = [
    # Setup functions
    'setup_all_commands',
    'setup_stats_commands',
    'setup_voice_commands',
    'setup_model_command',
    'setup_config_command',
    'setup_help_command',
    'setup_status_command',
    'setup_context_command',
    
    # Voice data
    'voice_clients',
    'get_voice_client',
    
    # Model data
    'selected_models',
    'available_models',
    'default_model',
    'get_selected_model',
    'initialize_models',
]