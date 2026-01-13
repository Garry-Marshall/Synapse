"""
Text processing utilities.
Handles token estimation, thinking tag removal, and text cleaning.
"""
import re
from config import HIDE_THINKING


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of tokens (approximately 4 characters per token).
    
    Args:
        text: Input text string
        
    Returns:
        Estimated number of tokens
    """
    return len(text) // 4


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
    url_pattern = r'https?://(?:[^\s()<>]+|(?:\([^\s()<>]*\)))+(?:(?:\([^\s()<>]*\))|[^\s`!()\[\]{};:\'".,<>?«»""''])'
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


def split_message(text: str, max_length: int = 2000) -> list[str]:
    """
    Split a long message into chunks that fit Discord's message limit.
    
    Args:
        text: Text to split
        max_length: Maximum length per chunk (default: 2000 for Discord)
        
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