"""
Model selection command.
Handles /model command for switching AI models.
"""
import discord
from discord import app_commands
from typing import Dict, List, Optional
import logging

from services.lmstudio import fetch_available_models
from config.constants import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# Store available models and selected model per guild
available_models: List[str] = []
default_model: str = DEFAULT_MODEL
selected_models: Dict[int, str] = {}


def is_guild_admin(interaction: discord.Interaction) -> bool:
    """Check if the user has admin permissions in the guild."""
    if not interaction.guild or not interaction.user:
        return False
    return interaction.user.guild_permissions.administrator


class ModelSelectView(discord.ui.View):
    """View with dropdown for model selection."""
    def __init__(self, current_model: str):
        super().__init__(timeout=60)
        self.add_item(ModelSelectDropdown(current_model))


class ModelSelectDropdown(discord.ui.Select):
    """Dropdown menu for selecting AI model."""
    def __init__(self, current_model: str):
        if not available_models:
            options = [discord.SelectOption(label="No models available", value="none")]
        else:
            options = [
                discord.SelectOption(
                    label=model,
                    value=model,
                    default=(model == current_model)
                )
                for model in available_models[:25]  # Discord limit
            ]
        
        super().__init__(
            placeholder="Select a model...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "❌ No models available.", 
                ephemeral=True
            )
            return
        
        selected_model = self.values[0]
        guild_id = interaction.guild.id
        selected_models[guild_id] = selected_model
        
        await interaction.response.send_message(
            f"✅ Model changed to: **{selected_model}**",
            ephemeral=True
        )
        logger.info(f"Model changed to '{selected_model}' in guild {guild_id} ({interaction.guild.name})")


def setup_model_command(tree: app_commands.CommandTree):
    """
    Register model command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name='model', description='Select AI model (Admin only)')
    async def select_model(interaction: discord.Interaction):
        """Show dropdown to select AI model."""
        # Check admin permissions
        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can change the model.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Refresh available models
        global available_models, default_model
        models = await fetch_available_models()
        
        if models:
            available_models = models
            if not default_model or default_model == "local-model":
                default_model = models[0]
        
        if not available_models:
            await interaction.followup.send(
                "❌ No models found in LMStudio. Please load a model first.",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        current_model = selected_models.get(guild_id, default_model)
        
        model_list = "\n".join(f"• {model}" for model in available_models)
        
        view = ModelSelectView(current_model)
        await interaction.followup.send(
            f"**Current model:** {current_model}\n\n"
            f"**Available models:**\n{model_list}\n\n"
            f"Select a new model:",
            view=view,
            ephemeral=True
        )


def get_selected_model(guild_id: Optional[int]) -> str:
    """
    Get the selected model for a guild.
    
    Args:
        guild_id: Guild ID (None for DMs)
        
    Returns:
        Model identifier
    """
    if guild_id is None:
        # For DMs, use default model
        model = default_model
        logger.debug(f"Using default model for DM: {model}")
        return model
    
    model = selected_models.get(guild_id, default_model)
    if guild_id not in selected_models:
        logger.debug(f"No model selected for guild {guild_id}, using default: {model}")
    else:
        logger.debug(f"Using selected model for guild {guild_id}: {model}")
    
    return model


async def initialize_models() -> bool:
    """
    Initialize available models from LMStudio.
    
    Returns:
        True if models were successfully loaded, False otherwise
    """
    global available_models, default_model
    
    models = await fetch_available_models()
    if models:
        available_models = models
        default_model = models[0]
        logger.info(f'✅ Loaded {len(models)} model(s) from LMStudio')
        logger.info(f'Default model set to: {default_model}')
        return True
    else:
        logger.error('❌ No models found in LMStudio. Please load a model.')
        return False