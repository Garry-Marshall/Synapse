"""
ComfyUI image generation service.
Handles creating images using ComfyUI workflows.
"""
import os
import discord
import logging
from PIL import Image
from datetime import datetime
from math import ceil, sqrt

from utils.image_utils import generate_flux_image


logger = logging.getLogger(__name__)

# Ensure output directory exists
OUTPUT_DIR = "./out"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_collage(images):
    """
    Create a collage from multiple images.

    Args:
        images: List of PIL Image objects

    Returns:
        Path to the saved collage image
    """
    # Ensure output directory exists (in case module import happened before directory was ready)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    num_images = len(images)
    num_cols = ceil(sqrt(num_images))
    num_rows = ceil(num_images / num_cols)
    collage_width = max(image.width for image in images) * num_cols
    collage_height = max(image.height for image in images) * num_rows
    collage = Image.new('RGB', (collage_width, collage_height))

    for idx, image in enumerate(images):
        row = idx // num_cols
        col = idx % num_cols
        x_offset = col * image.width
        y_offset = row * image.height
        collage.paste(image, (x_offset, y_offset))

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    collage_path = os.path.join(OUTPUT_DIR, f"images_{timestamp}.png")
    collage.save(collage_path)

    return collage_path


async def generate_and_send_image(message: discord.Message, prompt: str, guild_id: int = None):
    """
    Generate an image using ComfyUI and send it to the channel.

    Args:
        message: Discord message that triggered the generation
        prompt: Text prompt for image generation
        guild_id: Guild ID for logging (None for DMs)
    """
    from utils.logging_config import guild_debug_log
    from utils.stats_manager import update_stats

    # Determine conversation ID
    is_dm = isinstance(message.channel, discord.DMChannel)
    conversation_id = message.author.id if is_dm else message.channel.id

    guild_debug_log(guild_id, "info", f"Starting ComfyUI image generation with prompt: {prompt[:100]}")

    try:
        # Send initial status message
        status_msg = await message.channel.send(
            f"{message.author.mention} is generating an image: \"{prompt}\"\n"
            f"⏳ This may take a minute..."
        )

        # Generate the image
        guild_debug_log(guild_id, "debug", "Calling ComfyUI API for image generation")
        images = await generate_flux_image(prompt, None, message.channel.id)

        if not images:
            guild_debug_log(guild_id, "error", "No images returned from ComfyUI")
            await status_msg.edit(content=f"❌ Failed to generate image. Please try again.")
            return

        guild_debug_log(guild_id, "info", f"Successfully generated {len(images)} image(s)")

        # Create collage and send
        collage_path = create_collage(images)
        final_message = f"{message.author.mention} asked me to imagine: \"{prompt}\""

        await status_msg.delete()
        sent_message = await message.channel.send(
            content=final_message,
            file=discord.File(fp=collage_path, filename='generated_image.png')
        )

        # Track successful image generation in stats
        update_stats(conversation_id, tool_used="comfyui_generation", guild_id=guild_id)

        guild_debug_log(guild_id, "info", "Successfully sent generated image to channel")

        # Automatically analyze the generated image
        guild_debug_log(guild_id, "info", "Auto-analyzing generated image")
        await analyze_generated_image(sent_message, message, guild_id)

    except Exception as e:
        logger.error(f"Error generating image with ComfyUI: {e}", exc_info=True)
        guild_debug_log(guild_id, "error", f"ComfyUI generation failed: {e}")
        try:
            await message.channel.send(
                f"{message.author.mention} ❌ Failed to generate image: {str(e)}"
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")


async def analyze_generated_image(sent_message: discord.Message, original_message: discord.Message, guild_id: int = None):
    """
    Automatically analyze a generated image using the bot's vision capabilities.

    Args:
        sent_message: The message containing the generated image
        original_message: The original message that triggered generation
        guild_id: Guild ID for logging
    """
    from services.file_processor import process_image_attachment
    from services.lmstudio import stream_completion, build_api_messages
    from utils.stats_manager import add_message_to_history, get_conversation_history
    from utils.settings_manager import get_guild_setting, get_guild_temperature, get_guild_max_tokens
    from commands.model import get_selected_model
    from config.constants import DEFAULT_SYSTEM_PROMPT
    from utils.logging_config import guild_debug_log
    from utils.text_utils import remove_thinking_tags

    try:
        # Check if the message has attachments
        if not sent_message.attachments:
            guild_debug_log(guild_id, "warning", "No attachments found in sent message for analysis")
            return

        # Get conversation ID
        is_dm = isinstance(original_message.channel, discord.DMChannel)
        conversation_id = original_message.author.id if is_dm else original_message.channel.id

        # Process the image attachment
        attachment = sent_message.attachments[0]
        guild_debug_log(guild_id, "debug", f"Processing generated image for analysis: {attachment.filename}")

        image_data = await process_image_attachment(attachment, original_message.channel, guild_id)
        if not image_data:
            guild_debug_log(guild_id, "warning", "Failed to process generated image for analysis")
            return

        # Send analysis status
        analysis_msg = await original_message.channel.send("🔍 Analyzing the generated image...")

        # Build the analysis prompt
        analysis_content = [
            {"type": "text", "text": "Describe this image I just generated. What do you see?"},
            image_data
        ]

        # Add to conversation history
        add_message_to_history(conversation_id, "user", analysis_content)

        # Get system prompt and build API messages
        system_prompt = get_guild_setting(guild_id, "system_prompt", DEFAULT_SYSTEM_PROMPT)
        api_messages = build_api_messages(get_conversation_history(conversation_id), system_prompt)

        # Get model settings
        model = get_selected_model(guild_id)
        temperature = get_guild_temperature(guild_id)
        max_tokens = get_guild_max_tokens(guild_id)

        guild_debug_log(guild_id, "info", f"Streaming image analysis with model: {model}")

        # Stream the analysis
        response_text = ""
        async for chunk in stream_completion(api_messages, model, temperature, max_tokens, guild_id):
            response_text += chunk

        # Clean and send response
        final_response = remove_thinking_tags(response_text)
        if final_response.strip():
            await analysis_msg.edit(content=final_response[:2000])  # Discord limit

            # Add to conversation history
            add_message_to_history(conversation_id, "assistant", response_text)

            guild_debug_log(guild_id, "info", "Image analysis completed and sent")
        else:
            await analysis_msg.delete()
            guild_debug_log(guild_id, "warning", "Analysis produced no content")

    except Exception as e:
        logger.error(f"Error analyzing generated image: {e}", exc_info=True)
        guild_debug_log(guild_id, "error", f"Image analysis failed: {e}")


def extract_prompt_from_message(message_content: str, trigger_word: str) -> str:
    """
    Extract the image prompt from a message containing a trigger word.

    Args:
        message_content: The full message content
        trigger_word: The trigger word that was detected

    Returns:
        The extracted prompt text
    """
    # Find the trigger word and extract everything after it
    message_lower = message_content.lower()
    trigger_index = message_lower.find(trigger_word.lower())

    if trigger_index == -1:
        return message_content.strip()

    # Get everything after the trigger word
    prompt = message_content[trigger_index + len(trigger_word):].strip()

    # Remove common punctuation from the start
    while prompt and prompt[0] in [':', ',', '-', '!', '?']:
        prompt = prompt[1:].strip()

    return prompt if prompt else message_content.strip()
