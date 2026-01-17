"""
Logging configuration and setup.
Handles file and console logging with rotation.

Environment Variables:
- DEBUG_LEVEL: Controls logging verbosity
  - 'info': Console and file both show INFO, WARNING, ERROR only
  - 'debug': Console shows INFO+, file shows DEBUG+ (all messages)
- ENABLE_CONVERSATION_LOG: When 'true', creates separate conversation log file (only with DEBUG_LEVEL=debug)
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.settings import LOG_DIR
from config.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT


def setup_logging():
    """
    Configure logging to both file and console based on DEBUG_LEVEL.
    Creates rotating log files in the Logs directory.

    Returns:
        tuple: (main_log_filename, conversation_log_filename or None)
    """
    # Import here to avoid circular dependency
    from config.settings import DEBUG_LEVEL

    # Create log directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)

    # Create log filename with date stamp
    log_filename = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y-%m-%d')}.log")

    # Determine log levels based on DEBUG_LEVEL setting
    if DEBUG_LEVEL == 'debug':
        root_level = logging.DEBUG  # Root captures DEBUG and above
        file_level = logging.DEBUG
        console_level = logging.INFO
    else:  # 'info' or any other value
        root_level = logging.INFO  # Root only captures INFO and above
        file_level = logging.INFO
        console_level = logging.INFO

    # Create file handler
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)  # Set root level based on DEBUG_LEVEL
    root_logger.handlers.clear()  # Clear any existing handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress external library debug messages (even in debug mode)
    _suppress_external_loggers()

    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - DEBUG_LEVEL: {DEBUG_LEVEL.upper()}")
    logger.info(f"Main log file: {log_filename}")
    logger.info(f"Console: INFO+ | File: {logging.getLevelName(file_level)}+")

    # Setup conversation logging if in debug mode and explicitly enabled
    conversation_log = None
    if DEBUG_LEVEL == 'debug':
        conversation_log = _setup_conversation_logging()
        if conversation_log:
            logger.info(f"Conversation log file: {conversation_log}")

    return log_filename, conversation_log


def _suppress_external_loggers():
    """Suppress DEBUG messages from external libraries."""
    external_loggers = [
        # Discord.py
        'discord', 'discord.http', 'discord.gateway', 'discord.client',
        # HTTP and web scraping libraries
        'urllib3', 'urllib3.connectionpool', 'trafilatura', 'websockets',
        # DDGS and its dependencies
        'ddgs', 'ddgs.http_client', 'ddgs.http_client2', 'ddgs.base',
        'ddgs.engines', 'ddgs.ddgs', 'httpx', 'httpcore',
        'httpcore.http11', 'httpcore.connection', 'httpcore.proxy',
        'httpcore.http2', 'httpcore.socks',
        # Image processing
        'PIL',
    ]

    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _setup_conversation_logging() -> Optional[str]:
    """
    Setup separate conversation logging for debug mode.

    Returns:
        str: Path to conversation log file, or None if disabled
    """
    # Import here to avoid circular dependency
    import os

    # Check for ENABLE_CONVERSATION_LOG setting
    enable_conv_log = os.getenv('ENABLE_CONVERSATION_LOG', 'false').lower() == 'true'

    if not enable_conv_log:
        return None

    # Create conversation log filename
    conv_log_filename = os.path.join(
        LOG_DIR,
        f"conversations_{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    # Create conversation logger
    conv_logger = logging.getLogger('conversation')
    conv_logger.setLevel(logging.INFO)
    conv_logger.propagate = False  # Don't send to root logger

    # Create handler for conversation log
    conv_handler = RotatingFileHandler(
        conv_log_filename,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    conv_handler.setLevel(logging.INFO)
    conv_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    conv_logger.addHandler(conv_handler)

    return conv_log_filename


def log_conversation(user_id: int, guild_id: Optional[int], message: str, is_bot: bool = False):
    """
    Log a conversation message to the conversation log file.
    Only logs if conversation logging is enabled.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID (None for DMs)
        message: The message text
        is_bot: True if this is a bot response, False if user message
    """
    conv_logger = logging.getLogger('conversation')

    # Only log if handler exists (conversation logging is enabled)
    if not conv_logger.handlers:
        return

    # Format the message
    sender = "BOT" if is_bot else "USER"
    guild_str = f"Guild:{guild_id}" if guild_id else "DM"

    # Clean message for logging (preserve newlines as literal \n for readability)
    clean_message = message.replace('\n', '\\n').strip()

    # No truncation - log full messages for debugging purposes
    log_line = f"[{guild_str}] [User:{user_id}] [{sender}] {clean_message}"
    conv_logger.info(log_line)


def log_effective_config():
    """Log the current logging configuration for debugging."""
    logger = logging.getLogger(__name__)
    root_logger = logging.getLogger()
    handlers = root_logger.handlers

    logger.info("Logging configuration:")
    logger.info("  Root logger level: %s", logging.getLevelName(root_logger.level))

    for i, handler in enumerate(handlers):
        logger.info(
            "  Handler %d: %s | level=%s",
            i,
            handler.__class__.__name__,
            logging.getLevelName(handler.level)
        )


def guild_debug_log(
    guild_id: Optional[int],
    level: str,
    message: str,
    *args,
    **kwargs
):
    """
    Log debug messages for guilds with debug enabled.
    Automatically fetches guild settings from the settings manager.

    Args:
        guild_id: The guild ID to check for debug settings
        level: Log level ("info" or "debug")
        message: Message format string
        *args: Arguments for message formatting

    Key Changes in This Version:
    - Uses root logger (logging.getLogger()) instead of module logger for consistent output
    - Logs errors when settings can't be loaded (instead of silently failing)
    - This ensures debug messages actually reach the console and log files
    """
    # Use root logger for consistent output - THIS IS THE KEY CHANGE
    logger = logging.getLogger()

    # Skip if no guild_id
    if not guild_id:
        return

    # Fetch settings from the settings manager
    try:
        from utils.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()

        debug_enabled = settings_mgr.is_debug_enabled(guild_id)
        debug_level = settings_mgr.get_debug_level(guild_id)
    except Exception as e:
        # Log the error so user knows something is wrong - IMPROVED ERROR HANDLING
        logger.error(f"guild_debug_log: Failed to get settings for guild {guild_id}: {e}")
        return

    # Skip if debug not enabled
    if not debug_enabled:
        return

    # Skip debug messages if level is set to info
    if level == "debug" and debug_level != "debug":
        return

    # Format the message with args if provided
    try:
        if args:
            message = message % args
    except Exception as e:
        logger.error(f"Debug log formatting error: {e}")
        message = f"{message} (format error with args: {args})"

    # Log with guild prefix
    log_message = f"[GUILD-{guild_id} DEBUG] {message}"

    if level == "debug":
        logger.debug(log_message)
    else:
        logger.info(log_message)


def is_debug_enabled(guild_id: Optional[int], guild_settings: dict = None) -> bool:
    """Check if debug logging is enabled for a guild."""
    if guild_settings is None:
        guild_settings = {}

    if guild_id and guild_id in guild_settings:
        return bool(guild_settings[guild_id].get("debug", False))
    return False


def get_debug_level(guild_id: Optional[int], guild_settings: dict = None) -> str:
    """Get the debug level for a guild (info or debug)."""
    if guild_settings is None:
        guild_settings = {}

    if guild_id and guild_id in guild_settings:
        return guild_settings[guild_id].get("debug_level", "debug")
    return "debug"
