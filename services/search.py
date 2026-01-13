"""
Web search service using DuckDuckGo.
Provides search functionality with cooldown management.
"""
import logging
import time
from typing import Optional, Dict

from ddgs import DDGS

from config import (
    SEARCH_TRIGGERS,
    NEGATIVE_SEARCH_TRIGGERS,
    MIN_MESSAGE_LENGTH_FOR_SEARCH,
    MAX_SEARCH_RESULTS,
    SEARCH_COOLDOWN
)

logger = logging.getLogger(__name__)

# Track search cooldowns per guild
search_cooldowns: Dict[int, float] = {}


async def get_web_context(query: str, max_results: int = MAX_SEARCH_RESULTS) -> str:
    """
    Fetch search snippets from DuckDuckGo.
    
    Args:
        query: Search query
        max_results: Maximum number of results to fetch
        
    Returns:
        Formatted search results string, or empty string if failed
    """
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            if not results:
                logger.warning(f"No search results for: {query}")
                return ""
            
            context = "\n".join([
                f"Source: {r['href']}\nContent: {r['body']}" 
                for r in results
            ])
            return f"\n--- WEB SEARCH RESULTS ---\n{context}\n--------------------------\n"
            
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}", exc_info=True)
        return ""


def should_trigger_search(message_text: str) -> bool:
    """
    Determine if a message should trigger a web search.
    
    Args:
        message_text: User's message text
        
    Returns:
        True if search should be triggered
    """
    # Check message length
    if len(message_text) < MIN_MESSAGE_LENGTH_FOR_SEARCH:
        return False
    
    message_lower = message_text.lower()
    
    # Check for search triggers
    has_search_trigger = any(trigger in message_lower for trigger in SEARCH_TRIGGERS)
    
    # Check if user is referencing a local file/document
    is_referencing_file = any(neg in message_lower for neg in NEGATIVE_SEARCH_TRIGGERS)
    
    # Only search if triggered AND NOT talking about an attachment
    return has_search_trigger and not is_referencing_file


def check_search_cooldown(guild_id: Optional[int]) -> Optional[int]:
    """
    Check if search is on cooldown for a guild.
    
    Args:
        guild_id: Guild ID to check (None for DMs)
        
    Returns:
        Remaining cooldown seconds, or None if not on cooldown
    """
    if not guild_id:
        return None  # No cooldown for DMs
    
    last_search = search_cooldowns.get(guild_id, 0)
    time_since_search = time.time() - last_search
    
    if time_since_search < SEARCH_COOLDOWN:
        remaining = int(SEARCH_COOLDOWN - time_since_search)
        return remaining
    
    return None


def update_search_cooldown(guild_id: Optional[int]) -> None:
    """
    Update the search cooldown timestamp for a guild.
    
    Args:
        guild_id: Guild ID (None for DMs)
    """
    if guild_id:
        search_cooldowns[guild_id] = time.time()
        logger.info(f"Search cooldown updated for guild {guild_id}")