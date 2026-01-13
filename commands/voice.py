"""
Voice and TTS commands.
Handles /join, /leave, and /voice commands.
"""
import discord
from discord import app_commands
from typing import Dict
import logging

from config import ENABLE_TTS, AVAILABLE_VOICES, ALLTALK_VOICE, VOICE_DESCRIPTIONS

logger = logging.getLogger(__name__)

# Store voice channel connections per guild
voice_clients: Dict[int, discord.VoiceClient] = {}

# Store selected voice per guild
selected_voices: Dict[int, str] = {}


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
        selected_voices[guild_id] = selected_voice
        
        await interaction.response.send_message(
            f"✅ Voice changed to: **{selected_voice}**",
            ephemeral=True
        )
        logger.info(f"Voice changed to '{selected_voice}' in {interaction.guild.name}")


def setup_voice_commands(tree: app_commands.CommandTree):
    """
    Register voice commands with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name='join', description='Join your voice channel')
    async def join_voice(interaction: discord.Interaction):
        """Join the voice channel the user is currently in."""
        if not ENABLE_TTS:
            await interaction.response.send_message(
                "❌ TTS is currently disabled in the bot configuration.", 
                ephemeral=True
            )
            return
        
        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel first!", 
                ephemeral=True
            )
            return
        
        voice_channel = interaction.user.voice.channel
        guild_id = interaction.guild.id
        
        # Check if already connected
        if guild_id in voice_clients and voice_clients[guild_id].is_connected():
            if voice_clients[guild_id].channel.id == voice_channel.id:
                await interaction.response.send_message(
                    "✅ Already in your voice channel!", 
                    ephemeral=True
                )
                return
            else:
                # Move to the new channel
                await voice_clients[guild_id].move_to(voice_channel)
                await interaction.response.send_message(
                    f"✅ Moved to {voice_channel.name}!", 
                    ephemeral=True
                )
                logger.info(f"Moved to voice channel: {voice_channel.name} in {interaction.guild.name}")
                return
        
        try:
            # Connect to voice channel
            voice_client = await voice_channel.connect()
            voice_clients[guild_id] = voice_client
            await interaction.response.send_message(
                f"✅ Joined {voice_channel.name}! I'll speak my responses here.", 
                ephemeral=True
            )
            logger.info(f"Joined voice channel: {voice_channel.name} in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error joining voice channel: {e}")
            await interaction.response.send_message(
                f"❌ Failed to join voice channel: {str(e)}", 
                ephemeral=True
            )
    
    
    @tree.command(name='leave', description='Leave the voice channel')
    async def leave_voice(interaction: discord.Interaction):
        """Leave the current voice channel."""
        if not ENABLE_TTS:
            await interaction.response.send_message(
                "❌ TTS is currently disabled in the bot configuration.", 
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        
        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            await interaction.response.send_message(
                "❌ I'm not in a voice channel!", 
                ephemeral=True
            )
            return
        
        try:
            await voice_clients[guild_id].disconnect()
            del voice_clients[guild_id]
            await interaction.response.send_message(
                "✅ Left the voice channel.", 
                ephemeral=True
            )
            logger.info(f"Left voice channel in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")
            await interaction.response.send_message(
                f"❌ Failed to leave voice channel: {str(e)}", 
                ephemeral=True
            )
    
    
    @tree.command(name='voice', description='Select TTS voice')
    async def select_voice(interaction: discord.Interaction):
        """Show dropdown to select TTS voice."""
        if not ENABLE_TTS:
            await interaction.response.send_message(
                "❌ TTS is currently disabled in the bot configuration.", 
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        current_voice = selected_voices.get(guild_id, ALLTALK_VOICE)
        
        # Build voice list with descriptions
        voice_list = "\n".join([
            f"• **{voice}** - {VOICE_DESCRIPTIONS.get(voice, 'Unknown')}"
            for voice in AVAILABLE_VOICES
        ])
        
        view = VoiceSelectView(current_voice)
        await interaction.response.send_message(
            f"**Current voice:** {current_voice}\n\n"
            f"**Available voices:**\n{voice_list}\n\n"
            f"Select a new voice:",
            view=view,
            ephemeral=True
        )


def get_voice_client(guild_id: int) -> discord.VoiceClient:
    """Get the voice client for a guild."""
    return voice_clients.get(guild_id)


def get_selected_voice(guild_id: int) -> str:
    """Get the selected voice for a guild."""
    return selected_voices.get(guild_id, ALLTALK_VOICE)