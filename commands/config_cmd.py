"""
Configuration command.
Handles /config command for server settings.
"""
import discord
from discord import app_commands
from typing import Optional
import logging

from config import CONFIG_CATEGORIES
from utils import (
    guild_settings,
    get_guild_setting,
    set_guild_setting,
    delete_guild_setting,
    get_guild_temperature,
    get_guild_max_tokens,
    get_conversation_history,
    save_guild_settings
)

logger = logging.getLogger(__name__)


def is_guild_admin(interaction: discord.Interaction) -> bool:
    """Check if the user has admin permissions in the guild."""
    if not interaction.guild or not interaction.user:
        return False
    return interaction.user.guild_permissions.administrator


async def autocomplete_config_category(
    interaction: discord.Interaction,
    current: str
):
    """Autocomplete for config categories."""
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in CONFIG_CATEGORIES.keys()
        if cat.startswith(current.lower())
    ]


async def autocomplete_config_action(
    interaction: discord.Interaction,
    current: str
):
    """Autocomplete for config actions."""
    category = interaction.namespace.category
    if not category:
        return []

    actions = CONFIG_CATEGORIES.get(category.lower(), [])

    return [
        app_commands.Choice(name=action, value=action)
        for action in actions
        if action.startswith(current.lower())
    ]


def setup_config_command(tree: app_commands.CommandTree):
    """
    Register config command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name="config", description="Configure bot settings for this server")
    @app_commands.autocomplete(
        category=autocomplete_config_category,
        action=autocomplete_config_action,
    )
    async def config(
        interaction: discord.Interaction,
        category: str,
        action: Optional[str] = None,
        value: Optional[str] = None
    ):
        """Main config command handler."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Configuration is only available in servers.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        # SEARCH CONFIG
        if category.lower() == "search":
            if action.lower() == "show":
                enabled = get_guild_setting(guild_id, "search_enabled", True)
                await interaction.response.send_message(
                    f"🔍 Web search is **{'ENABLED' if enabled else 'DISABLED'}**",
                    ephemeral=True
                )
                return
            
            if not is_guild_admin(interaction):
                await interaction.response.send_message(
                    "❌ Only admins can change search settings.",
                    ephemeral=True
                )
                return
            
            if action.lower() in {"on", "off"}:
                enabled = action.lower() == "on"
                set_guild_setting(guild_id, "search_enabled", enabled)
                await interaction.response.send_message(
                    f"✅ Web search turned **{'ON' if enabled else 'OFF'}**.",
                    ephemeral=True
                )
                return

        # SHOW ALL CONFIG
        if category.lower() == "show" and (action is None or action.lower() == "show"):
            cfg = guild_settings.get(guild_id, {})

            system_prompt = cfg.get("system_prompt")
            temperature = cfg.get("temperature", 0.7)
            max_tokens = cfg.get("max_tokens", -1)
            debug_enabled = cfg.get("debug", False)
            debug_level = cfg.get("debug_level", "info")

            prompt_display = (
                "Default"
                if not system_prompt
                else f"Custom ({len(system_prompt)} chars)"
            )

            max_tokens_display = (
                "unlimited" if max_tokens == -1 else str(max_tokens)
            )

            message = (
                "🛠 **Server configuration**\n"
                f"🧠 System prompt: **{prompt_display}**\n"
                f"🌡️ Temperature: **{temperature}**\n"
                f"📝 Max tokens: **{max_tokens_display}**\n"
                f"🐞 Debug: **{'ON' if debug_enabled else 'OFF'}** "
                f"(level: **{debug_level.upper()}**)"
            )

            await interaction.response.send_message(message, ephemeral=True)
            return

        # SYSTEM PROMPT
        if category.lower() == "system":
            if action.lower() == "show":
                current = get_guild_setting(guild_id, "system_prompt")
                if current:
                    await interaction.response.send_message(
                        f"🧠 **System prompt:**\n```{current}```",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "ℹ️ No system prompt set.",
                        ephemeral=True
                    )
                return

            if not is_guild_admin(interaction):
                await interaction.response.send_message(
                    "❌ Only admins can modify the system prompt.",
                    ephemeral=True
                )
                return

            if action.lower() == "clear":
                delete_guild_setting(guild_id, "system_prompt")
                await interaction.response.send_message(
                    "✅ System prompt cleared.",
                    ephemeral=True
                )
                return

            if action.lower() == "set":
                if not value or not value.strip():
                    await interaction.response.send_message(
                        "❌ Please provide a system prompt.",
                        ephemeral=True
                    )
                    return

                set_guild_setting(guild_id, "system_prompt", value.strip())
                await interaction.response.send_message(
                    "✅ System prompt updated.",
                    ephemeral=True
                )
                return

        # TEMPERATURE
        if category.lower() == "temperature":
            if action.lower() == "show":
                temp = get_guild_temperature(guild_id)
                await interaction.response.send_message(
                    f"🌡️ Current temperature: **{temp}**",
                    ephemeral=True
                )
                return

            if not is_guild_admin(interaction):
                await interaction.response.send_message(
                    "❌ Only admins can change temperature.",
                    ephemeral=True
                )
                return

            if action.lower() == "reset":
                delete_guild_setting(guild_id, "temperature")
                await interaction.response.send_message(
                    "✅ Temperature reset to default (0.7).",
                    ephemeral=True
                )
                return

            if action.lower() == "set":
                try:
                    temp = float(value)
                    if not 0.0 <= temp <= 2.0:
                        raise ValueError
                except Exception:
                    await interaction.response.send_message(
                        "❌ Temperature must be a number between 0.0 and 2.0.",
                        ephemeral=True
                    )
                    return

                set_guild_setting(guild_id, "temperature", temp)
                await interaction.response.send_message(
                    f"✅ Temperature set to **{temp}**.",
                    ephemeral=True
                )
                return

        # MAX TOKENS
        if category.lower() == "max_tokens":
            if action.lower() == "show":
                current = get_guild_max_tokens(guild_id)
                display = "unlimited" if current == -1 else str(current)
                await interaction.response.send_message(
                    f"📝 Current max_tokens: **{display}**",
                    ephemeral=True
                )
                return

            if not is_guild_admin(interaction):
                await interaction.response.send_message(
                    "❌ Only admins can change max_tokens.",
                    ephemeral=True
                )
                return

            if action.lower() == "reset":
                delete_guild_setting(guild_id, "max_tokens")
                await interaction.response.send_message(
                    "✅ max_tokens reset to unlimited.",
                    ephemeral=True
                )
                return

            if action.lower() == "set":
                try:
                    value_int = int(value)
                    if value_int <= 0 and value_int != -1:
                        raise ValueError
                except Exception:
                    await interaction.response.send_message(
                        "❌ max_tokens must be a positive integer or `-1` (unlimited).",
                        ephemeral=True
                    )
                    return

                set_guild_setting(guild_id, "max_tokens", value_int)
                display = "unlimited" if value_int == -1 else str(value_int)
                await interaction.response.send_message(
                    f"✅ max_tokens set to **{display}**.",
                    ephemeral=True
                )
                return

        # CLEAR LAST
        if category.lower() == "clear" and action.lower() == "last":
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
                "🧹 Last interaction removed.",
                ephemeral=True
            )
            logger.info(f"Cleared last interaction in channel {interaction.channel_id}")
            return

        # DEBUG LOGGING
        if category.lower() == "debug":
            if action.lower() == "show":
                from utils import is_debug_enabled, get_debug_level
                enabled = is_debug_enabled(guild_id, guild_settings)
                level = get_debug_level(guild_id, guild_settings)
                await interaction.response.send_message(
                    f"🐞 Debug logging is **{'ON' if enabled else 'OFF'}** "
                    f"(level: **{level.upper()}**).",
                    ephemeral=True
                )
                return

            if not is_guild_admin(interaction):
                await interaction.response.send_message(
                    "❌ Only admins can change debug logging.",
                    ephemeral=True
                )
                return

            if action.lower() in {"on", "off"}:
                enabled = action.lower() == "on"
                set_guild_setting(guild_id, "debug", enabled)
                await interaction.response.send_message(
                    f"✅ Debug logging turned **{'ON' if enabled else 'OFF'}**.",
                    ephemeral=True
                )
                logger.info(f"Debug logging {'enabled' if enabled else 'disabled'} for guild {guild_id}")
                return

            if action.lower() == "level":
                if value not in {"info", "debug"}:
                    await interaction.response.send_message(
                        "❌ Usage: `/config debug level info` or `/config debug level debug`",
                        ephemeral=True
                    )
                    return

                set_guild_setting(guild_id, "debug_level", value)
                await interaction.response.send_message(
                    f"✅ Debug log level set to **{value.upper()}**.",
                    ephemeral=True
                )
                logger.info(f"Debug log level set to {value} for guild {guild_id}")
                return

        # FALLBACK
        await interaction.response.send_message(
            "❌ Invalid config command.\n\n"
            "**Usage examples:**\n"
            "`/config system show`\n"
            "`/config system set <prompt>`\n"
            "`/config temperature set 0.3`\n"
            "`/config clear last`",
            ephemeral=True
        )