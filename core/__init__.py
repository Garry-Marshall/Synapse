"""
Core package initialization.
Exports bot instance and event setup.
"""

from .bot_instance import bot, get_bot
from .events import setup_events

__all__ = [
    'bot',
    'get_bot',
    'setup_events',
]