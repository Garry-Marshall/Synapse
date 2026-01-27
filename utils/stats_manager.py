"""
Statistics tracking and persistence.
Manages conversation statistics per channel/DM.

UPDATED: Now uses SQLite database instead of JSON files for better reliability.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

from config.settings import MAX_HISTORY
from config.constants import INACTIVITY_THRESHOLD_DAYS

logger = logging.getLogger(__name__)

# Store conversation history per channel/DM (in-memory, not persisted)
conversation_histories: Dict[int, list] = defaultdict(list)

# Track whether context has been loaded for each conversation (in-memory)
context_loaded: Dict[int, bool] = defaultdict(bool)

# Database instance will be initialized on first use
_db = None


def _get_db():
    """Lazy-load database instance."""
    global _db
    if _db is None:
        from utils.database import get_database
        _db = get_database()
    return _db


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
            "comfyui_generation": 0,
        }
    }


def cleanup_old_conversations() -> None:
    """
    Clean up conversation data for channels/users inactive for more than INACTIVITY_THRESHOLD_DAYS.
    Removes old entries from database and clears in-memory conversation histories.
    """
    db = _get_db()
    deleted = db.cleanup_old_conversations(INACTIVITY_THRESHOLD_DAYS)
    
    if deleted > 0:
        # Also clean up in-memory histories for deleted conversations
        deleted_ids = []
        all_conv_ids = set(db.get_all_conversation_ids())
        
        for conv_id in list(conversation_histories.keys()):
            if conv_id not in all_conv_ids:
                deleted_ids.append(conv_id)
        
        for conv_id in deleted_ids:
            if conv_id in conversation_histories:
                del conversation_histories[conv_id]
            if conv_id in context_loaded:
                del context_loaded[conv_id]


def load_stats() -> None:
    """Load statistics from database (compatibility function - now no-op)."""
    # Database is automatically initialized when needed
    logger.info("Stats loading handled by database layer")


def save_stats() -> None:
    """Save statistics to database (compatibility function - now no-op)."""
    # Database auto-commits on each operation
    pass


def save_stats_if_needed(force: bool = False) -> None:
    """
    Save statistics if needed (compatibility function - now no-op).
    
    Args:
        force: Ignored - database auto-commits
    """
    # Database auto-commits, no periodic saving needed
    pass


def get_or_create_stats(conversation_id: int, guild_id: Optional[int] = None) -> dict:
    """
    Get stats for a conversation, creating empty stats if needed.
    
    Args:
        conversation_id: Channel or DM ID
        guild_id: Optional guild ID for new conversations
        
    Returns:
        Statistics dictionary for this conversation
    """
    db = _get_db()
    stats = db.get_conversation(conversation_id)
    
    if not stats:
        # Create new conversation
        db.create_conversation(conversation_id, guild_id)
        stats = db.get_conversation(conversation_id)
    
    return stats


def update_stats(
    conversation_id: int,
    prompt_tokens: int = 0,
    response_tokens_raw: int = 0,
    response_tokens_cleaned: int = 0,
    response_time: float = None,
    failed: bool = False,
    tool_used: str = None,
    guild_id: Optional[int] = None
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
        guild_id: Guild ID (for creating new conversations with proper guild association)
    """
    db = _get_db()
    db.update_conversation(
        conversation_id=conversation_id,
        prompt_tokens=prompt_tokens,
        response_tokens_raw=response_tokens_raw,
        response_tokens_cleaned=response_tokens_cleaned,
        response_time=response_time,
        failed=failed,
        tool_used=tool_used,
        guild_id=guild_id
    )


def reset_stats(conversation_id: int) -> None:
    """
    Reset statistics for a conversation.

    Args:
        conversation_id: Channel or DM ID
    """
    db = _get_db()

    # Delete and recreate
    with db._get_cursor() as cursor:
        cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))

    db.create_conversation(conversation_id)
    logger.info(f"Reset stats for conversation {conversation_id}")


def reset_guild_stats(guild_id: int) -> int:
    """
    Reset all statistics for all conversations in a guild.

    Args:
        guild_id: Guild ID

    Returns:
        Number of conversations reset
    """
    db = _get_db()
    return db.reset_guild_stats(guild_id)


def get_guild_stats_summary(guild_id: int) -> str:
    """
    Get a formatted summary of aggregated statistics for all channels in a guild.

    Args:
        guild_id: Guild ID

    Returns:
        Formatted statistics string for all guild channels
    """
    db = _get_db()
    conversations = db.get_guild_conversations(guild_id)

    if not conversations:
        return "📈 **Guild Statistics**\n\nNo conversations found in this guild."

    # Aggregate stats across all conversations
    total_messages = 0
    total_prompt_tokens = 0
    total_response_tokens_raw = 0
    total_response_tokens_cleaned = 0
    total_failed_requests = 0
    all_response_times = []
    aggregated_tool_usage = {
        "web_search": 0,
        "url_fetch": 0,
        "image_analysis": 0,
        "pdf_read": 0,
        "tts_voice": 0,
        "comfyui_generation": 0,
    }
    earliest_start = None
    latest_message = None

    for stats in conversations:
        total_messages += stats['total_messages']
        total_prompt_tokens += stats['prompt_tokens_estimate']
        total_response_tokens_raw += stats['response_tokens_raw']
        total_response_tokens_cleaned += stats['response_tokens_cleaned']
        total_failed_requests += stats.get('failed_requests', 0)
        all_response_times.extend(stats['response_times'])

        # Aggregate tool usage
        for tool, count in stats['tool_usage'].items():
            if tool in aggregated_tool_usage:
                aggregated_tool_usage[tool] += count

        # Track earliest start time
        if earliest_start is None or stats['start_time'] < earliest_start:
            earliest_start = stats['start_time']

        # Track latest message time
        if stats['last_message_time']:
            if latest_message is None or stats['last_message_time'] > latest_message:
                latest_message = stats['last_message_time']

    # Calculate average response time
    avg_response_time = 0
    if all_response_times:
        avg_response_time = sum(all_response_times) / len(all_response_times)

    # Calculate duration from earliest start to now
    duration = datetime.now() - earliest_start if earliest_start else timedelta(0)
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format last message time
    last_msg = "Never"
    if latest_message:
        last_msg = latest_message.strftime("%Y-%m-%d %H:%M:%S")

    # Tool usage stats
    tool_stats = (
        f"\n\n**Tool Usage (All Channels):**\n"
        f"🔍 Web Searches: {aggregated_tool_usage['web_search']}\n"
        f"🌐 URLs Fetched: {aggregated_tool_usage['url_fetch']}\n"
        f"🖼️ Images Analyzed: {aggregated_tool_usage['image_analysis']}\n"
        f"📄 PDFs Read: {aggregated_tool_usage['pdf_read']}\n"
        f"🔊 Voice Replies: {aggregated_tool_usage['tts_voice']}\n"
        f"🎨 Images Generated: {aggregated_tool_usage['comfyui_generation']}"
    )

    total_tokens = total_prompt_tokens + total_response_tokens_cleaned

    return f"""📈 **Guild Statistics (All Channels)**

**Active Channels:** {len(conversations)}
**Total Messages:** {total_messages}
**Prompt Tokens (est):** {total_prompt_tokens:,}
**Response Tokens (raw):** {total_response_tokens_raw:,}
**Response Tokens (cleaned):** {total_response_tokens_cleaned:,}
**Total Tokens (est):** {total_tokens:,}
**Failed Requests:** {total_failed_requests}

**Oldest Session:** {hours}h {minutes}m {seconds}s
**Average Response Time:** {avg_response_time:.2f}s
**Last Message:** {last_msg}{tool_stats}
"""


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
        f"🔊 Voice Replies: {tool_usage.get('tts_voice', 0)}\n"
        f"🎨 Images Generated: {tool_usage.get('comfyui_generation', 0)}"
    )
    
    total_tokens = stats['prompt_tokens_estimate'] + stats['response_tokens_cleaned']
    
    return f"""📈 **Conversation Statistics**

**Total Messages:** {stats['total_messages']}
**Prompt Tokens (est):** {stats['prompt_tokens_estimate']:,}
**Response Tokens (raw):** {stats['response_tokens_raw']:,}
**Response Tokens (cleaned):** {stats['response_tokens_cleaned']:,}
**Total Tokens (est):** {total_tokens:,}
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
    # Set context_loaded to True to prevent automatic reloading of context messages
    # This ensures the bot starts with a truly empty history after user explicitly clears it
    context_loaded[conversation_id] = True
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


# Backward compatibility - expose a dict-like interface for code that accesses channel_stats directly
class _StatsProxy:
    """Proxy object that provides dict-like access to database stats."""
    
    def __getitem__(self, conversation_id: int) -> dict:
        """Get stats for a conversation."""
        return get_or_create_stats(conversation_id)
    
    def __setitem__(self, conversation_id: int, value: dict) -> None:
        """Not supported - use update_stats() instead."""
        raise NotImplementedError("Direct assignment not supported. Use update_stats() instead.")
    
    def get(self, conversation_id: int, default=None) -> dict:
        """Get stats with default."""
        try:
            return get_or_create_stats(conversation_id)
        except Exception:
            return default if default is not None else create_empty_stats()
    
    def values(self):
        """Get all stats (for iteration)."""
        db = _get_db()
        for conv_id in db.get_all_conversation_ids():
            yield db.get_conversation(conv_id)
    
    def items(self):
        """Get all (id, stats) pairs."""
        db = _get_db()
        for conv_id in db.get_all_conversation_ids():
            yield conv_id, db.get_conversation(conv_id)
    
    def keys(self):
        """Get all conversation IDs."""
        db = _get_db()
        return db.get_all_conversation_ids()


# Create proxy instance for backward compatibility
channel_stats = _StatsProxy()


# Initialize on module import (database will auto-migrate if needed)
_db = _get_db()