"""
Text processing utilities.
Handles token estimation, thinking tag removal, and text cleaning.
"""
import re
import logging
from typing import Union, List, Dict, Any
from config.settings import HIDE_THINKING
from config.constants import CHARS_PER_TOKEN, DISCORD_MESSAGE_LIMIT

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cache for tiktoken encoding
_encoding_cache = None

def _get_encoding():
    """
    Get or create cached tiktoken encoding instance.
    Uses cl100k_base encoding (GPT-4, GPT-3.5-turbo compatible).

    Returns:
        tiktoken.Encoding instance or None if tiktoken unavailable
    """
    global _encoding_cache

    if not TIKTOKEN_AVAILABLE:
        return None

    if _encoding_cache is None:
        try:
            # cl100k_base is used by GPT-4 and GPT-3.5-turbo
            # This is a good default for most modern LLMs
            _encoding_cache = tiktoken.get_encoding("cl100k_base")
            logger.info("Initialized tiktoken with cl100k_base encoding")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken: {e}. Falling back to character-based estimation.")
            return None

    return _encoding_cache


def estimate_tokens(text: Union[str, List, Dict]) -> int:
    """
    Accurate token counting using tiktoken library with fallback.

    This function now uses tiktoken for accurate token counting, which is
    important for:
    - Statistics tracking (knowing actual token usage)
    - Context window management (avoiding overflow)
    - Cost estimation (for paid APIs)

    Args:
        text: Input text string, or message structure (list/dict)

    Returns:
        Estimated number of tokens
    """
    # Convert complex structures to string
    if isinstance(text, (list, dict)):
        text = str(text)

    if not isinstance(text, str):
        logger.warning(f"estimate_tokens received unexpected type: {type(text)}")
        return 0

    # Try tiktoken first for accurate counting
    encoding = _get_encoding()
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception as e:
            logger.debug(f"tiktoken encoding failed: {e}. Using fallback method.")

    # Fallback to character-based estimation
    return len(text) // CHARS_PER_TOKEN


def count_message_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    Count tokens in a list of chat messages with proper formatting overhead.

    This accounts for the additional tokens used by the chat format structure
    (role labels, delimiters, etc.) which are typically 3-4 tokens per message.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys

    Returns:
        Total token count including format overhead
    """
    encoding = _get_encoding()

    if encoding is None:
        # Fallback: simple character-based estimation
        total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
        # Add overhead: ~3 tokens per message for role/format
        return (total_chars // CHARS_PER_TOKEN) + (len(messages) * 3)

    total_tokens = 0

    try:
        for message in messages:
            # Count tokens in content
            content = message.get('content', '')

            # Handle complex content (images, etc.)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get('type') == 'text':
                            total_tokens += len(encoding.encode(item.get('text', '')))
                        elif item.get('type') == 'image_url':
                            # Images use a fixed token count (varies by detail level)
                            # High detail: ~765 tokens, Low detail: ~85 tokens
                            # Default to high detail estimate
                            total_tokens += 765
                    elif isinstance(item, str):
                        total_tokens += len(encoding.encode(item))
            elif isinstance(content, str):
                total_tokens += len(encoding.encode(content))

            # Count tokens in role (usually 1-2 tokens)
            role = message.get('role', '')
            if role:
                total_tokens += len(encoding.encode(role))

            # Add overhead for message formatting (delimiters, structure)
            # OpenAI format adds ~3-4 tokens per message
            total_tokens += 3

        # Add conversation overhead
        # Each conversation has a fixed overhead of ~3 tokens
        total_tokens += 3

    except Exception as e:
        logger.warning(f"Error counting message tokens: {e}. Using fallback.")
        total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
        return (total_chars // CHARS_PER_TOKEN) + (len(messages) * 3)

    return total_tokens


def remove_thinking_tags(text: str) -> str:
    """
    Remove thinking tags and box markers from reasoning model outputs.
    
    This removes:
    - <think>...</think> tags
    - [THINK]...[/THINK] tags
    - <think /> self-closing tags
    - <|begin_of_box|> and <|end_of_box|> markers
    
    Args:
        text: Input text with potential thinking tags
        
    Returns:
        Cleaned text with thinking tags removed
    """
    if not HIDE_THINKING:
        return text
    
    # Remove standard tags
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'\[THINK\].*?\[/THINK\]', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<think\s*/>|\[THINK\s*/\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<\|begin_of_box\|>|<\|end_of_box\|>', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up whitespace: remove triple newlines and leading/trailing gaps
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def is_inside_thinking_tags(text: str) -> bool:
    """
    Check if we're currently inside an unclosed thinking tag.
    
    This is useful for streaming responses to determine if we should
    hide partial output while the model is still "thinking".
    
    Args:
        text: Text to check for unclosed tags
        
    Returns:
        True if there are unclosed thinking tags
    """
    if not HIDE_THINKING:
        return False
    
    open_tags = len(re.findall(r'<think>', text, flags=re.IGNORECASE))
    close_tags = len(re.findall(r'</think>', text, flags=re.IGNORECASE))
    open_brackets = len(re.findall(r'\[THINK\]', text, flags=re.IGNORECASE))
    close_brackets = len(re.findall(r'\[/THINK\]', text, flags=re.IGNORECASE))
    
    return (open_tags > close_tags) or (open_brackets > close_brackets)


def truncate_text(text: str, max_chars: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum number of characters, adding a suffix.
    
    Args:
        text: Text to truncate
        max_chars: Maximum number of characters
        suffix: Suffix to add if truncated (default: "...")
        
    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


def extract_urls(text: str) -> list[str]:
    """
    Extract URLs from text using regex pattern.
    
    Args:
        text: Text to search for URLs
        
    Returns:
        List of found URLs
    """
    url_pattern = r'https?://(?:[^\s()<>]+|(?:\([^\s()<>]*\)))+(?:(?:\([^\s()<>]*\))|[^\s`!()\[\]{};:\'".,<>?Â«Â»""''])'
    return re.findall(url_pattern, text)


def clean_discord_content(text: str) -> str:
    """
    Clean Discord-specific formatting from text.
    Removes mentions, emojis, and other Discord markup.
    
    Args:
        text: Discord message content
        
    Returns:
        Cleaned text
    """
    # Remove user mentions
    text = re.sub(r'<@!?\d+>', '', text)
    # Remove role mentions
    text = re.sub(r'<@&\d+>', '', text)
    # Remove channel mentions
    text = re.sub(r'<#\d+>', '', text)
    # Remove custom emojis
    text = re.sub(r'<a?:\w+:\d+>', '', text)
    
    return text.strip()


def split_message(text: str, max_length: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """
    Split a long message into chunks that fit Discord's message limit.
    
    Args:
        text: Text to split
        max_length: Maximum length per chunk (default: Discord's 2000 char limit)
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit, save current chunk
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If single paragraph is too long, split by sentences
            if len(paragraph) > max_length:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + '. '
                    else:
                        current_chunk += sentence + '. '
            else:
                current_chunk = paragraph + '\n\n'
        else:
            current_chunk += paragraph + '\n\n'
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks