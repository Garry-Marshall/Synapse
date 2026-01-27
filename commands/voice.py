"""
Voice and TTS commands.
Handles /join, /leave, and /voice commands.
"""
import discord
from discord import app_commands
from discord.ext import voice_recv
from typing import Dict, Optional
import logging

from config.settings import ENABLE_TTS, ENABLE_MOSHI, MOSHI_TEXT_PROMPT, MOSHI_VOICE
from config.constants import (
    AVAILABLE_VOICES,
    VOICE_DESCRIPTIONS,
    MSG_VOICE_CHANGED,
    MSG_SERVER_ONLY,
    MSG_TTS_DISABLED_GLOBAL,
    MSG_TTS_DISABLED_SERVER,
    MSG_NEED_VOICE_CHANNEL,
    MSG_NOT_IN_VOICE,
    MSG_ALREADY_IN_VOICE,
    MSG_LEFT_VOICE,
    MSG_JOINED_VOICE,
    MSG_MOVED_VOICE,
    MSG_FAILED_TO_JOIN_VOICE,
)
from utils.settings_manager import is_tts_enabled_for_guild, get_guild_voice, get_guild_moshi_voice, set_guild_setting, get_guild_setting
from services.moshi_voice_handler import start_moshi_voice, stop_moshi_voice, is_moshi_active
from services.moshi import is_moshi_available


logger = logging.getLogger(__name__)

# Store voice channel connections per guild (Still in-memory as these are active sessions)
voice_clients: Dict[int, discord.VoiceClient] = {}

# Moshi voice options
MOSHI_VOICES = [
    "NATF0.pt", "NATF1.pt", "NATF2.pt", "NATF3.pt",  # Female voices
    "NATM0.pt", "NATM1.pt", "NATM2.pt", "NATM3.pt"   # Male voices
]

MOSHI_VOICE_DESCRIPTIONS = {
    "NATF0.pt": "Female voice 0",
    "NATF1.pt": "Female voice 1",
    "NATF2.pt": "Female voice 2",
    "NATF3.pt": "Female voice 3",
    "NATM0.pt": "Male voice 0",
    "NATM1.pt": "Male voice 1",
    "NATM2.pt": "Male voice 2",
    "NATM3.pt": "Male voice 3",
}


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
            MSG_VOICE_CHANGED.format(selected_voice=selected_voice),
            ephemeral=True
        )
        logger.info(f"Voice changed to '{selected_voice}' in guild {guild_id} ({interaction.guild.name})")


class MoshiVoiceSelectView(discord.ui.View):
    """View with dropdown for Moshi voice selection."""
    def __init__(self, current_voice: str):
        super().__init__(timeout=60)
        self.add_item(MoshiVoiceSelectDropdown(current_voice))


class MoshiVoiceSelectDropdown(discord.ui.Select):
    """Dropdown menu for selecting Moshi AI voice."""
    def __init__(self, current_voice: str):
        options = [
            discord.SelectOption(
                label=voice.replace(".pt", ""),
                value=voice,
                description=MOSHI_VOICE_DESCRIPTIONS.get(voice, f"Voice: {voice}"),
                default=(voice == current_voice)
            )
            for voice in MOSHI_VOICES
        ]

        super().__init__(
            placeholder="Select a Moshi voice...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_voice = self.values[0]
        guild_id = interaction.guild.id

        # Save to persistent guild settings
        set_guild_setting(guild_id, "moshi_voice", selected_voice)

        await interaction.response.send_message(
            f"✅ Moshi voice changed to **{selected_voice.replace('.pt', '')}**.\n\n"
            f"The new voice will be used the next time you start Moshi.",
            ephemeral=True
        )
        logger.info(f"Moshi voice changed to '{selected_voice}' in guild {guild_id} ({interaction.guild.name})")


class MoshiPromptModal(discord.ui.Modal, title='Customize Moshi Prompt'):
    """Modal dialog for customizing Moshi's system prompt."""

    prompt_input = discord.ui.TextInput(
        label='System Prompt',
        style=discord.TextStyle.paragraph,
        placeholder='Enter the system prompt for Moshi...',
        required=True,
        max_length=1000,
        default='You are a helpful AI assistant.'
    )

    def __init__(self, current_prompt: str):
        super().__init__()
        self.prompt_input.default = current_prompt

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        new_prompt = self.prompt_input.value

        # Save to persistent guild settings
        set_guild_setting(guild_id, "moshi_prompt", new_prompt)

        await interaction.response.send_message(
            f"✅ Moshi prompt updated successfully!\n\n**New prompt:**\n```\n{new_prompt}\n```\n\n"
            f"The new prompt will be used the next time you start Moshi.",
            ephemeral=True
        )
        logger.info(f"Moshi prompt changed in guild {guild_id} ({interaction.guild.name})")


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
            await interaction.response.send_message(MSG_FAILED_TO_JOIN_VOICE, ephemeral=True)
    
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

        # Stop Moshi if active
        if is_moshi_active(guild_id):
            await stop_moshi_voice(guild_id)
            logger.info(f"Stopped Moshi when leaving voice in guild {guild_id}")

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
            f"• **{voice}** - {VOICE_DESCRIPTIONS.get(voice, 'Unknown')}"
            for voice in AVAILABLE_VOICES
        ])
        
        view = VoiceSelectView(current_voice)
        await interaction.response.send_message(
            f"**Current voice:** {current_voice}\n\n**Available voices:**\n{voice_list}\n\nSelect a new voice:",
            view=view,
            ephemeral=True
        )

    @tree.command(name='moshi', description='Start or stop Moshi AI voice conversation')
    @app_commands.describe(action="Start or stop Moshi voice AI, or customize settings")
    @app_commands.choices(action=[
        app_commands.Choice(name="Start", value="start"),
        app_commands.Choice(name="Stop", value="stop"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Voice", value="voice"),
        app_commands.Choice(name="Prompt", value="prompt")
    ])
    async def moshi_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
        # Quick validation that doesn't need deferring
        if not interaction.guild:
            await interaction.response.send_message(MSG_SERVER_ONLY, ephemeral=True)
            return

        if not ENABLE_MOSHI:
            await interaction.response.send_message(
                "❌ Moshi AI is not enabled. Please enable it in the configuration.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        # Handle voice selection
        if action.value == "voice":
            # Get current voice from guild settings or use default
            current_voice = get_guild_moshi_voice(guild_id)

            # Build voice list display
            voice_list = "**Female voices:**\n"
            for voice in [v for v in MOSHI_VOICES if "NATF" in v]:
                voice_list += f"• **{voice.replace('.pt', '')}** - {MOSHI_VOICE_DESCRIPTIONS.get(voice)}\n"

            voice_list += "\n**Male voices:**\n"
            for voice in [v for v in MOSHI_VOICES if "NATM" in v]:
                voice_list += f"• **{voice.replace('.pt', '')}** - {MOSHI_VOICE_DESCRIPTIONS.get(voice)}\n"

            view = MoshiVoiceSelectView(current_voice)
            await interaction.response.send_message(
                f"**Current Moshi voice:** {current_voice.replace('.pt', '')}\n\n{voice_list}\nSelect a new voice:",
                view=view,
                ephemeral=True
            )
            return

        # Handle prompt customization
        if action.value == "prompt":
            # Get current prompt from guild settings or use default
            current_prompt = get_guild_setting(guild_id, "moshi_prompt", MOSHI_TEXT_PROMPT)

            # Show modal for prompt input
            modal = MoshiPromptModal(current_prompt)
            await interaction.response.send_modal(modal)
            return

        # Status is quick - no defer needed
        if action.value == "status":
            is_active_now = is_moshi_active(guild_id)

            # Defer before the network call
            await interaction.response.defer(ephemeral=True)

            is_available = await is_moshi_available()

            status_msg = "**Moshi AI Status:**\n"
            status_msg += f"• Service Available: {'✅ Yes' if is_available else '❌ No'}\n"
            status_msg += f"• Active in this server: {'✅ Yes' if is_active_now else '❌ No'}"

            if is_active_now:
                voice_client = get_voice_client(guild_id)
                if voice_client and voice_client.channel:
                    status_msg += f"\n• Channel: {voice_client.channel.name}"

            await interaction.followup.send(status_msg, ephemeral=True)
            return

        if action.value == "start":
            # Quick checks first
            if is_moshi_active(guild_id):
                await interaction.response.send_message(
                    "⚠️ Moshi is already active in this server. Use `/moshi stop` first.",
                    ephemeral=True
                )
                return

            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.response.send_message(MSG_NEED_VOICE_CHANNEL, ephemeral=True)
                return

            voice_channel = interaction.user.voice.channel

            # Try to defer, but continue even if interaction expired
            deferred = False
            try:
                await interaction.response.defer(ephemeral=True)
                deferred = True
            except discord.errors.NotFound:
                logger.warning("Interaction expired before defer, starting Moshi anyway")
            except Exception as e:
                logger.warning(f"Could not defer interaction: {e}")

            try:
                voice_client = voice_clients.get(guild_id)

                if not voice_client or not voice_client.is_connected():
                    voice_client = await voice_channel.connect(cls=voice_recv.VoiceRecvClient)
                    voice_clients[guild_id] = voice_client
                    logger.info(f"Joined voice channel '{voice_channel.name}' for Moshi in guild {guild_id}")
                elif voice_client.channel.id != voice_channel.id:
                    await voice_client.move_to(voice_channel)
                    logger.info(f"Moved to voice channel '{voice_channel.name}' for Moshi in guild {guild_id}")

                success = await start_moshi_voice(guild_id, voice_client)

                if success:
                    logger.info(f"Moshi voice started in guild {guild_id}")
                    if deferred:
                        await interaction.followup.send(
                            f"🎙️ Moshi AI voice conversation started in **{voice_channel.name}**!\n"
                            f"You can now speak and Moshi will respond with voice.",
                            ephemeral=True
                        )
                else:
                    logger.error(f"Failed to start Moshi in guild {guild_id}")
                    if deferred:
                        await interaction.followup.send(
                            "❌ Failed to start Moshi. Please check that Moshi is running and accessible.",
                            ephemeral=True
                        )

            except Exception as e:
                logger.error(f"Error starting Moshi in guild {guild_id}: {e}", exc_info=True)
                if deferred:
                    try:
                        await interaction.followup.send(
                            f"❌ Error starting Moshi: {str(e)}",
                            ephemeral=True
                        )
                    except:
                        pass

        elif action.value == "stop":
            # Quick check
            if not is_moshi_active(guild_id):
                await interaction.response.send_message(
                    "⚠️ Moshi is not currently active in this server.",
                    ephemeral=True
                )
                return

            # Try to defer, but if interaction expired, still perform the stop
            deferred = False
            try:
                await interaction.response.defer(ephemeral=True)
                deferred = True
            except discord.errors.NotFound:
                logger.warning("Interaction expired before defer, stopping Moshi anyway")
            except Exception as e:
                logger.warning(f"Could not defer interaction: {e}")

            try:
                await stop_moshi_voice(guild_id)
                logger.info(f"Moshi voice stopped for guild {guild_id}")

                if deferred:
                    await interaction.followup.send(
                        "🛑 Moshi AI voice conversation stopped.",
                        ephemeral=True
                    )

            except Exception as e:
                logger.error(f"Error stopping Moshi in guild {guild_id}: {e}", exc_info=True)
                if deferred:
                    try:
                        await interaction.followup.send(
                            f"❌ Error stopping Moshi: {str(e)}",
                            ephemeral=True
                        )
                    except:
                        pass


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