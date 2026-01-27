"""
Status/Health check command.
Handles /status command to show system health and connectivity.
"""
import discord
from discord import app_commands
import logging
import aiohttp
import time
import psutil
import sys
from datetime import datetime, timedelta

from config.constants import CPU_MEASUREMENT_INTERVAL
from config.settings import LMSTUDIO_URL, ALLTALK_URL, ENABLE_TTS, ENABLE_MOSHI, MOSHI_URL, ENABLE_COMFYUI, COMFYUI_URL
from services.lmstudio import fetch_available_models
from services.moshi import is_moshi_available
from commands.model import default_model, get_selected_model
from utils.stats_manager import channel_stats, conversation_histories
from utils.settings_manager import get_settings_manager

logger = logging.getLogger(__name__)


async def check_lmstudio_health() -> tuple[bool, str, float]:
    """
    Check LMStudio API connectivity and response time.
    
    Returns:
        Tuple of (is_healthy, status_message, response_time_ms)
    """
    start_time = time.time()
    try:
        base_url = (
            LMSTUDIO_URL.split('/v1/')[0]
            if '/v1/' in LMSTUDIO_URL
            else LMSTUDIO_URL.rsplit('/', 1)[0]
        )
        
        models_url = f"{base_url}/api/v1/models"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(models_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    loaded_count = sum(1 for m in models if m.get("loaded_instances"))
                    
                    return True, f"Connected ({loaded_count} model(s) loaded)", response_time
                else:
                    return False, f"HTTP {response.status}", response_time
                    
    except aiohttp.ClientError as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Connection failed: {type(e).__name__}", response_time
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Error: {str(e)[:50]}", response_time


async def check_alltalk_health() -> tuple[bool, str, float]:
    """
    Check AllTalk TTS API connectivity and response time.

    Returns:
        Tuple of (is_healthy, status_message, response_time_ms)
    """
    if not ENABLE_TTS:
        return True, "Disabled (globally)", 0.0

    start_time = time.time()
    try:
        # Try to access the status endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ALLTALK_URL}/api/ready", timeout=aiohttp.ClientTimeout(total=5)) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == 200:
                    return True, "Connected", response_time
                else:
                    return False, f"HTTP {response.status}", response_time

    except aiohttp.ClientError as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Connection failed: {type(e).__name__}", response_time
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Error: {str(e)[:50]}", response_time


async def check_moshi_health() -> tuple[bool, str, float]:
    """
    Check Moshi AI Voice service connectivity and response time.

    Returns:
        Tuple of (is_healthy, status_message, response_time_ms)
    """
    if not ENABLE_MOSHI:
        return True, "Disabled (globally)", 0.0

    start_time = time.time()
    try:
        is_available = await is_moshi_available()
        response_time = (time.time() - start_time) * 1000

        if is_available:
            return True, "Connected", response_time
        else:
            return False, "Service unavailable", response_time

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Error: {str(e)[:50]}", response_time


async def check_comfyui_health() -> tuple[bool, str, float]:
    """
    Check ComfyUI API connectivity and response time.

    Returns:
        Tuple of (is_healthy, status_message, response_time_ms)
    """
    if not ENABLE_COMFYUI:
        return True, "Disabled (globally)", 0.0

    start_time = time.time()
    try:
        # Try to access the queue endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{COMFYUI_URL}/queue", timeout=aiohttp.ClientTimeout(total=5)) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == 200:
                    return True, "Connected", response_time
                else:
                    return False, f"HTTP {response.status}", response_time

    except aiohttp.ClientError as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Connection failed: {type(e).__name__}", response_time
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return False, f"Error: {str(e)[:50]}", response_time


def get_system_stats() -> dict:
    """
    Get system resource usage statistics.
    
    Returns:
        Dictionary with CPU, memory, and uptime info
    """
    try:
        process = psutil.Process()
        
        # Get memory info
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # Get CPU usage (over 1 second interval)
        cpu_percent = process.cpu_percent(interval=CPU_MEASUREMENT_INTERVAL)
        
        # Get uptime
        create_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - create_time
        
        return {
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "uptime": uptime,
            "threads": process.num_threads(),
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {
            "memory_mb": 0,
            "cpu_percent": 0,
            "uptime": timedelta(0),
            "threads": 0,
        }


def get_bot_stats() -> dict:
    """
    Get bot-specific statistics.
    
    Returns:
        Dictionary with conversation and usage stats
    """
    total_messages = sum(stats.get("total_messages", 0) for stats in channel_stats.values())
    total_conversations = len(conversation_histories)
    active_conversations = sum(1 for hist in conversation_histories.values() if len(hist) > 0)
    
    # Count total tool usage
    total_searches = sum(stats.get("tool_usage", {}).get("web_search", 0) for stats in channel_stats.values())
    total_url_fetches = sum(stats.get("tool_usage", {}).get("url_fetch", 0) for stats in channel_stats.values())
    total_images = sum(stats.get("tool_usage", {}).get("image_analysis", 0) for stats in channel_stats.values())
    total_pdfs = sum(stats.get("tool_usage", {}).get("pdf_read", 0) for stats in channel_stats.values())
    total_tts = sum(stats.get("tool_usage", {}).get("tts_voice", 0) for stats in channel_stats.values())
    total_comfyui = sum(stats.get("tool_usage", {}).get("comfyui_generation", 0) for stats in channel_stats.values())

    return {
        "total_messages": total_messages,
        "total_conversations": total_conversations,
        "active_conversations": active_conversations,
        "tool_usage": {
            "web_search": total_searches,
            "url_fetch": total_url_fetches,
            "image_analysis": total_images,
            "pdf_read": total_pdfs,
            "tts_voice": total_tts,
            "comfyui_generation": total_comfyui,
        }
    }


def format_uptime(uptime: timedelta) -> str:
    """Format uptime as human-readable string."""
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


def setup_status_command(tree: app_commands.CommandTree):
    """
    Register status command with the bot's command tree.
    
    Args:
        tree: Discord command tree to register commands with
    """
    
    @tree.command(name="status", description="Show bot health and system status")
    async def status_command(interaction: discord.Interaction):
        """Display comprehensive bot status and health check."""
        await interaction.response.defer(ephemeral=True)

        # Determine current guild
        guild_id = interaction.guild.id if interaction.guild else None

        # Get guild-specific settings
        settings_manager = get_settings_manager()
        tts_enabled_for_guild = settings_manager.is_tts_enabled(guild_id)
        comfyui_enabled_for_guild = settings_manager.is_comfyui_enabled(guild_id)

        # Check service health
        lm_healthy, lm_status, lm_time = await check_lmstudio_health()
        tt_healthy, tt_status, tt_time = await check_alltalk_health()
        mo_healthy, mo_status, mo_time = await check_moshi_health()
        cf_healthy, cf_status, cf_time = await check_comfyui_health()

        # Fetch fresh model list
        current_models = await fetch_available_models()

        # Get system stats
        sys_stats = get_system_stats()
        bot_stats = get_bot_stats()

        # Determine current model for this guild
        current_model = get_selected_model(guild_id)
        
        # Create status embed
        # Only consider services that are enabled for this guild
        services_to_check = [lm_healthy]
        if tts_enabled_for_guild:
            services_to_check.append(tt_healthy)
        if ENABLE_MOSHI:
            services_to_check.append(mo_healthy)
        if comfyui_enabled_for_guild:
            services_to_check.append(cf_healthy)

        all_healthy = all(services_to_check)
        embed = discord.Embed(
            title="🤖 Bot Status & Health Check",
            color=discord.Color.green() if all_healthy else discord.Color.orange(),
            timestamp=datetime.now()
        )

        # Service Status
        lm_emoji = "✅" if lm_healthy else "❌"
        tt_emoji = "✅" if tt_healthy else "❌"
        mo_emoji = "✅" if mo_healthy else "❌"
        cf_emoji = "✅" if cf_healthy else "❌"

        services_value = (
            f"{lm_emoji} **LMStudio**: {lm_status}\n"
            f"└ Response: {lm_time:.0f}ms\n"
            f"└ URL: `{LMSTUDIO_URL}`"
        )

        # Only add AllTalk if enabled for this guild
        if tts_enabled_for_guild:
            services_value += (
                f"\n{tt_emoji} **AllTalk TTS**: {tt_status}\n"
                f"└ Response: {tt_time:.0f}ms\n"
                f"└ URL: `{ALLTALK_URL}`"
            )

        # Only add Moshi if enabled globally
        if ENABLE_MOSHI:
            services_value += (
                f"\n{mo_emoji} **Moshi AI Voice**: {mo_status}\n"
                f"└ Response: {mo_time:.0f}ms\n"
                f"└ URL: `{MOSHI_URL}`"
            )

        # Only add ComfyUI if enabled for this guild
        if comfyui_enabled_for_guild:
            services_value += (
                f"\n{cf_emoji} **ComfyUI**: {cf_status}\n"
                f"└ Response: {cf_time:.0f}ms\n"
                f"└ URL: `http://{COMFYUI_URL}`"
            )

        embed.add_field(
            name="🔧 Services",
            value=services_value,
            inline=False
        )
        
        # Model Info
        model_info = (
            f"**Current Model**: {current_model}\n"
            f"**Available Models**: {len(current_models)}\n"
        )
        if current_models:
            models_list = ", ".join(current_models[:3])
            if len(current_models) > 3:
                models_list += f", +{len(current_models) - 3} more"
            model_info += f"└ {models_list}"
        else:
            model_info += f"└ ⚠️ No models loaded in LMStudio"
        
        embed.add_field(
            name="🧠 AI Models",
            value=model_info,
            inline=False
        )
        
        # System Resources
        embed.add_field(
            name="💻 System Resources",
            value=(
                f"**Memory**: {sys_stats['memory_mb']:.1f} MB\n"
                f"**CPU**: {sys_stats['cpu_percent']:.1f}%\n"
                f"**Threads**: {sys_stats['threads']}\n"
                f"**Uptime**: {format_uptime(sys_stats['uptime'])}\n"
                f"**Python**: {sys.version.split()[0]}"
            ),
            inline=True
        )
        
        # Bot Statistics
        bot_stats_value = (
            f"**Total Messages**: {bot_stats['total_messages']:,}\n"
            f"**Conversations**: {bot_stats['active_conversations']}/{bot_stats['total_conversations']}\n"
            f"**Web Searches**: {bot_stats['tool_usage']['web_search']:,}\n"
            f"**Images Analyzed**: {bot_stats['tool_usage']['image_analysis']:,}\n"
            f"**PDFs Read**: {bot_stats['tool_usage']['pdf_read']:,}"
        )

        # Add ComfyUI stats if enabled for this guild
        if comfyui_enabled_for_guild:
            bot_stats_value += f"\n**Images Generated**: {bot_stats['tool_usage']['comfyui_generation']:,}"

        embed.add_field(
            name="📊 Bot Statistics",
            value=bot_stats_value,
            inline=True
        )
        
        # Overall health indicator
        if all_healthy:
            health_msg = "🟢 All systems operational"
        elif lm_healthy:
            degraded_services = []
            if not tt_healthy and tts_enabled_for_guild:
                degraded_services.append("TTS")
            if not mo_healthy and ENABLE_MOSHI:
                degraded_services.append("Moshi")
            if not cf_healthy and comfyui_enabled_for_guild:
                degraded_services.append("ComfyUI")
            if degraded_services:
                health_msg = f"🟡 LMStudio operational, {', '.join(degraded_services)} degraded"
            else:
                health_msg = "🟢 All systems operational"
        else:
            health_msg = "🔴 Critical services unavailable"
        
        embed.set_footer(text=health_msg)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Status command executed by {interaction.user.name} in {interaction.guild.name if interaction.guild else 'DM'}")