"""
Services package initialization.
Exports all service functions for easy importing.
"""

# LMStudio service
from .lmstudio import (
    fetch_available_models,
    build_api_messages,
    stream_completion,
)

# TTS service
from .tts import (
    text_to_speech,
    get_voice_description,
    is_valid_voice,
)

# Search service
from .search import (
    get_web_context,
    should_trigger_search,
    check_search_cooldown,
    update_search_cooldown,
    search_cooldowns,
)

# Content fetching service
from .content_fetch import (
    fetch_url_content,
    process_message_urls,
)

# File processing service
from .file_processor import (
    process_image_attachment,
    process_text_attachment,
    process_pdf_attachment,
    process_all_attachments,
)

__all__ = [
    # LMStudio
    'fetch_available_models',
    'build_api_messages',
    'stream_completion',
    
    # TTS
    'text_to_speech',
    'get_voice_description',
    'is_valid_voice',
    
    # Search
    'get_web_context',
    'should_trigger_search',
    'check_search_cooldown',
    'update_search_cooldown',
    'search_cooldowns',
    
    # Content fetch
    'fetch_url_content',
    'process_message_urls',
    
    # File processing
    'process_image_attachment',
    'process_text_attachment',
    'process_pdf_attachment',
    'process_all_attachments',
]