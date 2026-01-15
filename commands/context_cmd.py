"""
Context window analysis command.
Handles /context command to show token usage and context limits.

IMAGE TOKEN ESTIMATION:
Vision models typically process images using a tile-based approach:
1. OpenAI's system: Divide into 512×512 tiles
2. Cost = 85 base tokens + (num_tiles × 170 tokens per tile)

Examples:
- 1920×1080 image → ~1920×1080 → 4×2 = 8 tiles → 85 + 1,360 = 1,445 tokens
- 4080×3072 image → ~3072×2048 → 6×4 = 24 tiles → 85 + 4080 = 4165 tokens
- Small 800×600 → ~800×600 → 2×2 = 4 tiles → 85 + 680 = 765 tokens

we use a CONSERVATIVE estimate of 24 tiles (4165 tokens) for all images.
This overestimates for small images but prevents underestimating large ones.
"""
import discord
from discord import app_commands
import logging
import aiohttp

from config.settings import LMSTUDIO_URL
from config.constants import DEFAULT_SYSTEM_PROMPT
from commands.model import get_selected_model
from utils.settings_manager import get_guild_setting
from utils.stats_manager import get_conversation_history
from utils.text_utils import estimate_tokens

logger = logging.getLogger(__name__)


async def fetch_model_context_limit(model_name: str) -> tuple[int, int, str]:
    """
    Fetch the actual context limit for a model from LMStudio API.
    
    Args:
        model_name: Model identifier
        
    Returns:
        Tuple of (max_context_length, loaded_context_length, detection_method)
        detection_method is one of: "lmstudio_api", "estimated", "unknown"
    """
    try:
        base_url = (
            LMSTUDIO_URL.split('/v1/')[0]
            if '/v1/' in LMSTUDIO_URL
            else LMSTUDIO_URL.rsplit('/', 1)[0]
        )
        
        # Query the model-specific endpoint
        model_url = f"{base_url}/api/v0/models/{model_name}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(model_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    max_ctx = data.get("max_context_length", 0)
                    loaded_ctx = data.get("loaded_context_length", 0)
                    
                    if loaded_ctx > 0:
                        return max_ctx, loaded_ctx, "lmstudio_api"
                    elif max_ctx > 0:
                        return max_ctx, max_ctx, "lmstudio_api"
                    
                logger.warning(f"Model API returned no context info: {data}")
                
    except Exception as e:
        logger.warning(f"Failed to fetch model context from API: {e}")
    
    # Fallback: estimate based on common model sizes
    common_sizes = {
        "4k": 4096,
        "8k": 8192,
        "16k": 16384,
        "32k": 32768,
        "64k": 65536,
        "128k": 131072,
        "200k": 200000,
    }
    
    model_lower = model_name.lower()
    for size_name, size_tokens in sorted(common_sizes.items(), reverse=True):
        if size_name in model_lower:
            return size_tokens, size_tokens, "estimated"
    
    # Default fallback to 4K
    return 4096, 4096, "unknown"


def format_token_count(tokens: int) -> str:
    """Format token count with K suffix for readability."""
    if tokens >= 1000:
        return f"{tokens / 1000:.1f}K"
    return str(tokens)


def create_progress_bar(used: int, total: int, width: int = 10) -> str:
    """
    Create a visual progress bar.
    
    Args:
        used: Tokens used
        total: Total tokens available
        width: Width of the bar in characters
        
    Returns:
        Progress bar string with filled/empty blocks
    """
    if total == 0:
        return "░" * width
    
    percentage = min(used / total, 1.0)
    filled = int(percentage * width)
    empty = width - filled
    
    return "█" * filled + "░" * empty


def get_status_message(percentage: float) -> str:
    """Get status message based on context usage percentage."""
    if percentage < 50:
        return "✅ Context usage: Low"
    elif percentage < 70:
        return "✅ Context usage: Moderate"
    elif percentage < 85:
        return "⚠️ Context usage: High"
    elif percentage < 95:
        return "⚠️ Context usage: Very High"
    else:
        return "⚠️ Context usage: Near Capacity"


def calculate_image_tokens(image_data: dict) -> int:
    """
    Calculate tokens for an image using tile-based approach (similar to OpenAI).
    
    Vision models typically:
    1. Resize image to fit within 2048×2048 while maintaining aspect ratio
    2. Divide into 512×512 tiles
    3. Use base tokens + (tiles × tokens_per_tile)
    
    Args:
        image_data: Image data dict from conversation history
        
    Returns:
        Estimated token count for the image
    """
    # Try to extract dimensions from base64 data if available
    # For now, we'll use a conservative high estimate since we can't
    # easily decode base64 images without PIL
    
    # Conservative approach: assume a "typical" high-res image
    # Most screenshots/photos are 1920×1080 to 4080×3072
    # This will overestimate for small images but underestimating is worse
    
    # Assume worst-case: large image that fills 3072×2048 after resize
    # That's 6×4 = 24 tiles maximum
    BASE_TOKENS = 85
    TOKENS_PER_TILE = 170
    
    # For images we can't inspect, assume medium-large size
    # (equivalent to ~3072×2048 = 24 tiles, or ~1920×1080 = 8 tiles)
    # Using 24 tiles as reasonable high estimate
    ESTIMATED_TILES = 24
    
    return BASE_TOKENS + (ESTIMATED_TILES * TOKENS_PER_TILE)


def calculate_conversation_tokens(conversation_id: int, context_limit: int, system_tokens: int) -> dict:
    """
    Calculate token usage breakdown for a conversation.
    Works BACKWARDS from most recent messages (rolling window).
    
    Args:
        conversation_id: Channel or DM ID
        context_limit: Maximum context window size
        system_tokens: Tokens used by system prompt
        
    Returns:
        Dictionary with token counts for each component
    """
    history = get_conversation_history(conversation_id)
    
    breakdown = {
        "text_messages": 0,
        "system_prompts": 0,
        "images": 0,
        "files": 0,
        "total": 0,
        "in_context_messages": 0,
        "out_of_context_messages": 0,
        "total_messages": len(history),
        "image_count": 0
    }
    
    # Calculate available space for conversation (after system prompt)
    available_for_conversation = context_limit - system_tokens
    current_tokens = 0
    
    # Process messages from MOST RECENT to OLDEST (rolling window)
    for msg in reversed(history):
        content = msg.get("content", "")
        msg_tokens = 0
        msg_breakdown = {
            "text": 0,
            "system": 0,
            "images": 0,
            "files": 0
        }
        
        # Handle multimodal content (images)
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    tokens = estimate_tokens(item.get("text", ""))
                    msg_tokens += tokens
                    msg_breakdown["text"] += tokens
                elif item.get("type") == "image_url":
                    # Use proper tile-based calculation
                    image_tokens = calculate_image_tokens(item)
                    msg_tokens += image_tokens
                    msg_breakdown["images"] += image_tokens
        else:
            # Regular text message
            text_content = str(content)
            tokens = estimate_tokens(text_content)
            msg_tokens += tokens
            
            # Check if it's a system message with additional context
            if "WEB SEARCH RESULTS" in text_content or "Content from provided URL" in text_content:
                msg_breakdown["system"] += tokens
            elif "Content of PDF:" in text_content or "Content of" in text_content and "---" in text_content:
                msg_breakdown["files"] += tokens
            else:
                msg_breakdown["text"] += tokens
        
        # Check if this message fits in the context window
        if current_tokens + msg_tokens <= available_for_conversation:
            # Message is IN CONTEXT
            current_tokens += msg_tokens
            breakdown["text_messages"] += msg_breakdown["text"]
            breakdown["system_prompts"] += msg_breakdown["system"]
            breakdown["images"] += msg_breakdown["images"]
            breakdown["files"] += msg_breakdown["files"]
            breakdown["in_context_messages"] += 1
            
            # Count images
            if msg_breakdown["images"] > 0:
                if isinstance(content, list):
                    breakdown["image_count"] += sum(1 for item in content if item.get("type") == "image_url")
        else:
            # Message is OUT OF CONTEXT (will be dropped by LMStudio)
            breakdown["out_of_context_messages"] += 1
    
    breakdown["total"] = current_tokens
    
    return breakdown


def setup_context_command(tree: app_commands.CommandTree):
    """
    Register context command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name="context", description="Show context window usage and limits")
    async def context_command(interaction: discord.Interaction):
        """Display context window analysis with token usage breakdown."""
        await interaction.response.defer(ephemeral=True)
        
        # Get conversation ID
        is_dm = not interaction.guild
        conversation_id = interaction.user.id if is_dm else interaction.channel_id
        guild_id = None if is_dm else interaction.guild.id
        
        # Get current model
        model_name = get_selected_model(guild_id)
        
        # Fetch context limits
        max_ctx, loaded_ctx, detection = await fetch_model_context_limit(model_name)
        
        # Get system prompt
        base_system_prompt = get_guild_setting(guild_id, "system_prompt", DEFAULT_SYSTEM_PROMPT)
        system_tokens = estimate_tokens(base_system_prompt)
        
        # Calculate conversation token usage WITH ROLLING WINDOW
        conv_breakdown = calculate_conversation_tokens(conversation_id, loaded_ctx, system_tokens)
        conv_tokens = conv_breakdown["total"]
        
        # Calculate totals
        total_used = system_tokens + conv_tokens
        available = max(0, loaded_ctx - total_used)
        percentage = (total_used / loaded_ctx * 100) if loaded_ctx > 0 else 0
        
        # Create embed
        embed = discord.Embed(
            title="📊 Context Window Analysis",
            color=discord.Color.blue() if percentage < 70 else discord.Color.orange() if percentage < 85 else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        # Model info
        detection_emoji = "✅" if detection == "lmstudio_api" else "⚠️"
        detection_text = "LMStudio API (exact)" if detection == "lmstudio_api" else f"{detection.title()}"
        
        embed.add_field(
            name="🤖 Model Configuration",
            value=(
                f"**Model**: {model_name}\n"
                f"**Context Limit**: {format_token_count(loaded_ctx)} tokens ({loaded_ctx:,})\n"
                f"**Detection**: {detection_emoji} {detection_text}"
            ),
            inline=False
        )
        
        # Token usage breakdown with progress bars
        system_bar = create_progress_bar(system_tokens, loaded_ctx)
        system_pct = (system_tokens / loaded_ctx * 100) if loaded_ctx > 0 else 0
        
        conv_bar = create_progress_bar(conv_tokens, loaded_ctx)
        conv_pct = (conv_tokens / loaded_ctx * 100) if loaded_ctx > 0 else 0
        
        avail_bar = create_progress_bar(available, loaded_ctx)
        avail_pct = (available / loaded_ctx * 100) if loaded_ctx > 0 else 0
        
        usage_text = (
            f"**System Prompt**: {system_tokens:,} tokens {system_bar} {system_pct:.1f}%\n"
            f"**Conversation**: {conv_tokens:,} tokens {conv_bar} {conv_pct:.1f}%\n"
        )
        
        # Add conversation breakdown if significant
        if conv_breakdown["images"] > 0 or conv_breakdown["files"] > 0 or conv_breakdown["system_prompts"] > 0:
            usage_text += f"  ├─ Text: {conv_breakdown['text_messages']:,} tokens\n"
            if conv_breakdown["images"] > 0:
                avg_per_image = conv_breakdown["images"] // max(conv_breakdown.get("image_count", 1), 1)
                usage_text += f"  ├─ Images: ~{conv_breakdown['images']:,} tokens ({conv_breakdown.get('image_count', 0)} image(s), ~{avg_per_image} each)\n"
            if conv_breakdown["files"] > 0:
                usage_text += f"  ├─ Files: {conv_breakdown['files']:,} tokens\n"
            if conv_breakdown["system_prompts"] > 0:
                usage_text += f"  └─ Context (web/URL): {conv_breakdown['system_prompts']:,} tokens\n"
        
        usage_text += f"**Available**: {available:,} tokens {avail_bar} {avail_pct:.1f}%"
        
        embed.add_field(
            name="📈 Token Usage",
            value=usage_text,
            inline=False
        )
        
        # Summary with rolling window info
        status_msg = get_status_message(percentage)
        
        summary_text = f"**Total Used**: {total_used:,} / {loaded_ctx:,} tokens ({percentage:.1f}% full)\n"
        
        # Add rolling window info if messages are being dropped
        if conv_breakdown["out_of_context_messages"] > 0:
            summary_text += (
                f"ℹ️ **Rolling Window**: {conv_breakdown['out_of_context_messages']} older message(s) "
                f"outside context window (automatically handled by LMStudio)\n"
            )
        
        summary_text += status_msg
        
        embed.add_field(
            name="📊 Summary",
            value=summary_text,
            inline=False
        )
        
        # Add footer with message count
        footer_text = (
            f"{conv_breakdown['in_context_messages']} messages in context"
        )
        if conv_breakdown["out_of_context_messages"] > 0:
            footer_text += f" • {conv_breakdown['out_of_context_messages']} outside"
        footer_text += f" • {conv_breakdown['total_messages']} total stored"
        
        embed.set_footer(text=footer_text)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(
            f"Context command used by {interaction.user.name} | "
            f"Model: {model_name} | Usage: {percentage:.1f}% ({total_used:,}/{loaded_ctx:,}) | "
            f"Out-of-context: {conv_breakdown['out_of_context_messages']}"
        )