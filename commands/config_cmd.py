"""
Configuration command.
Handles /config command for server settings using interactive modals.
"""
import discord
from discord import app_commands
from typing import Optional
import logging

from utils.guild_settings import (
    get_guild_setting,
    set_guild_setting,
    delete_guild_setting,
    get_guild_temperature,
    get_guild_max_tokens,
    is_debug_enabled,
    get_debug_level,
    is_search_enabled
)
from utils.stats_manager import (
    get_conversation_history,
    clear_conversation_history
)

logger = logging.getLogger(__name__)


def is_guild_admin(interaction: discord.Interaction) -> bool:
    """Check if the user has admin permissions in the guild."""
    if not interaction.guild or not interaction.user:
        return False
    return interaction.user.guild_permissions.administrator


class SystemPromptModal(discord.ui.Modal, title="System Prompt Configuration"):
    """Modal for configuring the system prompt."""
    
    system_prompt = discord.ui.TextInput(
        label="System Prompt",
        style=discord.TextStyle.paragraph,
        placeholder="Enter custom system prompt (leave blank to use default)",
        required=False,
        max_length=2000
    )
    
    def __init__(self, guild_id: int, current_prompt: Optional[str] = None):
        super().__init__()
        self.guild_id = guild_id
        if current_prompt:
            self.system_prompt.default = current_prompt
    
    async def on_submit(self, interaction: discord.Interaction):
        prompt_value = self.system_prompt.value.strip()
        
        if prompt_value:
            set_guild_setting(self.guild_id, "system_prompt", prompt_value)
            await interaction.response.send_message(
                f"✅ System prompt updated ({len(prompt_value)} characters).",
                ephemeral=True
            )
        else:
            delete_guild_setting(self.guild_id, "system_prompt")
            await interaction.response.send_message(
                "✅ System prompt cleared (using default).",
                ephemeral=True
            )
        
        logger.info(f"System prompt updated for guild {self.guild_id}")


class TemperatureModal(discord.ui.Modal, title="Temperature Configuration"):
    """Modal for configuring temperature."""
    
    temperature = discord.ui.TextInput(
        label="Temperature (0.0 - 2.0)",
        style=discord.TextStyle.short,
        placeholder="0.7",
        required=True,
        max_length=4
    )
    
    def __init__(self, guild_id: int, current_temp: float = 0.7):
        super().__init__()
        self.guild_id = guild_id
        self.temperature.default = str(current_temp)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            temp = float(self.temperature.value)
            if not 0.0 <= temp <= 2.0:
                await interaction.response.send_message(
                    "❌ Temperature must be between 0.0 and 2.0.",
                    ephemeral=True
                )
                return
            
            set_guild_setting(self.guild_id, "temperature", temp)
            await interaction.response.send_message(
                f"✅ Temperature set to **{temp}**.",
                ephemeral=True
            )
            logger.info(f"Temperature set to {temp} for guild {self.guild_id}")
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number between 0.0 and 2.0.",
                ephemeral=True
            )


class MaxTokensModal(discord.ui.Modal, title="Max Tokens Configuration"):
    """Modal for configuring max tokens."""
    
    max_tokens = discord.ui.TextInput(
        label="Max Tokens (-1 for unlimited)",
        style=discord.TextStyle.short,
        placeholder="-1",
        required=True,
        max_length=6
    )
    
    def __init__(self, guild_id: int, current_max: int = -1):
        super().__init__()
        self.guild_id = guild_id
        self.max_tokens.default = str(current_max)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            tokens = int(self.max_tokens.value)
            if tokens <= 0 and tokens != -1:
                await interaction.response.send_message(
                    "❌ Max tokens must be a positive integer or -1 (unlimited).",
                    ephemeral=True
                )
                return
            
            set_guild_setting(self.guild_id, "max_tokens", tokens)
            display = "unlimited" if tokens == -1 else str(tokens)
            await interaction.response.send_message(
                f"✅ Max tokens set to **{display}**.",
                ephemeral=True
            )
            logger.info(f"Max tokens set to {tokens} for guild {self.guild_id}")
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid integer or -1 for unlimited.",
                ephemeral=True
            )


class DebugLevelModal(discord.ui.Modal, title="Debug Level Configuration"):
    """Modal for configuring debug log level."""
    
    debug_level = discord.ui.TextInput(
        label="Debug Level (info or debug)",
        style=discord.TextStyle.short,
        placeholder="info",
        required=True,
        max_length=5
    )
    
    def __init__(self, guild_id: int, current_level: str = "info"):
        super().__init__()
        self.guild_id = guild_id
        self.debug_level.default = current_level
    
    async def on_submit(self, interaction: discord.Interaction):
        level = self.debug_level.value.lower().strip()
        
        if level not in {"info", "debug"}:
            await interaction.response.send_message(
                "❌ Debug level must be either 'info' or 'debug'.",
                ephemeral=True
            )
            return
        
        set_guild_setting(self.guild_id, "debug_level", level)
        await interaction.response.send_message(
            f"✅ Debug log level set to **{level.upper()}**.",
            ephemeral=True
        )
        logger.info(f"Debug log level set to {level} for guild {self.guild_id}")


class ConfigView(discord.ui.View):
    """Interactive view for bot configuration."""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.guild_id = guild_id
        self.update_toggle_buttons()
    
    def update_toggle_buttons(self):
        """Update button states based on current settings."""
        # Update debug button
        debug_enabled = is_debug_enabled(self.guild_id)
        self.toggle_debug.label = f"Debug: {'ON' if debug_enabled else 'OFF'}"
        self.toggle_debug.style = discord.ButtonStyle.success if debug_enabled else discord.ButtonStyle.secondary
        
        # Update search button
        search_enabled = is_search_enabled(self.guild_id)
        self.toggle_search.label = f"Web Search: {'ON' if search_enabled else 'OFF'}"
        self.toggle_search.style = discord.ButtonStyle.success if search_enabled else discord.ButtonStyle.secondary
    
    def create_embed(self) -> discord.Embed:
        """Create embed showing current configuration."""
        system_prompt = get_guild_setting(self.guild_id, "system_prompt")
        temperature = get_guild_temperature(self.guild_id)
        max_tokens = get_guild_max_tokens(self.guild_id)
        debug_enabled = is_debug_enabled(self.guild_id)
        debug_level = get_debug_level(self.guild_id)
        search_enabled = is_search_enabled(self.guild_id)
        
        prompt_display = (
            "Default"
            if not system_prompt
            else f"Custom ({len(system_prompt)} chars)"
        )
        max_tokens_display = "unlimited" if max_tokens == -1 else str(max_tokens)
        
        embed = discord.Embed(
            title="⚙️ Bot Configuration",
            description="Click the buttons below to configure settings",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🧠 System Prompt",
            value=prompt_display,
            inline=True
        )
        embed.add_field(
            name="🌡️ Temperature",
            value=str(temperature),
            inline=True
        )
        embed.add_field(
            name="📊 Max Tokens",
            value=max_tokens_display,
            inline=True
        )
        embed.add_field(
            name="🔍 Web Search",
            value="Enabled" if search_enabled else "Disabled",
            inline=True
        )
        embed.add_field(
            name="🐞 Debug Mode",
            value=f"{'ON' if debug_enabled else 'OFF'} (level: {debug_level.upper()})",
            inline=True
        )
        
        embed.set_footer(text="⚠️ Admin permissions required to make changes")
        
        return embed
    
    @discord.ui.button(label="Edit System Prompt", style=discord.ButtonStyle.primary, emoji="🧠")
    async def edit_prompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = get_guild_setting(self.guild_id, "system_prompt")
        modal = SystemPromptModal(self.guild_id, current)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Adjust Temperature", style=discord.ButtonStyle.primary, emoji="🌡️")
    async def adjust_temp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = get_guild_temperature(self.guild_id)
        modal = TemperatureModal(self.guild_id, current)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Max Tokens", style=discord.ButtonStyle.primary, emoji="📊")
    async def set_tokens(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = get_guild_max_tokens(self.guild_id)
        modal = MaxTokensModal(self.guild_id, current)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Debug: OFF", style=discord.ButtonStyle.secondary, emoji="🐞", row=1)
    async def toggle_debug(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = is_debug_enabled(self.guild_id)
        new_state = not current
        
        set_guild_setting(self.guild_id, "debug", new_state)
        self.update_toggle_buttons()

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        
        logger.info(f"Debug logging {'enabled' if new_state else 'disabled'} for guild {self.guild_id}")
    
    @discord.ui.button(label="Web Search: ON", style=discord.ButtonStyle.success, emoji="🔍", row=1)
    async def toggle_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = is_search_enabled(self.guild_id)
        new_state = not current
        
        set_guild_setting(self.guild_id, "search_enabled", new_state)
        self.update_toggle_buttons()
        
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        
        logger.info(f"Web search {'enabled' if new_state else 'disabled'} for guild {self.guild_id}")
    
    @discord.ui.button(label="Set Debug Level", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def set_debug_level(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify settings.", ephemeral=True
            )
            return
        
        current = get_debug_level(self.guild_id)
        modal = DebugLevelModal(self.guild_id, current)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Clear Last Message", style=discord.ButtonStyle.danger, emoji="🧹", row=2)
    async def clear_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can clear conversation history.", ephemeral=True
            )
            return
        
        conversation_id = interaction.channel_id
        history = get_conversation_history(conversation_id)
        
        if not history:
            await interaction.response.send_message(
                "ℹ️ No conversation history to clear.",
                ephemeral=True
            )
            return
        
        # Remove last assistant + user messages
        removed = 0
        while history and removed < 2:
            if history[-1]["role"] in {"assistant", "user"}:
                history.pop()
                removed += 1
            else:
                break
        
        await interaction.response.send_message(
            "🧹 Last interaction removed from conversation history.",
            ephemeral=True
        )
        logger.info(f"Cleared last interaction in channel {interaction.channel_id}")
    
    @discord.ui.button(label="Clear All History", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def clear_all_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can clear conversation history.", ephemeral=True
            )
            return
        
        conversation_id = interaction.channel_id
        history = get_conversation_history(conversation_id)
        
        if not history:
            await interaction.response.send_message(
                "ℹ️ No conversation history to clear.",
                ephemeral=True
            )
            return
        
        clear_conversation_history(conversation_id)
        await interaction.response.send_message(
            f"🗑️ Cleared entire conversation history ({len(history)} messages).",
            ephemeral=True
        )
        logger.info(f"Cleared all conversation history in channel {interaction.channel_id}")
    
    @discord.ui.button(label="Reset to Defaults", style=discord.ButtonStyle.danger, emoji="🔄", row=3)
    async def reset_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can reset settings.", ephemeral=True
            )
            return
        
        # Clear all custom settings
        delete_guild_setting(self.guild_id, "system_prompt")
        delete_guild_setting(self.guild_id, "temperature")
        delete_guild_setting(self.guild_id, "max_tokens")
        delete_guild_setting(self.guild_id, "debug")
        delete_guild_setting(self.guild_id, "debug_level")
        
        self.update_toggle_buttons()
        embed = self.create_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(
            "✅ All settings reset to defaults.",
            ephemeral=True
        )
        logger.info(f"Settings reset to defaults for guild {self.guild_id}")


def setup_config_command(tree: app_commands.CommandTree):
    """
    Register config command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name="config", description="Configure bot settings for this server")
    async def config(interaction: discord.Interaction):
        """Open the configuration panel."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Configuration is only available in servers.",
                ephemeral=True
            )
            return
        
        view = ConfigView(interaction.guild.id)
        embed = view.create_embed()
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
        logger.info(f"Config panel opened by {interaction.user} in guild {interaction.guild.id}")