"""
Discord Bot - Main Entry Point
A modular Discord bot with LMStudio integration, TTS, and file processing.
"""
import logging

from config.settings import DISCORD_TOKEN, CHANNEL_IDS
from utils.logging_config import setup_logging
from core.events import setup_events
from core.bot_instance import bot


# Setup logging first
log_filename = setup_logging()

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the bot."""
    
    # Validate configuration
    if DISCORD_TOKEN == 'your-discord-bot-token-here':
        logger.error("Please set your DISCORD_BOT_TOKEN environment variable")
        logger.info("You can create a bot at: https://discord.com/developers/applications")
        return
    
    if not CHANNEL_IDS or CHANNEL_IDS == {0}:
        logger.error("Please set your DISCORD_CHANNEL_IDS environment variable")
        logger.info("Right-click channels in Discord (with Developer Mode on) and click 'Copy ID'")
        logger.info("Format: DISCORD_CHANNEL_IDS=123456789,987654321,111222333")
        return
    
    # Setup event handlers
    setup_events(bot)
    
    # Start the bot
    logger.info("Starting bot...")
    logger.info(f"Logging to: {log_filename}")
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()