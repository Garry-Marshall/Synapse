"""
Logging configuration and setup.
Handles file and console logging with rotation.
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
    Configure logging to both file and console.
    Creates rotating log files in the Logs directory.
    """
    # Create log directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create log filename with date stamp
    log_filename = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y-%m-%d')}.log")
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # File handler with rotation (max 10MB per file, keep 5 backup files)
            RotatingFileHandler(
                log_filename, 
                maxBytes=LOG_MAX_BYTES, 
                backupCount=LOG_BACKUP_COUNT, 
                encoding='utf-8'
            ),
            # Console handler
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_filename}")
    
    return log_filename


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
    guild_settings: dict = None
):
    """
    Log debug messages for guilds with debug enabled.
    
    Args:
        guild_id: The guild ID to check for debug settings
        level: Log level ("info" or "debug")
        message: Message format string
        *args: Arguments for message formatting
        guild_settings: Guild settings dictionary (optional)
    """
    logger = logging.getLogger(__name__)
    
    # Check if debug is enabled for this guild
    if guild_settings is None:
        guild_settings = {}
    
    if guild_id and guild_id in guild_settings:
        debug_enabled = guild_settings[guild_id].get("debug", False)
        debug_level = guild_settings[guild_id].get("debug_level", "info")
    else:
        debug_enabled = False
        debug_level = "info"
    
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
    log_message = f"[GUILD-{guild_id}] {message}"
    
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