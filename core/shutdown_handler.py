"""
Graceful shutdown handler.
Ensures stats and settings are saved before bot exits.
"""
import signal
import sys
import logging
import atexit

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """
    Handles graceful shutdown of the bot.
    
    Saves all data and cleans up resources before exit.
    """
    
    def __init__(self, bot):
        """
        Initialize shutdown handler.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.shutdown_initiated = False
    
    def cleanup(self):
        """Perform synchronous cleanup operations before shutdown."""
        if self.shutdown_initiated:
            return
        
        self.shutdown_initiated = True
        logger.info("🛑 Initiating graceful shutdown...")
        
        # Save statistics
        try:
            logger.info("💾 Saving statistics...")
            from utils.stats_manager import save_stats
            save_stats()
            logger.info("✅ Statistics saved")
        except Exception as e:
            logger.error(f"❌ Error saving statistics: {e}", exc_info=True)
        
        # Save guild settings
        try:
            logger.info("💾 Saving guild settings...")
            from utils.settings_manager import save_guild_settings
            save_guild_settings()
            logger.info("✅ Guild settings saved")
        except Exception as e:
            logger.error(f"❌ Error saving guild settings: {e}", exc_info=True)
        
        logger.info("👋 Shutdown complete")
    
    def handle_signal(self, sig, frame):
        """
        Handle system signals (SIGINT, SIGTERM).
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(sig).name
        logger.info(f"📡 Received signal: {signal_name}")
        
        # Run cleanup immediately (synchronous)
        self.cleanup()
        
        # Exit gracefully
        sys.exit(0)


def setup_shutdown_handlers(bot):
    """
    Register signal handlers for graceful shutdown.
    
    Args:
        bot: Discord bot instance
    """
    handler = ShutdownHandler(bot)
    
    # Register atexit handler (runs on any exit)
    atexit.register(handler.cleanup)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handler.handle_signal)   # Ctrl+C
    signal.signal(signal.SIGTERM, handler.handle_signal)  # Kill command
    
    # On Windows, also handle SIGBREAK (Ctrl+Break)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, handler.handle_signal)
    
    logger.info("✅ Shutdown handlers registered (SIGINT, SIGTERM)")
    
    return handler