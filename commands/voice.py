"""
Voice and TTS commands.
Handles /join, /leave, and /voice commands.
"""
import discord
from discord import app_commands
from typing import Dict, Optional
import logging

from config.settings import ENABLE_TTS
from config.constants import (
    AVAILABLE_VOICES,
    VOICE_DESCRIPTIONS,
    MSG_SERVER_ONLY,
    MSG_TTS_DISABLED_GLOBAL,
    MSG_TTS_DISABLED_SERVER,
    MSG_NEED_VOICE_CHANNEL,
    MSG_NOT_IN_VOICE,
    MSG_ALREADY_IN_VOICE,
    MSG_LEFT_VOICE,
    MSG_JOINED_VOICE,
    MSG_MOVED_VOICE,
)
from utils.settings_manager import is_tts_enabled_for_guild, get_guild_voice, set_guild_setting


logger = logging.getLogger(__name__)

# Store voice channel connections per guild (Still in-memory as these are active sessions)
voice_clients: Dict[int, discord.VoiceClient] = {}


def check_tts_enabled(guild_id: int) -> tuple[bool, Optional[str]]:
    """
    Check if TTS is enabled for a guild and return appropriate error message.
    
    Args:
        guild_id: Guild ID to check
        
    Returns:
        Tuple of (is_enabled, error_message)
        error_message is None if TTS is enabled
    """
    if not ENABLE_TTS:
        return False, MSG_TTS_DISABLED_GLOBAL
    
    if not is_tts_enabled_for_guild(guild_id):
        return False, MSG_TTS_DISABLED_SERVER
    
    return True, None


class VoiceSelectView(discord.ui.View):
    """View with dropdown for voice selection."""
    def __init__(self, current_voice: str):
        super().__init__(timeout=60)
        self.add_item(VoiceSelectDropdown(current_voice))


class VoiceSelectDropdown(discord.ui.Select):
    """Dropdown menu for selecting TTS voice."""
    def __init__(self, current_voice: str):
        options = [
            discord.SelectOption(
                label=voice.capitalize(),
                value=voice,
                description=VOICE_DESCRIPTIONS.get(voice, f"Voice: {voice}"),
                default=(voice == current_voice)
            )
            for voice in AVAILABLE_VOICES
        ]
        
        super().__init__(
            placeholder="Select a voice...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_voice = self.values[0]
        guild_id = interaction.guild.id
        
        # Save to persistent guild settings
        set_guild_setting(guild_id, "selected_voice", selected_voice)
        
        await interaction.response.send_message(
            f"âœ… Voice changed to: **{selected_voice}**",
            ephemeral=True
        )
        logger.info(f"Voice changed to '{selected_voice}' in guild {guild_id} ({interaction.guild.name})")


def setup_voice_commands(tree: app_commands.CommandTree):
    """Register voice commands with the bot's command tree."""
    
    @tree.command(name='join', description='Join your voice channel')
    async def join_voice(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                MSG_SERVER_ONLY,
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        
        # Use helper function for consistent error messaging
        is_enabled, error_msg = check_tts_enabled(guild_id)
        if not is_enabled:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(MSG_NEED_VOICE_CHANNEL, ephemeral=True)
            return
        
        voice_channel = interaction.user.voice.channel
        
        if guild_id in voice_clients and voice_clients[guild_id].is_connected():
            if voice_clients[guild_id].channel.id == voice_channel.id:
                await interaction.response.send_message(MSG_ALREADY_IN_VOICE, ephemeral=True)
                return
            await voice_clients[guild_id].move_to(voice_channel)
            await interaction.response.send_message(MSG_MOVED_VOICE.format(channel=voice_channel.name), ephemeral=True)
            logger.info(f"Moved to voice channel '{voice_channel.name}' in guild {guild_id}")
            return
        
        try:
            voice_client = await voice_channel.connect()
            voice_clients[guild_id] = voice_client
            await interaction.response.send_message(MSG_JOINED_VOICE.format(channel=voice_channel.name), ephemeral=True)
            logger.info(f"Joined voice channel '{voice_channel.name}' in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error joining voice channel in guild {guild_id}: {e}", exc_info=True)
            await interaction.response.send_message(f"âŒ Failed to join voice channel: {str(e)}", ephemeral=True)
    
    @tree.command(name='leave', description='Leave the voice channel')
    async def leave_voice(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                MSG_SERVER_ONLY,
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            await interaction.response.send_message(MSG_NOT_IN_VOICE, ephemeral=True)
            return
        
        channel_name = voice_clients[guild_id].channel.name if voice_clients[guild_id].channel else "unknown"
        await voice_clients[guild_id].disconnect()
        del voice_clients[guild_id]
        await interaction.response.send_message(MSG_LEFT_VOICE, ephemeral=True)
        logger.info(f"Left voice channel '{channel_name}' in guild {guild_id}")
    
    @tree.command(name='voice', description='Select TTS voice')
    async def select_voice(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                MSG_SERVER_ONLY,
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        
        # Use helper function for consistent error messaging
        is_enabled, error_msg = check_tts_enabled(guild_id)
        if not is_enabled:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        # Pull from persistent settings
        current_voice = get_guild_voice(guild_id)
        
        voice_list = "\n".join([
            f"â€¢ **{voice}** - {VOICE_DESCRIPTIONS.get(voice, 'Unknown')}"
            for voice in AVAILABLE_VOICES
        ])
        
        view = VoiceSelectView(current_voice)
        await interaction.response.send_message(
            f"**Current voice:** {current_voice}\n\n**Available voices:**\n{voice_list}\n\nSelect a new voice:",
            view=view,
            ephemeral=True
        )


def get_voice_client(guild_id: int) -> Optional[discord.VoiceClient]:
    """
    Get the voice client for a guild.
    
    Args:
        guild_id: Guild ID
        
    Returns:
        Voice client if connected, None otherwise
    """
    return voice_clients.get(guild_id)


def remove_voice_client(guild_id: int) -> None:
    """
    Remove voice client for a guild from tracking.
    
    Args:
        guild_id: Guild ID
    """
    if guild_id in voice_clients:
        del voice_clients[guild_id]
        logger.debug(f"Removed voice client for guild {guild_id}")