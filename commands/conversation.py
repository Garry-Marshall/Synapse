"""
Conversation management commands.
Handles /reset and /history commands.
"""
import discord
from discord import app_commands
import logging

from config import CHANNEL_IDS, ALLOW_DMS
from utils import (
    clear_conversation_history,
    reset_stats,
    get_conversation_history
)

logger = logging.getLogger(__name__)


def setup_conversation_commands(tree: app_commands.CommandTree):
    """
    Register conversation commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name='reset', description='Reset the conversation history for this channel or DM')
    async def reset_conversation(interaction: discord.Interaction):
        """Slash command to reset the conversation history for the current channel or DM."""
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
        
        # Clear history and reset stats
        clear_conversation_history(conversation_id)
        reset_stats(conversation_id)
        
        await interaction.response.send_message(
            "✅ Conversation history and statistics have been reset. Starting fresh!", 
            ephemeral=True
        )
        logger.info(f"Reset conversation for {conversation_id}")
    
    
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
        
        from config import MAX_HISTORY
        await interaction.response.send_message(
            f"📊 This conversation has {msg_count} messages in its history (max: {MAX_HISTORY * 2}).",
            ephemeral=True
        )
        logger.info(f"History check for {conversation_id}: {msg_count} messages")