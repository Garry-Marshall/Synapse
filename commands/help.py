"""
Help command.
Displays all available bot commands and usage instructions.
"""
import discord
from discord import app_commands
import logging

from config.settings import ENABLE_TTS, ENABLE_COMFYUI, COMFYUI_TRIGGERS
from utils.settings_manager import is_tts_enabled_for_guild, is_comfyui_enabled_for_guild

logger = logging.getLogger(__name__)


def setup_help_command(tree: app_commands.CommandTree):
    """
    Register help command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name="help", description="Show all available bot commands")
    async def help_command(interaction: discord.Interaction):
        """Display comprehensive help information about the bot."""
        # Get guild ID for checking TTS and ComfyUI status
        guild_id = interaction.guild.id if interaction.guild else None
        tts_enabled = ENABLE_TTS and (guild_id is None or is_tts_enabled_for_guild(guild_id))
        comfyui_enabled = ENABLE_COMFYUI and (guild_id is None or is_comfyui_enabled_for_guild(guild_id))

        # Build help text dynamically
        help_text = """
🤖 **Jarvis — Help**
---
### 💬 Core Usage
• Just type a message in a monitored channel or DM the bot to chat with the AI
• Attach images or text files to include them in the prompt
• Prefix a message with `*` to prevent the bot from responding
---
### ⚙️ Configuration
*(Requires admin permissions)*
• `/config` — Opens the config dialog box
• `/add_channel` — bot will monitor this channel for messages
• `/remove_channel` — bot will stop monitoring this channel
• `/list_channels` — display all channels the bot monitors
---
### 🧠 Conversation Management
• `/stats` — Display detailed conversation statistics
• `/context` — Show context window usage and token limits
---
### 🤖 Model Management
• `/model` — Select the active AI model for this server
---"""

        # Add TTS section if enabled
        if tts_enabled:
            help_text += """
### 📊 Voice / TTS
• `/join` — Join your current voice channel
• `/leave` — Leave the voice channel
• `/voice` — Select the TTS voice persona
---"""

        help_text += """
### 🔧 System
• `/status` — Show bot health and connectivity status
---
### ℹ️ Notes
• Settings are saved per server and persist across restarts
• Temperature and max_tokens affect response style and length
• The bot automatically searches the web when needed
• Supported file types: images (PNG, JPG, GIF, WebP), PDFs, and text files  """

        # Add ComfyUI note if enabled (both globally and for this guild)
        if comfyui_enabled:
            trigger_words = "', '".join(COMFYUI_TRIGGERS)
            help_text += f"• Use trigger words '{trigger_words}' to create images with ComfyUI\n"

        help_text += "\n---\n"

        await interaction.response.send_message(help_text, ephemeral=True)

        # Fixed: Safely handle guild name for logging
        guild_name = interaction.guild.name if interaction.guild else 'DM'
        user_name = interaction.user.name if interaction.user else 'Unknown'
        logger.info(f"Help command used by {user_name} in {guild_name}")