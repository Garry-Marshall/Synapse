"""
URL content fetching service.
Extracts main text content from web pages using Trafilatura.
"""
import logging
import ipaddress
import asyncio
from urllib.parse import urlparse
from functools import partial

import trafilatura
from trafilatura.settings import use_config

from config.constants import MAX_URL_CHARS, DEFAULT_USER_AGENT
from utils.text_utils import extract_urls

logger = logging.getLogger(__name__)

# Timeout for fetching URL content (in seconds)
FETCH_TIMEOUT = 10

# Blocked IP ranges for SSRF protection
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('10.0.0.0/8'),       # Private network
    ipaddress.ip_network('172.16.0.0/12'),    # Private network
    ipaddress.ip_network('192.168.0.0/16'),   # Private network
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
]

# Allowed URL schemes
ALLOWED_SCHEMES = {'http', 'https'}


def _validate_url_safety(url: str) -> tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Parse URL
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed."

        # Check hostname exists
        if not parsed.hostname:
            return False, "Invalid URL: missing hostname"

        # Resolve hostname to IP and check against blocked ranges
        try:
            # Get IP address from hostname
            import socket
            ip_str = socket.gethostbyname(parsed.hostname)
            ip = ipaddress.ip_address(ip_str)

            # Check if IP is in any blocked range
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    logger.warning(f"SSRF attempt blocked: {url} resolves to {ip} in blocked range {blocked_range}")
                    return False, "Access to internal/private network addresses is not allowed"

        except socket.gaierror:
            # DNS resolution failed
            return False, f"Could not resolve hostname: {parsed.hostname}"
        except Exception as e:
            logger.error(f"Error validating IP address: {e}")
            return False, "Error validating URL"

        # URL is safe
        return True, ""

    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        return False, "Invalid URL format"


def _fetch_url_sync(url: str) -> str:
    """
    Synchronous helper to fetch URL content (to be run in executor).

    Args:
        url: URL to fetch

    Returns:
        Downloaded HTML content or empty string
    """
    try:
        # Create a custom config for the User-Agent
        new_config = use_config()
        new_config.set(
            "DEFAULT",
            "USER_AGENT",
            DEFAULT_USER_AGENT
        )

        # Fetch with trafilatura (blocking call)
        downloaded = trafilatura.fetch_url(url, config=new_config)
        return downloaded if downloaded else ""

    except Exception as e:
        logger.error(f"Error in sync fetch for {url}: {e}")
        return ""


async def fetch_url_content(url: str, timeout: int = FETCH_TIMEOUT) -> str:
    """
    Fetch and clean the main text content from a specific URL with SSRF protection and timeout.

    Args:
        url: URL to fetch
        timeout: Timeout in seconds (default: 10)

    Returns:
        Extracted text content, or empty string if failed
    """
    # Validate URL safety first
    is_safe, error_msg = _validate_url_safety(url)
    if not is_safe:
        logger.warning(f"URL rejected for safety: {url} - {error_msg}")
        return f"[URL access blocked: {error_msg}]"

    try:
        # Run the blocking fetch operation in an executor with timeout
        loop = asyncio.get_event_loop()
        fetch_func = partial(_fetch_url_sync, url)

        try:
            downloaded = await asyncio.wait_for(
                loop.run_in_executor(None, fetch_func),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ({timeout}s) fetching URL: {url}")
            return ""

        if not downloaded:
            logger.warning(f"Failed to download content from {url}")
            return ""

        # Extract main text content (this is fast, no need for executor)
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
    logger.info(f"🔗 URL detected. Fetching content from: {target_url}")
    
    url_content = await fetch_url_content(target_url)
    
    if url_content:
        return f"\n[Content from provided URL]:\n{url_content}\n"
    
    return ""