"""
Database module for persistent storage using SQLite.
Handles guild settings, conversation statistics, and data migration.
"""
import sqlite3
import json
import logging
import os
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from contextlib import contextmanager
from threading import Lock

from config.settings import DB_FILE

logger = logging.getLogger(__name__)

# Thread-safe lock for database operations
_db_lock = Lock()


class Database:
    """
    SQLite database manager for bot data.
    
    Handles:
    - Guild settings storage
    - Conversation statistics
    - Automatic migration from JSON files
    """
    
    def __init__(self, db_path: str = DB_FILE):
        """
        Initialize database connection and schema.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
        self._initialize_database()
    
    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursor with automatic commit/rollback."""
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database error: {e}", exc_info=True)
                raise
            finally:
                cursor.close()
                conn.close()
    
    def _initialize_database(self) -> None:
        """Create database schema if it doesn't exist."""
        logger.info(f"Initializing database: {self.db_path}")
        
        with self._get_cursor() as cursor:
            # Guild settings table (key-value store with JSON values)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, key)
                )
            """)
            
            # Index for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_settings_lookup 
                ON guild_settings(guild_id, key)
            """)
            
            # Conversation statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    start_time TIMESTAMP NOT NULL,
                    last_message_time TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    prompt_tokens_estimate INTEGER DEFAULT 0,
                    response_tokens_raw INTEGER DEFAULT 0,
                    response_tokens_cleaned INTEGER DEFAULT 0,
                    failed_requests INTEGER DEFAULT 0,
                    tool_usage TEXT,
                    response_times TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for cleanup queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_last_message 
                ON conversations(last_message_time)
            """)
            
            logger.info("Database schema initialized successfully")
    
    # ========================================================================
    # GUILD SETTINGS METHODS
    # ========================================================================
    
    def get_setting(self, guild_id: int, key: str, default: Any = None) -> Any:
        """
        Get a guild setting value.
        
        Args:
            guild_id: Guild ID
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value (parsed from JSON) or default
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT value FROM guild_settings WHERE guild_id = ? AND key = ?",
                (guild_id, key)
            )
            row = cursor.fetchone()
            
            if row and row['value'] is not None:
                try:
                    return json.loads(row['value'])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse setting {key} for guild {guild_id}")
                    return default
            
            return default
    
    def set_setting(self, guild_id: int, key: str, value: Any) -> None:
        """
        Set a guild setting value.
        
        Args:
            guild_id: Guild ID
            key: Setting key
            value: Setting value (will be JSON encoded)
        """
        json_value = json.dumps(value)
        
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO guild_settings (guild_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, key) 
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """, (guild_id, key, json_value))
        
        logger.debug(f"Updated setting {key} for guild {guild_id}")
    
    def delete_setting(self, guild_id: int, key: str) -> None:
        """
        Delete a guild setting.
        
        Args:
            guild_id: Guild ID
            key: Setting key
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM guild_settings WHERE guild_id = ? AND key = ?",
                (guild_id, key)
            )
        
        logger.debug(f"Deleted setting {key} for guild {guild_id}")
    
    def get_all_settings(self, guild_id: int) -> Dict[str, Any]:
        """
        Get all settings for a guild.
        
        Args:
            guild_id: Guild ID
            
        Returns:
            Dictionary of all settings
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT key, value FROM guild_settings WHERE guild_id = ?",
                (guild_id,)
            )
            
            settings = {}
            for row in cursor.fetchall():
                try:
                    settings[row['key']] = json.loads(row['value'])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse setting {row['key']} for guild {guild_id}")
            
            return settings
    
    def clear_all_settings(self, guild_id: int) -> None:
        """
        Clear all settings for a guild.
        
        Args:
            guild_id: Guild ID
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        
        logger.info(f"Cleared all settings for guild {guild_id}")
    
    # ========================================================================
    # CONVERSATION STATISTICS METHODS
    # ========================================================================
    
    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get conversation statistics.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Dictionary with conversation stats or None
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Parse JSON fields
            stats = dict(row)
            stats['start_time'] = datetime.fromisoformat(stats['start_time'])
            if stats['last_message_time']:
                stats['last_message_time'] = datetime.fromisoformat(stats['last_message_time'])
            stats['tool_usage'] = json.loads(stats['tool_usage']) if stats['tool_usage'] else {}
            stats['response_times'] = json.loads(stats['response_times']) if stats['response_times'] else []

            # Migration: Add comfyui_generation if missing (for existing databases)
            if 'comfyui_generation' not in stats['tool_usage']:
                stats['tool_usage']['comfyui_generation'] = 0

            return stats
    
    def create_conversation(self, conversation_id: int, guild_id: Optional[int] = None) -> None:
        """
        Create a new conversation record.
        
        Args:
            conversation_id: Conversation ID
            guild_id: Guild ID (None for DMs)
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO conversations
                (conversation_id, guild_id, start_time, tool_usage, response_times)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
            """, (
                conversation_id,
                guild_id,
                json.dumps({"web_search": 0, "url_fetch": 0, "image_analysis": 0, "pdf_read": 0, "tts_voice": 0, "comfyui_generation": 0}),
                json.dumps([])
            ))
        
        logger.debug(f"Created conversation record for {conversation_id}")
    
    def update_conversation(
        self,
        conversation_id: int,
        prompt_tokens: int = 0,
        response_tokens_raw: int = 0,
        response_tokens_cleaned: int = 0,
        response_time: Optional[float] = None,
        failed: bool = False,
        tool_used: Optional[str] = None
    ) -> None:
        """
        Update conversation statistics.
        
        Args:
            conversation_id: Conversation ID
            prompt_tokens: Tokens in prompt
            response_tokens_raw: Raw response tokens
            response_tokens_cleaned: Cleaned response tokens
            response_time: Response time in seconds
            failed: Whether request failed
            tool_used: Name of tool used
        """
        # Get current stats
        stats = self.get_conversation(conversation_id)
        
        if not stats:
            # Create if doesn't exist
            self.create_conversation(conversation_id)
            stats = self.get_conversation(conversation_id)
        
        # Update counters
        if failed:
            stats['failed_requests'] += 1
        else:
            stats['total_messages'] += 1
            stats['prompt_tokens_estimate'] += prompt_tokens
            stats['response_tokens_raw'] += response_tokens_raw
            stats['response_tokens_cleaned'] += response_tokens_cleaned
            stats['last_message_time'] = datetime.now()
            
            if response_time is not None:
                response_times = stats['response_times']
                response_times.append(response_time)
                # Keep only last 100 entries
                if len(response_times) > 100:
                    response_times = response_times[-100:]
                stats['response_times'] = response_times
        
        # Update tool usage
        if tool_used and tool_used in stats['tool_usage']:
            stats['tool_usage'][tool_used] += 1
        
        # Save back to database
        with self._get_cursor() as cursor:
            cursor.execute("""
                UPDATE conversations SET
                    total_messages = ?,
                    prompt_tokens_estimate = ?,
                    response_tokens_raw = ?,
                    response_tokens_cleaned = ?,
                    failed_requests = ?,
                    last_message_time = ?,
                    tool_usage = ?,
                    response_times = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ?
            """, (
                stats['total_messages'],
                stats['prompt_tokens_estimate'],
                stats['response_tokens_raw'],
                stats['response_tokens_cleaned'],
                stats['failed_requests'],
                stats['last_message_time'].isoformat() if stats['last_message_time'] else None,
                json.dumps(stats['tool_usage']),
                json.dumps(stats['response_times']),
                conversation_id
            ))
    
    def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        Delete conversations older than specified days.
        
        Args:
            days: Number of days of inactivity
            
        Returns:
            Number of conversations deleted
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM conversations 
                WHERE last_message_time IS NOT NULL 
                AND last_message_time < ?
            """, (cutoff.isoformat(),))
            
            deleted = cursor.rowcount
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} inactive conversations (older than {days} days)")
        
        return deleted
    
    def get_all_conversation_ids(self) -> List[int]:
        """Get list of all conversation IDs."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT conversation_id FROM conversations")
            return [row['conversation_id'] for row in cursor.fetchall()]

    def reset_guild_stats(self, guild_id: int) -> int:
        """
        Reset all statistics for conversations in a guild.

        Args:
            guild_id: Guild ID

        Returns:
            Number of conversations reset
        """
        with self._get_cursor() as cursor:
            # Reset all stats for conversations in this guild
            cursor.execute("""
                UPDATE conversations SET
                    start_time = CURRENT_TIMESTAMP,
                    last_message_time = NULL,
                    total_messages = 0,
                    prompt_tokens_estimate = 0,
                    response_tokens_raw = 0,
                    response_tokens_cleaned = 0,
                    failed_requests = 0,
                    tool_usage = ?,
                    response_times = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
            """, (
                json.dumps({"web_search": 0, "url_fetch": 0, "image_analysis": 0, "pdf_read": 0, "tts_voice": 0}),
                json.dumps([]),
                guild_id
            ))

            reset_count = cursor.rowcount

        if reset_count > 0:
            logger.info(f"Reset statistics for {reset_count} conversation(s) in guild {guild_id}")

        return reset_count
    
    # ========================================================================
    # MIGRATION METHODS
    # ========================================================================
    
    def migrate_from_json(self, settings_file: str, stats_file: str) -> None:
        """
        Migrate data from JSON files to database.
        
        Args:
            settings_file: Path to guild_settings.json
            stats_file: Path to channel_stats.json
        """
        logger.info("Starting migration from JSON files to database...")
        
        # Migrate guild settings
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    old_settings = json.load(f)
                
                for guild_id_str, settings in old_settings.items():
                    guild_id = int(guild_id_str)
                    for key, value in settings.items():
                        self.set_setting(guild_id, key, value)
                
                logger.info(f"✅ Migrated settings for {len(old_settings)} guild(s)")
                
                # Backup old file
                backup_path = f"{settings_file}.backup"
                os.rename(settings_file, backup_path)
                logger.info(f"Backed up old settings to {backup_path}")
                
            except Exception as e:
                logger.error(f"Failed to migrate guild settings: {e}", exc_info=True)
        
        # Migrate conversation stats
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    old_stats = json.load(f)
                
                for conv_id_str, stats in old_stats.items():
                    conv_id = int(conv_id_str)
                    
                    # Parse timestamps
                    start_time = datetime.fromisoformat(stats['start_time'])
                    last_msg_time = None
                    if stats.get('last_message_time'):
                        last_msg_time = datetime.fromisoformat(stats['last_message_time'])
                    
                    # Insert conversation
                    with self._get_cursor() as cursor:
                        cursor.execute("""
                            INSERT OR REPLACE INTO conversations 
                            (conversation_id, guild_id, start_time, last_message_time,
                             total_messages, prompt_tokens_estimate, response_tokens_raw,
                             response_tokens_cleaned, failed_requests, tool_usage, response_times)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            conv_id,
                            None,  # guild_id not stored in old format
                            start_time.isoformat(),
                            last_msg_time.isoformat() if last_msg_time else None,
                            stats.get('total_messages', 0),
                            stats.get('prompt_tokens_estimate', 0),
                            stats.get('response_tokens_raw', 0),
                            stats.get('response_tokens_cleaned', 0),
                            stats.get('failed_requests', 0),
                            json.dumps(stats.get('tool_usage', {})),
                            json.dumps(stats.get('response_times', []))
                        ))
                
                logger.info(f"✅ Migrated statistics for {len(old_stats)} conversation(s)")
                
                # Backup old file
                backup_path = f"{stats_file}.backup"
                os.rename(stats_file, backup_path)
                logger.info(f"Backed up old stats to {backup_path}")
                
            except Exception as e:
                logger.error(f"Failed to migrate conversation stats: {e}", exc_info=True)
        
        logger.info("Migration completed")


# Global database instance
_database: Optional[Database] = None


def get_database() -> Database:
    """
    Get the global database instance.
    
    Returns:
        Database instance
    """
    global _database
    if _database is None:
        _database = Database()
        
        # Auto-migrate from JSON if files exist
        from config.settings import GUILD_SETTINGS_FILE, STATS_FILE
        if os.path.exists(GUILD_SETTINGS_FILE) or os.path.exists(STATS_FILE):
            logger.info("📦 JSON files detected - starting automatic migration...")
            _database.migrate_from_json(GUILD_SETTINGS_FILE, STATS_FILE)
    
    return _database