"""
Web search service using DDGS (Dux Distributed Global Search).
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


async def get_web_context(
    query: str, 
    max_results: int = MAX_SEARCH_RESULTS,
    region: str = "wt-wt",  # Worldwide
    safesearch: str = "moderate",
    backend: str = "auto"  # Let DDGS choose best backend
) -> str:
    """
    Fetch search snippets from DDGS metasearch.
    
    Args:
        query: Search query
        max_results: Maximum number of results to fetch
        region: Search region (wt-wt for worldwide, us-en, etc.)
        safesearch: Safe search setting (on, moderate, off)
        backend: Search backend(s) to use (auto, duckduckgo, google, bing, etc.)
        
    Returns:
        Formatted search results string, or empty string if failed
    """
    try:
        # Initialize DDGS with timeout and optional proxy
        ddgs = DDGS(timeout=10)  # Increase timeout for reliability
        
        # Perform search with backend selection
        results = ddgs.text(
            query=query,
            region=region,
            safesearch=safesearch,
            max_results=max_results,
            backend=backend
        )
        
        if not results:
            logger.warning(f"No search results for: {query}")
            return ""
        
        # Format results with source attribution
        formatted_results = []
        for i, r in enumerate(results, 1):
            title = r.get('title', 'No title')
            href = r.get('href', 'No URL')
            body = r.get('body', 'No description')
            
            formatted_results.append(
                f"[{i}] {title}\n"
                f"URL: {href}\n"
                f"Summary: {body}\n"
            )
        
        context = "\n".join(formatted_results)
        return f"\n--- WEB SEARCH RESULTS ({len(results)} sources) ---\n{context}--------------------------\n"
            
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}", exc_info=True)
        # Try fallback to DuckDuckGo only if auto fails
        if backend == "auto":
            try:
                logger.info("Retrying search with DuckDuckGo backend only...")
                ddgs = DDGS(timeout=10)
                results = ddgs.text(
                    query=query,
                    region=region,
                    safesearch=safesearch,
                    max_results=max_results,
                    backend="duckduckgo"
                )
                if results:
                    formatted_results = []
                    for i, r in enumerate(results, 1):
                        formatted_results.append(
                            f"[{i}] {r.get('title', 'No title')}\n"
                            f"URL: {r.get('href', 'No URL')}\n"
                            f"Summary: {r.get('body', 'No description')}\n"
                        )
                    context = "\n".join(formatted_results)
                    return f"\n--- WEB SEARCH RESULTS ({len(results)} sources) ---\n{context}--------------------------\n"
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
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