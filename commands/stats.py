"""
Statistics commands.
Handles /stats command.
"""
import discord
from discord import app_commands
import logging

from config.settings import ALLOW_DMS
from config.constants import MSG_DM_NOT_ENABLED
from utils.stats_manager import get_or_create_stats, get_stats_summary, get_guild_stats_summary


logger = logging.getLogger(__name__)


def setup_stats_commands(tree: app_commands.CommandTree):
    """
    Register statistics commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name='stats', description='Show conversation statistics')
    async def show_stats(interaction: discord.Interaction):
        """Slash command to show conversation statistics."""
        if not interaction.guild and not ALLOW_DMS:
            await interaction.response.send_message(
                MSG_DM_NOT_ENABLED,
                ephemeral=True
            )
            return

        # In guilds, show guild-wide stats; in DMs, show user stats
        if interaction.guild:
            stats_message = get_guild_stats_summary(interaction.guild_id)
            logger.info(f"Guild stats displayed for guild {interaction.guild_id}")
        else:
            conversation_id = interaction.user.id
            get_or_create_stats(conversation_id)
            stats_message = get_stats_summary(conversation_id)
            logger.info(f"Stats displayed for DM conversation {conversation_id}")

        await interaction.response.send_message(stats_message, ephemeral=True)