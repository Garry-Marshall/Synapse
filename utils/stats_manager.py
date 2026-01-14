"""
Statistics tracking and persistence.
Manages conversation statistics per channel/DM.
"""
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

from config.settings import STATS_FILE, MAX_HISTORY
from config.constants import MAX_RESPONSE_TIMES

logger = logging.getLogger(__name__)

# Store conversation history per channel/DM
conversation_histories: Dict[int, list] = defaultdict(list)

# Track whether context has been loaded for each conversation
context_loaded: Dict[int, bool] = defaultdict(bool)

# Store statistics per channel/DM
channel_stats: Dict[int, Dict] = {}

# Inactivity threshold for cleanup (30 days)
INACTIVITY_THRESHOLD_DAYS = 30


def create_empty_stats() -> dict:
    """Returns a dictionary with the default structure for a new channel's stats."""
    return {
        "start_time": datetime.now(),
        "total_messages": 0,
        "prompt_tokens_estimate": 0,
        "response_tokens_raw": 0,
        "response_tokens_cleaned": 0,
        "response_times": [],
        "last_message_time": None,
        "failed_requests": 0,
        "tool_usage": {
            "web_search": 0,
            "url_fetch": 0,
            "image_analysis": 0,
            "pdf_read": 0,
            "tts_voice": 0,
        }
    }


def serialize_stats(stats: dict) -> dict:
    """
    Convert stats dictionary to JSON-serializable format.
    
    Args:
        stats: Statistics dictionary with datetime objects
        
    Returns:
        Serializable dictionary
    """
    out = {}
    for cid, data in stats.items():
        out[str(cid)] = {
            **data,
            "start_time": data["start_time"].isoformat(),
            "last_message_time": (
                data["last_message_time"].isoformat()
                if data["last_message_time"] else None
            ),
        }
    return out


def deserialize_stats(data: dict) -> dict:
    """
    Convert JSON data back to stats dictionary with datetime objects.
    
    Args:
        data: Serialized statistics dictionary
        
    Returns:
        Statistics dictionary with datetime objects
    """
    out = {}
    for cid, stats in data.items():
        out[int(cid)] = {
            **stats,
            "start_time": datetime.fromisoformat(stats["start_time"]),
            "last_message_time": (
                datetime.fromisoformat(stats["last_message_time"])
                if stats["last_message_time"] else None
            ),
        }
    return out


def cleanup_old_conversations() -> None:
    """
    Clean up conversation data for channels/users inactive for more than INACTIVITY_THRESHOLD_DAYS.
    Removes old entries from conversation_histories, context_loaded, and channel_stats.
    """
    now = datetime.now()
    threshold = timedelta(days=INACTIVITY_THRESHOLD_DAYS)
    
    # Find inactive conversations
    inactive_ids = []
    for conv_id, stats in channel_stats.items():
        last_message = stats.get("last_message_time")
        if last_message and (now - last_message) > threshold:
            inactive_ids.append(conv_id)
    
    # Clean up
    for conv_id in inactive_ids:
        if conv_id in conversation_histories:
            del conversation_histories[conv_id]
        if conv_id in context_loaded:
            del context_loaded[conv_id]
        if conv_id in channel_stats:
            del channel_stats[conv_id]
    
    if inactive_ids:
        logger.info(f"Cleaned up {len(inactive_ids)} inactive conversations (inactive > {INACTIVITY_THRESHOLD_DAYS} days)")
        save_stats()


def load_stats() -> None:
    """Load statistics from file."""
    global channel_stats
    
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict) and raw:
                    channel_stats = deserialize_stats(raw)
                    logger.info(f"Successfully loaded stats for {len(channel_stats)} channels.")
                else:
                    # File exists but is just [] or "" or similar
                    channel_stats = {}
        except Exception as e:
            logger.warning(f"Stats file was invalid ({e}). Resetting memory.")
            channel_stats = {}
    else:
        logger.info("Stats file not found. A new one will be created.")
        channel_stats = {}
    
    # Ensure a valid file exists on disk right now
    save_stats()


def save_stats() -> None:
    """Save statistics to file."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(serialize_stats(channel_stats), f, indent=2)
    except Exception as e:
        logger.error(f"Could not write stats file: {e}")


def get_or_create_stats(conversation_id: int) -> dict:
    """
    Get stats for a conversation, creating empty stats if needed.
    
    Args:
        conversation_id: Channel or DM ID
        
    Returns:
        Statistics dictionary for this conversation
    """
    if conversation_id not in channel_stats:
        channel_stats[conversation_id] = create_empty_stats()
    else:
        # Ensure tool_usage exists for backward compatibility
        if "tool_usage" not in channel_stats[conversation_id]:
            channel_stats[conversation_id]["tool_usage"] = {
                "web_search": 0,
                "url_fetch": 0,
                "image_analysis": 0,
                "pdf_read": 0,
                "tts_voice": 0,
            }
    
    return channel_stats[conversation_id]


def update_stats(
    conversation_id: int,
    prompt_tokens: int = 0,
    response_tokens_raw: int = 0,
    response_tokens_cleaned: int = 0,
    response_time: float = None,
    failed: bool = False,
    tool_used: str = None
) -> None:
    """
    Update statistics for a conversation.
    
    Args:
        conversation_id: Channel or DM ID
        prompt_tokens: Number of tokens in prompt
        response_tokens_raw: Raw response tokens (before cleaning)
        response_tokens_cleaned: Cleaned response tokens (after removing thinking)
        response_time: Time taken for response in seconds
        failed: Whether the request failed
        tool_used: Name of tool used (web_search, url_fetch, image_analysis, pdf_read, tts_voice)
    """
    stats = get_or_create_stats(conversation_id)
    
    if failed:
        stats["failed_requests"] += 1
    else:
        stats["total_messages"] += 1
        stats["prompt_tokens_estimate"] += prompt_tokens
        stats["response_tokens_raw"] += response_tokens_raw
        stats["response_tokens_cleaned"] += response_tokens_cleaned
        stats["total_tokens_estimate"] = (
            stats["prompt_tokens_estimate"] + stats["response_tokens_cleaned"]
        )
        
        if response_time is not None:
            stats["response_times"].append(response_time)
            # Keep only last MAX_RESPONSE_TIMES entries to prevent unbounded growth
            if len(stats["response_times"]) > MAX_RESPONSE_TIMES:
                stats["response_times"] = stats["response_times"][-MAX_RESPONSE_TIMES:]
        
        stats["last_message_time"] = datetime.now()
    
    # Track tool usage regardless of success/failure
    if tool_used:
        # Ensure tool_usage dict exists
        if "tool_usage" not in stats:
            stats["tool_usage"] = {
                "web_search": 0,
                "url_fetch": 0,
                "image_analysis": 0,
                "pdf_read": 0,
                "tts_voice": 0,
            }
        
        if tool_used in stats["tool_usage"]:
            stats["tool_usage"][tool_used] += 1
    
    save_stats()


def reset_stats(conversation_id: int) -> None:
    """
    Reset statistics for a conversation.
    
    Args:
        conversation_id: Channel or DM ID
    """
    channel_stats[conversation_id] = create_empty_stats()
    save_stats()
    logger.info(f"Reset stats for conversation {conversation_id}")


def get_stats_summary(conversation_id: int) -> str:
    """
    Get a formatted summary of statistics for display.
    
    Args:
        conversation_id: Channel or DM ID
        
    Returns:
        Formatted statistics string
    """
    stats = get_or_create_stats(conversation_id)
    
    avg_response_time = 0
    if stats['response_times']:
        avg_response_time = sum(stats['response_times']) / len(stats['response_times'])
    
    duration = datetime.now() - stats['start_time']
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    last_msg = "Never"
    if stats['last_message_time']:
        last_msg = stats['last_message_time'].strftime("%Y-%m-%d %H:%M:%S")
    
    history_count = len(conversation_histories.get(conversation_id, []))
    
    # Get tool usage stats
    tool_usage = stats.get('tool_usage', {})
    tool_stats = (
        f"\n\n**Tool Usage:**\n"
        f"🔍 Web Searches: {tool_usage.get('web_search', 0)}\n"
        f"🌐 URLs Fetched: {tool_usage.get('url_fetch', 0)}\n"
        f"🖼️ Images Analyzed: {tool_usage.get('image_analysis', 0)}\n"
        f"📄 PDFs Read: {tool_usage.get('pdf_read', 0)}\n"
        f"🔊 Voice Replies: {tool_usage.get('tts_voice', 0)}"
    )
    
    return f"""📈 **Conversation Statistics**

**Total Messages:** {stats['total_messages']}
**Prompt Tokens (est):** {stats['prompt_tokens_estimate']:,}
**Response Tokens (raw):** {stats['response_tokens_raw']:,}
**Response Tokens (cleaned):** {stats['response_tokens_cleaned']:,}
**Total Tokens (est):** {(stats['prompt_tokens_estimate'] + stats['response_tokens_cleaned']):,}
**Failed Requests:** {stats.get('failed_requests', 0)}

**Session Duration:** {hours}h {minutes}m {seconds}s
**Average Response Time:** {avg_response_time:.2f}s
**Last Message:** {last_msg}
**Messages in History:** {history_count}{tool_stats}
"""


def clear_conversation_history(conversation_id: int) -> None:
    """
    Clear conversation history for a channel/DM.
    
    Args:
        conversation_id: Channel or DM ID
    """
    conversation_histories[conversation_id].clear()
    context_loaded[conversation_id] = False
    logger.info(f"Cleared conversation history for {conversation_id}")


def add_message_to_history(conversation_id: int, role: str, content) -> None:
    """
    Add a message to conversation history.
    
    Args:
        conversation_id: Channel or DM ID
        role: Message role ("user" or "assistant")
        content: Message content (string or list for multimodal)
    """
    history = conversation_histories[conversation_id]

    history.append({
        "role": role,
        "content": content
    })

    # Enforce history limit
    if MAX_HISTORY > 0:
        excess = len(history) - MAX_HISTORY
        if excess > 0:
            logger.debug(f"Trimmed {excess} messages from history for {conversation_id}")
            del history[0:excess]


def get_conversation_history(conversation_id: int) -> list:
    """
    Get conversation history for a channel/DM.
    
    Args:
        conversation_id: Channel or DM ID
        
    Returns:
        List of message dictionaries
    """
    return conversation_histories[conversation_id]


def is_context_loaded(conversation_id: int) -> bool:
    """
    Check if context has been loaded for a conversation.
    
    Args:
        conversation_id: Channel or DM ID
        
    Returns:
        True if context has been loaded
    """
    return context_loaded[conversation_id]


def set_context_loaded(conversation_id: int, loaded: bool = True) -> None:
    """
    Set context loaded status for a conversation.
    
    Args:
        conversation_id: Channel or DM ID
        loaded: Whether context has been loaded
    """
    context_loaded[conversation_id] = loaded


# Initialize stats on module import
load_stats()