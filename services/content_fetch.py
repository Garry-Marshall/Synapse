"""
URL content fetching service.
Extracts main text content from web pages using Trafilatura.
"""
import logging

import trafilatura
from trafilatura.settings import use_config

from config.constants import MAX_URL_CHARS, DEFAULT_USER_AGENT
from utils.text_utils import extract_urls

logger = logging.getLogger(__name__)


async def fetch_url_content(url: str) -> str:
    """
    Fetch and clean the main text content from a specific URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Extracted text content, or empty string if failed
    """
    try:
        # Create a custom config for the User-Agent
        new_config = use_config()
        new_config.set(
            "DEFAULT", 
            "USER_AGENT",
            DEFAULT_USER_AGENT
        )
        
        # Pass the config object
        downloaded = trafilatura.fetch_url(url, config=new_config)
        if not downloaded:
            logger.warning(f"Failed to download content from {url}")
            return ""
        
        # Extract main text content
        content = trafilatura.extract(
            downloaded, 
            include_comments=False, 
            include_tables=True
        )
        
        if not content:
            logger.warning(f"No content extracted from {url}")
            return ""
        
        # Truncate if too long
        if len(content) > MAX_URL_CHARS:
            logger.info(f"URL content truncated from {len(content)} to {MAX_URL_CHARS} characters")
            content = content[:MAX_URL_CHARS]
        else:
            logger.info(f"URL content fully loaded ({len(content)} characters)")
        
        return content
        
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}", exc_info=True)
        return ""


async def process_message_urls(message_text: str) -> str:
    """
    Extract and fetch content from URLs in a message.
    
    Args:
        message_text: Message text potentially containing URLs
        
    Returns:
        Formatted URL content string, or empty if no URLs found
    """
    found_urls = extract_urls(message_text)
    
    if not found_urls:
        return ""
    
    # Focus on the first URL provided
    target_url = found_urls[0]
    logger.info(f"ðŸ”— URL detected. Fetching content from: {target_url}")
    
    url_content = await fetch_url_content(target_url)
    
    if url_content:
        return f"\n[Content from provided URL]:\n{url_content}\n"
    
    return ""