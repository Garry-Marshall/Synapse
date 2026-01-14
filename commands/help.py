"""
Help command.
Displays all available bot commands and usage instructions.
"""
import discord
from discord import app_commands
import logging

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
        help_text = """
🤖 **Jarvis — Help**

---
### 💬 Core Usage
• Just type a message in a monitored channel or DM the bot to chat with the AI  
• Attach images or text files to include them in the prompt  
• Prefix a message with `*` to prevent the bot from responding  

---
### ⚙️ Configuration
*(Some options require admin permissions)*
• `/config` — Opens the config dialog box

---
### 🧠 Conversation Management
• `/history` — Show number of messages in conversation history  
• `/stats` — Display detailed conversation statistics  

---
### 🧠 Model Management
• `/model` — Select the active AI model for this server  

---
### 📊 Voice / TTS
• `/join` — Join your current voice channel  
• `/leave` — Leave the voice channel  
• `/voice` — Select the TTS voice persona

---
### ℹ️ Notes
• Settings are saved per server and persist across restarts  
• Temperature and max_tokens affect response style and length  
• The bot automatically searches the web when needed  
• Supported file types: images (PNG, JPG, GIF, WebP), PDFs, and text files  

---
"""
        await interaction.response.send_message(help_text, ephemeral=True)
        
        # Fixed: Safely handle guild name for logging
        guild_name = interaction.guild.name if interaction.guild else 'DM'
        user_name = interaction.user.name if interaction.user else 'Unknown'
        logger.info(f"Help command used by {user_name} in {guild_name}")