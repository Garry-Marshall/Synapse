"""
Bot instance creation and initialization.
Central location for the Discord bot setup.
"""
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

# Bot setup with message content intent
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Need this for voice channels

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)


def get_bot():
    """
    Get the bot instance.
    
    Returns:
        Discord bot instance
    """
    return bot