"""
Constants used throughout the application.
These are hardcoded values that don't come from environment variables.
"""

# ============================================================================
# TTS VOICES
# ============================================================================

# OpenAI-compatible voice names for AllTalk TTS
AVAILABLE_VOICES = ['alloy', 'echo', 'fable', 'nova', 'onyx', 'shimmer']

# Voice descriptions for user selection
VOICE_DESCRIPTIONS = {
    'alloy': 'Neutral and balanced',
    'echo': 'Clear and expressive',
    'fable': 'Warm and engaging',
    'nova': 'Energetic and bright',
    'onyx': 'Deep and authoritative',
    'shimmer': 'Soft and soothing'
}

# ============================================================================
# WEB SEARCH CONFIGURATION
# ============================================================================

# Triggers that indicate a web search might be needed
SEARCH_TRIGGERS = [
    "search for", 
    "look up", 
    "find information", 
    "current news", 
    "latest", 
    "what's happening",
    "what is happening",
    "who's currently",
    "who is currently", 
    "weather in",
    "temperature in",
    "today's",
    "who is the current", 
    "recent", 
    "breaking news"
]

# Negative triggers that indicate user is referring to local content
NEGATIVE_SEARCH_TRIGGERS = [
    "this document", 
    "this file", 
    "this pdf", 
    "attached", 
    "the content", 
    "summarize this", 
    "a document"
]

# Minimum message length to trigger automatic search
MIN_MESSAGE_LENGTH_FOR_SEARCH = 12

# Maximum number of search results to fetch
MAX_SEARCH_RESULTS = 5

# ============================================================================
# FILE PROCESSING
# ============================================================================

# Supported text file extensions
TEXT_FILE_EXTENSIONS = [
    '.txt', '.md', '.py', '.js', '.java', '.c', '.cpp', '.h', 
    '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.csv', 
    '.log', '.sh', '.bat', '.ps1', '.sql', '.r', '.php', '.go', 
    '.rs', '.swift', '.kt'
]

# File encoding attempts (in order)
FILE_ENCODINGS = ['utf-8', 'latin-1', 'cp1252']

# Maximum characters to extract from PDF files
MAX_PDF_CHARS = 40000

# Maximum characters to extract from URLs
MAX_URL_CHARS = 60000


# ============================================================================
# DEFAULTS
# ============================================================================

# Default system prompt if none is set
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."

# Default temperature for LLM
DEFAULT_TEMPERATURE = 0.7

# Default max tokens (-1 means unlimited)
DEFAULT_MAX_TOKENS = -1

# Default model identifier
DEFAULT_MODEL = "local-model"

# Maximum number of response times to keep in memory
MAX_RESPONSE_TIMES = 100