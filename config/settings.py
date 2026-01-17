"""
Configuration settings loaded from environment variables.
All environment variable parsing and validation happens here.
"""
import os
import logging
from dotenv import load_dotenv

# Initialize logger for settings module
logger = logging.getLogger(__name__)

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

# REQUIRED: database name
DB_FILE=synapse_bot.db

# Logging and Debug Settings
DEBUG=true
DEBUG_LEVEL=info # options: info, debug

# Permission system (optional but recommended)
# Bot owner user IDs (comma-separated Discord user IDs)
BOT_OWNER_IDS=123456789012345678,987654321098765432
# Default bot admin role name
BOT_ADMIN_ROLE_NAME=Bot Admin

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

# Voice/TTS Settings (optional)
ENABLE_TTS=false
ALLTALK_URL=http://127.0.0.1:7851
ALLTALK_VOICE=alloy

# ComfyUI Settings (optional)
ENABLE_COMFYUI=false
COMFYUI_URL=127.0.0.1:8188
COMFYUI_WORKFLOW='workflow_flux_api.json'
COMFYUI_PROMPT_NODES=6
COMFYUI_RAND_SEED_NODES=36
COMFYUI_TRIGGERS=imagine,generate
"""
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(default_env_content)
        logger.info(f"Created default .env file at {env_file_path}")
        logger.info("Please edit the .env file and add your DISCORD_BOT_TOKEN")
        # Reload after creating the file
        load_dotenv()

# Ensure .env exists before loading settings
ensure_env_file()

# ============================================================================
# DISCORD CONFIGURATION
# ============================================================================

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your-discord-bot-token-here')

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DB_FILE = os.getenv('DB_FILE', 'synapse_bot.db')

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

ENABLE_TTS = os.getenv('ENABLE_TTS', 'false').lower() == 'true'
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


# ============================================================================
# COMFYUI SETTINGS
# ============================================================================

ENABLE_COMFYUI = os.getenv('ENABLE_COMFYUI', 'false').lower() == 'true'
COMFYUI_URL = os.getenv('COMFYUI_URL', '127.0.0.1:8188')
COMFYUI_WORKFLOW = os.getenv('COMFYUI_WORKFLOW', 'workflow_flux_api.json')
COMFYUI_PROMPT_NODES = [str(x.strip()) for x in os.getenv('COMFYUI_PROMPT_NODES', '6').split(',') if x.strip()]
COMFYUI_RAND_SEED_NODES = [str(x.strip()) for x in os.getenv('COMFYUI_RAND_SEED_NODES', '36').split(',') if x.strip()]
COMFYUI_TRIGGERS = [x.strip().lower() for x in os.getenv('COMFYUI_TRIGGERS', 'imagine,generate').split(',') if x.strip()]

# ============================================================================
# LOGGING/DEBUG SETTINGS
# ============================================================================

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
DEBUG_LEVEL = os.getenv('DEBUG_LEVEL', 'info').lower()  # 'info' or 'debug'
