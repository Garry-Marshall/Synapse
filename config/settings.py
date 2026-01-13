"""
Configuration settings loaded from environment variables.
All environment variable parsing and validation happens here.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check if .env file exists, if not create one with defaults
def ensure_env_file():
    """Create .env file with default values if it doesn't exist."""
    env_file_path = ".env"
    if not os.path.exists(env_file_path):
        default_env_content = """# Discord Bot Configuration
# Fill in your bot token and channel IDs below

# REQUIRED: Your Discord bot token from https://discord.com/developers/applications
DISCORD_BOT_TOKEN=your-discord-bot-token-here

# REQUIRED: Comma-separated list of channel IDs where the bot should listen
# Enable Developer Mode in Discord, right-click channels, and select "Copy ID"
DISCORD_CHANNEL_IDS=

# LMStudio API Configuration
LMSTUDIO_URL=http://localhost:1234/v1/chat/completions

# Conversation Settings
MAX_HISTORY_MESSAGES=10
CONTEXT_MESSAGES=5

# Bot Behavior
IGNORE_BOTS=true
ALLOW_DMS=true

# Image Support
ALLOW_IMAGES=true
MAX_IMAGE_SIZE=5

# Text File Support
ALLOW_TEXT_FILES=true
MAX_TEXT_FILE_SIZE=2

# PDF Support
ALLOW_PDF=true
MAX_PDF_SIZE=10

# Reasoning Model Settings
HIDE_THINKING=true

# Voice/TTS Settings
ENABLE_TTS=true
ALLTALK_URL=http://127.0.0.1:7851
ALLTALK_VOICE=alloy
"""
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(default_env_content)
        print(f"Created default .env file at {env_file_path}")
        print("Please edit the .env file and add your DISCORD_BOT_TOKEN and DISCORD_CHANNEL_IDS")
        print("")
        # Reload after creating the file
        load_dotenv()

# Ensure .env exists before loading settings
ensure_env_file()

# ============================================================================
# DISCORD CONFIGURATION
# ============================================================================

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your-discord-bot-token-here')

# Parse channel IDs from comma-separated string
CHANNEL_IDS_STR = os.getenv('DISCORD_CHANNEL_IDS', '0')
CHANNEL_IDS = set()
if CHANNEL_IDS_STR and CHANNEL_IDS_STR != '0':
    try:
        CHANNEL_IDS = set(int(cid.strip()) for cid in CHANNEL_IDS_STR.split(',') if cid.strip())
    except ValueError:
        print("ERROR: DISCORD_CHANNEL_IDS must be comma-separated numbers")
        CHANNEL_IDS = set()

# ============================================================================
# LMSTUDIO API CONFIGURATION
# ============================================================================

LMSTUDIO_URL = os.getenv('LMSTUDIO_URL', 'http://localhost:1234/v1/chat/completions')

# ============================================================================
# CONVERSATION SETTINGS
# ============================================================================

MAX_HISTORY = int(os.getenv('MAX_HISTORY_MESSAGES', '10'))
CONTEXT_MESSAGES = int(os.getenv('CONTEXT_MESSAGES', '5'))

# ============================================================================
# BOT BEHAVIOR
# ============================================================================

IGNORE_BOTS = os.getenv('IGNORE_BOTS', 'true').lower() == 'true'
ALLOW_DMS = os.getenv('ALLOW_DMS', 'true').lower() == 'true'

# ============================================================================
# FILE PROCESSING SETTINGS
# ============================================================================

# Image support
ALLOW_IMAGES = os.getenv('ALLOW_IMAGES', 'true').lower() == 'true'
MAX_IMAGE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', '5'))  # in MB

# Text file support
ALLOW_TEXT_FILES = os.getenv('ALLOW_TEXT_FILES', 'true').lower() == 'true'
MAX_TEXT_FILE_SIZE = int(os.getenv('MAX_TEXT_FILE_SIZE', '2'))  # in MB

# PDF support
ALLOW_PDF = os.getenv('ALLOW_PDF', 'true').lower() == 'true'
MAX_PDF_SIZE = int(os.getenv('MAX_PDF_SIZE', '10'))  # in MB

# ============================================================================
# MODEL SETTINGS
# ============================================================================

HIDE_THINKING = os.getenv('HIDE_THINKING', 'true').lower() == 'true'

# ============================================================================
# TTS (TEXT-TO-SPEECH) SETTINGS
# ============================================================================

ENABLE_TTS = os.getenv('ENABLE_TTS', 'true').lower() == 'true'
ALLTALK_URL = os.getenv('ALLTALK_URL', 'http://127.0.0.1:7851')
ALLTALK_VOICE = os.getenv('ALLTALK_VOICE', 'alloy')

# ============================================================================
# FILE PATHS
# ============================================================================

STATS_FILE = "channel_stats.json"
GUILD_SETTINGS_FILE = "guild_settings.json"
LOG_DIR = "Logs"

# ============================================================================
# SEARCH SETTINGS
# ============================================================================

SEARCH_COOLDOWN = 10  # seconds between searches per guild