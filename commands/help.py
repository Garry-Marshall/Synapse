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
• Just type a message in a monitored channel or DM to chat with the AI  
• Attach images or text files to include them in the prompt  
• Prefix a message with `*` to prevent the bot from responding  

---
### ⚙️ Configuration (`/config`)
*(Some options require admin permissions)*

**Show configuration**
• `/config show show` — Show all current server settings  

**System prompt**
• `/config system show`  
• `/config system set <prompt>` *(admin)*  
• `/config system clear` *(admin)*  

**Temperature**
• `/config temperature show`  
• `/config temperature set <0.0–2.0>` *(admin)*  
• `/config temperature reset` *(admin)*  

**Max tokens**
• `/config max_tokens show`  
• `/config max_tokens set <number | -1>` *(admin)*  
• `/config max_tokens reset` *(admin)*  

**Debug logging**
• `/config debug show`  
• `/config debug on|off` *(admin)*  
• `/config debug level info|debug` *(admin)*  

**Web search**
• `/config search show`  
• `/config search on|off` *(admin)*  

**Conversation tools**
• `/config clear last` — Remove the last user/assistant exchange  

---
### 🧠 Conversation Management
• `/reset` — Clear conversation history and start fresh  
• `/history` — Show number of messages in conversation history  
• `/stats` — Display detailed conversation statistics  
• `/stats_reset` — Reset statistics for this channel  

---
### 🧠 Model Management
• `/model` — Select the active AI model for this server  

---
### 📊 Voice / TTS
• `/join` — Join your current voice channel  
• `/leave` — Leave the voice channel  
• `/voice` — Select the TTS voice  

---
### ℹ️ Notes
• Settings are saved per server and persist across restarts  
• Admin-only options are marked *(admin)*  
• Autocomplete is available for `/config` categories and actions  
• Temperature and max_tokens affect response style and length  
• The bot automatically searches the web when needed  
• Supported file types: images (PNG, JPG, GIF, WebP), PDFs, and text files  

---
"""
        await interaction.response.send_message(help_text, ephemeral=True)
        logger.info(f"Help command used by {interaction.user.name} in {interaction.guild.name if interaction.guild else 'DM'}")