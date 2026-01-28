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
    # Existing ones...
    "search for", "look up", "find information", 'find info on',
    "current news", "current weather", "latest", 
    "what's happening", "what is happening",
    "who's currently", "who is currently", 
    "weather in", "temperature in", "today's",
    "who is the current", "who's the current",
    "recent", "breaking news", "weather forecast",
    
    # Price/cost queries
    "how much does", "how much is", "price of", "cost of",
    "how expensive", "how cheap",
    
    # Location queries
    "where is", "where can i find", "where to",
    
    # Time-sensitive queries
    "when will", "when does", "schedule for",
    
    # Stock/financial (very time-sensitive)
    "stock price", "exchange rate", "crypto price",
    
    # Real-time status
    "currently happening",
    
    # Updates/changes
    "update on", "updates about", "changes to", "new version",
    
    # Statistics/data
    "statistics", "data on", "numbers for",
]

# Negative triggers that indicate user is referring to local content
NEGATIVE_SEARCH_TRIGGERS = [
    # File references
    "this document", "this file", "this pdf", 
    "attached", "the content", "summarize this", "a document",
    "in the image", "in the picture", "in this attachment",
    "in the pdf", "in this text", "in the code", "in this file",
    
    # Context references
    "you just", "you said", "you mentioned", "earlier you",
    "above message", "previous message", "your last",
    
    # Analysis of provided content
    "analyze this", "explain this", "review this",
    "what does this", "tell me about this",
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

# Days to keep conversation history before considering it inactive
INACTIVITY_THRESHOLD_DAYS = 30

# Constants for rate limiting
MAX_MESSAGE_EDITS_PER_WINDOW = 4  # Discord allows 5, use 4 to be safe
MESSAGE_EDIT_WINDOW = 5.0  # seconds

# ============================================================================
# TOKEN ESTIMATION
# ============================================================================

# Rough character-to-token ratio (1 token ≈ 4 characters)
CHARS_PER_TOKEN = 4

# ============================================================================
# API TIMEOUTS AND LIMITS
# ============================================================================

# HTTP timeout for external API calls (seconds)
DEFAULT_HTTP_TIMEOUT = 5
LMSTUDIO_TIMEOUT = 10
TTS_TIMEOUT = 60

# Discord UI interaction timeout
DISCORD_VIEW_TIMEOUT = 60
DISCORD_CONFIG_VIEW_TIMEOUT = 300  # 5 minutes

# Maximum models to show in Discord dropdown (Discord limitation)
DISCORD_SELECT_MAX_OPTIONS = 25

# ============================================================================
# LMSTUDIO TIMEOUTS AND LIMITS
# ============================================================================

LMSTUDIO_MAX_RETRIES = 3
LMSTUDIO_INITIAL_RETRY_DELAY = 1.0  # seconds
LMSTUDIO_MAX_RETRY_DELAY = 10.0  # seconds
LMSTUDIO_RETRY_BACKOFF_MULTIPLIER = 2.0

# ============================================================================
# MESSAGE PROCESSING
# ============================================================================

# Message update interval for streaming responses (seconds)
STREAM_UPDATE_INTERVAL = 1.5

# Discord message length limits
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_SAFE_DISPLAY_LIMIT = 1900  # Leave buffer for "..."

# System prompt truncation limits
MAX_SYSTEM_PROMPT_LENGTH = 10000  # For validation
MAX_SYSTEM_PROMPT_CONTEXT = 60000  # Total context including search results
SYSTEM_PROMPT_TRUNCATE_TO = 59900
SYSTEM_PROMPT_SAFE_TRUNCATE = 50000  # Safe paragraph boundary search

# ============================================================================
# HISTORY MANAGEMENT
# ============================================================================

# Multiplier for API message history limit
HISTORY_MULTIPLIER = 2

# ============================================================================
# LOGGING
# ============================================================================

# Log file rotation settings
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# ============================================================================
# COOLDOWNS AND CLEANUP
# ============================================================================

# Search cooldown cleanup threshold (seconds)
SEARCH_COOLDOWN_CLEANUP = 3600  # 1 hour

# ============================================================================
# RATE LIMITING CONFIGURATION
# ============================================================================

# Rate limits for web search (per-user and per-guild)
SEARCH_RATE_LIMIT_USER_PER_MINUTE = 3
SEARCH_RATE_LIMIT_USER_PER_HOUR = 20
SEARCH_RATE_LIMIT_USER_COOLDOWN = 20  # seconds

SEARCH_RATE_LIMIT_GUILD_PER_MINUTE = 10
SEARCH_RATE_LIMIT_GUILD_PER_HOUR = 100
SEARCH_RATE_LIMIT_GUILD_COOLDOWN = 10  # seconds

# Rate limits for system prompt changes
MAX_PROMPT_CHANGES_PER_HOUR = 5

# CPU measurement interval for system stats (seconds)
CPU_MEASUREMENT_INTERVAL = 0.1

# ============================================================================
# FILE SIZE CONVERSION
# ============================================================================

BYTES_PER_MB = 1024 * 1024

# ============================================================================
# USER AGENT
# ============================================================================

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
)

# ============================================================================
# TEMPERATURE BOUNDS
# ============================================================================

MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0

# ============================================================================
# IMAGE TOKEN ESTIMATION (Vision Models)
# ============================================================================

# Vision models use tile-based processing (e.g., OpenAI's approach)
# Images are divided into 512×512 tiles after resizing to fit 2048×2048
IMAGE_BASE_TOKENS = 85
TOKENS_PER_IMAGE_TILE = 170

# Conservative estimate: assume large images (e.g., 3072×2048 = 24 tiles)
IMAGE_ESTIMATED_TILES = 24
IMAGE_DEFAULT_TOKEN_ESTIMATE = IMAGE_BASE_TOKENS + (IMAGE_ESTIMATED_TILES * TOKENS_PER_IMAGE_TILE)


# ============================================================================
# STATS AND SETTINGS SAVE INTERVALS
# ============================================================================

# Inactivity threshold for cleanup (days)
INACTIVITY_THRESHOLD_DAYS = 30

# Interval for periodic saving of stats/settings (seconds)
SAVE_INTERVAL = 300

# ============================================================================
# USER-FACING MESSAGES
# ============================================================================

# Status messages
MSG_THINKING = "🤔 Thinking..."
MSG_PROCESSING_ATTACHMENTS = "🔎 Processing attachments..."
MSG_LOADING_CONTEXT = "📚 Loading conversation context..."
MSG_SEARCHING_WEB = "🔍 Searching the web..."
MSG_FETCHING_URL = "🌐 Fetching URL content..."
MSG_BUILDING_CONTEXT = "🧠 Building context..."
MSG_WRITING_RESPONSE = "✍️ Writing response..."

# Error messages
MSG_DM_NOT_ENABLED = "❌ DM conversations are not enabled."
MSG_ADMIN_ONLY = "❌ Only admins can modify settings."
MSG_SERVER_ONLY = "❌ This command only works in servers, not DMs."
MSG_TTS_DISABLED_GLOBAL = "❌ TTS is currently disabled globally in the bot configuration."
MSG_TTS_DISABLED_SERVER = "❌ TTS is disabled for this server. An admin can enable it using '/config'."
MSG_NEED_VOICE_CHANNEL = "❌ You need to be in a voice channel first!"
MSG_NOT_IN_VOICE = "❌ I'm not in a voice channel!"
MSG_CONFIG_ONLY_SERVERS = "❌ Configuration is only available in servers."
MSG_ALREADY_IN_VOICE = "✅ Already in your voice channel!"
MSG_NO_MODELS_AVAILABLE = "❌ No models found in LMStudio. Please load a model first."
MSG_FAILED_TO_JOIN_VOICE = "❌ Failed to join voice channel: {channel}"
MSG_FAILED_TO_PROCESS_IMAGE = "❌ Failed to process image **{attachment}**: {exception}"
MSG_FAILED_TO_PROCESS_FILE = "❌ Failed to process file **{attachment}**: {exception}"
MSG_FAILED_TO_DECODE_FILE = "❌ Could not decode file **{attachment}**. Please ensure it's a valid text file."
MSG_FAILED_TO_PROCESS_PDF = "❌ Failed to process PDF **{attachment}**: {exception}"

# Success messages
MSG_SETTINGS_RESET = "✅ All settings reset to defaults."
MSG_STATS_CLEARED = "✅ Statistics cleared."
MSG_VOICE_CHANGED = "✅ Voice changed to: **{selected_voice}**"
MSG_MODEL_CHANGED = "✅ Model changed to: **{model}**"
MSG_SETTING_UPDATED = "✅ {setting} updated."
MSG_LEFT_VOICE = "✅ Left the voice channel."
MSG_JOINED_VOICE = "✅ Joined {channel}!"
MSG_MOVED_VOICE = "✅ Moved to {channel}!"