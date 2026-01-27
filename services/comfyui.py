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
        await message.channel.send(
            content=final_message,
            file=discord.File(fp=collage_path, filename='generated_image.png')
        )

        # Track successful image generation in stats
        update_stats(conversation_id, tool_used="comfyui_generation", guild_id=guild_id)

        guild_debug_log(guild_id, "info", "Successfully sent generated image to channel")

    except Exception as e:
        logger.error(f"Error generating image with ComfyUI: {e}", exc_info=True)
        guild_debug_log(guild_id, "error", f"ComfyUI generation failed: {e}")
        try:
            await message.channel.send(
                f"{message.author.mention} ❌ Failed to generate image: {str(e)}"
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")


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
