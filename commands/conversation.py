"""
Conversation management commands.
Handles /reset and /history commands.
"""
import discord
from discord import app_commands
import logging

from config.settings import CHANNEL_IDS, ALLOW_DMS
from utils.stats_manager import get_conversation_history

logger = logging.getLogger(__name__)


def setup_conversation_commands(tree: app_commands.CommandTree):
    """
    Register conversation commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name='history', description='Show the conversation history length')
    async def show_history(interaction: discord.Interaction):
        """Slash command to show how many messages are in the current channel's or DM's history."""
        conversation_id = interaction.channel_id if interaction.guild else interaction.user.id
        
        if interaction.guild and interaction.channel_id not in CHANNEL_IDS:
            await interaction.response.send_message(
                "❌ This command only works in monitored channels.", 
                ephemeral=True
            )
            return
        
        if not interaction.guild and not ALLOW_DMS:
            await interaction.response.send_message(
                "❌ DM conversations are not enabled.", 
                ephemeral=True
            )
            return
        
        history = get_conversation_history(conversation_id)
        msg_count = len(history)
        
        from config.settings import MAX_HISTORY
        await interaction.response.send_message(
            f"📊 This conversation has {msg_count} messages in its history (max: {MAX_HISTORY * 2}).",
            ephemeral=True
        )
        logger.info(f"History check for {conversation_id}: {msg_count} messages")