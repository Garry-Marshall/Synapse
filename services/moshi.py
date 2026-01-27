"""
Moshi AI Voice Assistant Service
Handles WebSocket connection and audio streaming with Moshi voice AI
"""

import asyncio
import logging
import aiohttp
import json
import threading
import queue
from typing import Optional, AsyncIterator, Callable
from config.settings import MOSHI_URL, ENABLE_MOSHI, MOSHI_VOICE, MOSHI_TEXT_PROMPT

logger = logging.getLogger(__name__)

class MoshiClient:
    """
    Client for Moshi voice AI assistant.
    Runs WebSocket communication in a dedicated thread with its own event loop
    to avoid blocking Discord's event loop.
    """

    def __init__(self, base_url: str = MOSHI_URL, voice_prompt: str = "NATF2.pt", text_prompt: str = ""):
        """
        Initialize Moshi client

        Args:
            base_url: Base URL for Moshi server (default from settings)
            voice_prompt: Voice prompt file (e.g., NATF2.pt for female, NATM0.pt for male)
            text_prompt: System/text prompt for the AI assistant
        """
        self.base_url = base_url.rstrip('/')
        self.voice_prompt = voice_prompt
        self.text_prompt = text_prompt
        # Build WebSocket URL with voice_prompt and text_prompt query parameters
        ws_base = f"{self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')}/api/chat"
        # URL encode the text_prompt
        from urllib.parse import quote
        encoded_text_prompt = quote(text_prompt)
        self.ws_url = f"{ws_base}?voice_prompt={voice_prompt}&text_prompt={encoded_text_prompt}"
        
        # Connection state
        self.connected = False
        self._handshake_complete = False
        
        # Thread-safe queues for cross-thread communication
        self._outbound_queue = queue.Queue()  # Audio to send to Moshi
        
        # Callbacks
        self._sync_audio_callback: Optional[Callable] = None
        self._audio_callback: Optional[Callable] = None
        
        # Dedicated thread and event loop for WebSocket
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_loop: Optional[asyncio.AbstractEventLoop] = None
        self._websocket = None
        self._stop_event = threading.Event()

    def _run_ws_thread(self):
        """Run WebSocket communication in dedicated thread"""
        # Create new event loop for this thread
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)
        
        try:
            self._ws_loop.run_until_complete(self._ws_main())
        except Exception as e:
            logger.error(f"WebSocket thread error: {e}", exc_info=True)
        finally:
            self._ws_loop.close()
            self._ws_loop = None

    async def _ws_main(self):
        """Main WebSocket loop running in dedicated thread"""
        try:
            # Create session and connect
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                logger.debug(f"Connecting to Moshi at {self.ws_url}")
                async with session.ws_connect(
                    self.ws_url,
                    heartbeat=30,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as websocket:
                    self._websocket = websocket
                    self.connected = True
                    logger.info("Connected to Moshi")
                    
                    # Run send and receive concurrently
                    # Use return_exceptions to prevent one failure from killing the other
                    results = await asyncio.gather(
                        self._receive_loop(websocket),
                        self._send_loop(websocket),
                        return_exceptions=True
                    )
                    
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"Moshi task error: {result}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            self.connected = False
            self._handshake_complete = False
            self._websocket = None

    async def _receive_loop(self, websocket):
        """Receive messages from Moshi - high priority, minimal overhead"""
        try:
            async for msg in websocket:
                if self._stop_event.is_set():
                    break

                if msg.type == aiohttp.WSMsgType.BINARY:
                    data_len = len(msg.data)

                    # Handle handshake
                    if not self._handshake_complete and data_len < 100:
                        self._handshake_complete = True
                        logger.debug("Moshi handshake complete")
                        continue

                    # Strip message type byte if present
                    audio_data = msg.data
                    if data_len > 1 and audio_data[0] == 0x01:
                        audio_data = audio_data[1:]
                        data_len = len(audio_data)

                    # Call sync callback directly (we're in dedicated thread)
                    if self._sync_audio_callback and data_len > 0:
                        self._sync_audio_callback(audio_data)

                elif msg.type == aiohttp.WSMsgType.TEXT:
                    logger.debug(f"Moshi text: {msg.data}")

                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                    logger.debug("Moshi WebSocket closed")
                    break

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"Moshi WebSocket error: {msg.data}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive loop error: {e}", exc_info=True)

    async def _send_loop(self, websocket):
        """Send queued audio to Moshi"""
        try:
            while not self._stop_event.is_set() and not websocket.closed:
                # Batch all queued messages
                batch = []
                while len(batch) < 50:
                    try:
                        message = self._outbound_queue.get_nowait()
                        batch.append(message)
                    except queue.Empty:
                        break

                # Send batch
                for message in batch:
                    if websocket.closed:
                        break
                    try:
                        await websocket.send_bytes(message)
                    except Exception as e:
                        if "closing" in str(e).lower() or "closed" in str(e).lower():
                            return
                        raise

                # Minimal sleep - just yield to receive loop
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Send loop error: {e}", exc_info=True)

    async def connect(self) -> bool:
        """
        Start WebSocket communication in dedicated thread

        Returns:
            bool: True if thread started (connection happens async)
        """
        try:
            self._stop_event.clear()
            self._ws_thread = threading.Thread(target=self._run_ws_thread, daemon=True, name="MoshiWS")
            self._ws_thread.start()
            
            # Wait briefly for connection
            for _ in range(50):  # Up to 5 seconds
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            
            logger.error("Timeout waiting for Moshi connection")
            return self.connected

        except Exception as e:
            logger.error(f"Failed to start Moshi thread: {e}")
            return False

    async def disconnect(self):
        """Stop WebSocket thread and close connection"""
        try:
            self._stop_event.set()
            self.connected = False

            # Close WebSocket from its event loop
            if self._ws_loop and self._websocket and not self._websocket.closed:
                try:
                    # Schedule close on the WS thread's event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self._websocket.close(),
                        self._ws_loop
                    )
                    # Wait briefly for close to complete
                    future.result(timeout=1.0)
                except Exception as e:
                    logger.debug(f"WebSocket close: {e}")

            if self._ws_thread and self._ws_thread.is_alive():
                self._ws_thread.join(timeout=2.0)

            self._ws_thread = None
            self._websocket = None
            logger.info("Disconnected from Moshi")

        except Exception as e:
            logger.error(f"Error during Moshi disconnect: {e}")

    async def send_audio(self, audio_data: bytes):
        """
        Queue audio data to be sent to Moshi (non-blocking)

        Args:
            audio_data: Raw Opus packet bytes (24kHz mono)
        """
        self.queue_audio(audio_data)
    
    def queue_audio(self, audio_data: bytes):
        """
        Synchronously queue audio data to be sent to Moshi
        Can be called from any thread.

        Args:
            audio_data: Raw Opus packet bytes (24kHz mono)
        """
        if not self.connected:
            return

        # Wait for handshake to complete before sending audio
        if not self._handshake_complete:
            return

        # Validate audio data
        if not audio_data or len(audio_data) == 0:
            return

        # Protocol: first byte = message kind (1 = audio), rest = Opus data
        message = b'\x01' + audio_data

        # Queue for the send task (thread-safe, non-blocking)
        self._outbound_queue.put(message)

    def set_audio_callback(self, callback: Callable):
        """
        Set callback function for received audio

        Args:
            callback: Async function that takes audio bytes as parameter
        """
        self._audio_callback = callback
    
    def set_sync_audio_callback(self, callback: Callable):
        """
        Set SYNCHRONOUS callback for received audio (lower latency)

        Args:
            callback: Sync function that takes audio bytes as parameter
        """
        self._sync_audio_callback = callback

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Moshi"""
        return self.connected


class MoshiSession:
    """Manages a Moshi voice conversation session for a Discord guild"""

    def __init__(self, guild_id: int, voice_prompt: Optional[str] = None, text_prompt: Optional[str] = None):
        """
        Initialize Moshi session for a guild

        Args:
            guild_id: Discord guild ID
            voice_prompt: Voice prompt file (defaults to MOSHI_VOICE from settings if not provided)
            text_prompt: System/text prompt (defaults to MOSHI_TEXT_PROMPT from settings if not provided)
        """
        self.guild_id = guild_id
        # Use provided values or fall back to defaults from settings
        voice = voice_prompt if voice_prompt is not None else MOSHI_VOICE
        prompt = text_prompt if text_prompt is not None else MOSHI_TEXT_PROMPT
        self.client = MoshiClient(voice_prompt=voice, text_prompt=prompt)
        self.active = False
        self._audio_buffer = asyncio.Queue()

    async def start(self) -> bool:
        """
        Start Moshi session

        Returns:
            bool: True if session started successfully
        """
        if not ENABLE_MOSHI:
            logger.warning("Moshi is disabled in configuration")
            return False

        success = await self.client.connect()
        if success:
            self.active = True
            # Set callback to buffer received audio
            self.client.set_audio_callback(self._on_audio_received)

            logger.info(f"Moshi session started for guild {self.guild_id}")

        return success

    async def stop(self):
        """Stop Moshi session"""
        self.active = False
        await self.client.disconnect()
        logger.info(f"Moshi session stopped for guild {self.guild_id}")

    async def send_audio(self, audio_data: bytes):
        """
        Send audio to Moshi

        Args:
            audio_data: Audio bytes from Discord voice
        """
        if self.active:
            await self.client.send_audio(audio_data)

    def queue_audio(self, audio_data: bytes):
        """
        Synchronously queue audio to Moshi (thread-safe)

        Args:
            audio_data: Audio bytes from Discord voice
        """
        if self.active:
            self.client.queue_audio(audio_data)

    async def _on_audio_received(self, audio_data: bytes):
        """Callback for received audio from Moshi"""
        await self._audio_buffer.put(audio_data)

    async def get_audio_response(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        Get audio response from buffer

        Args:
            timeout: Timeout in seconds

        Returns:
            Audio bytes or None if timeout
        """
        try:
            # Always try non-blocking first (avoids race with empty() check)
            return self._audio_buffer.get_nowait()
        except asyncio.QueueEmpty:
            if timeout > 0:
                try:
                    return await asyncio.wait_for(self._audio_buffer.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
            return None


# Global session manager
_active_sessions: dict[int, MoshiSession] = {}


async def get_moshi_session(guild_id: int) -> Optional[MoshiSession]:
    """
    Get active Moshi session for guild

    Args:
        guild_id: Discord guild ID

    Returns:
        MoshiSession or None if not active
    """
    return _active_sessions.get(guild_id)


async def start_moshi_session(guild_id: int, text_prompt: Optional[str] = None, voice_prompt: Optional[str] = None) -> Optional[MoshiSession]:
    """
    Start new Moshi session for guild

    Args:
        guild_id: Discord guild ID
        text_prompt: Optional custom text prompt (defaults to MOSHI_TEXT_PROMPT from settings if not provided)
        voice_prompt: Optional custom voice prompt (defaults to MOSHI_VOICE from settings if not provided)

    Returns:
        MoshiSession or None if failed to start
    """
    # Stop existing session if any
    if guild_id in _active_sessions:
        await stop_moshi_session(guild_id)

    # Use custom values if provided, otherwise MoshiSession will use defaults from settings
    session = MoshiSession(guild_id, voice_prompt=voice_prompt, text_prompt=text_prompt)
    success = await session.start()

    if success:
        _active_sessions[guild_id] = session
        return session

    return None


async def stop_moshi_session(guild_id: int):
    """
    Stop Moshi session for guild

    Args:
        guild_id: Discord guild ID
    """
    session = _active_sessions.pop(guild_id, None)
    if session:
        await session.stop()


async def is_moshi_available() -> bool:
    """
    Check if Moshi service is available

    Returns:
        bool: True if Moshi is enabled and reachable
    """
    if not ENABLE_MOSHI:
        return False

    try:
        # Test connection
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(MOSHI_URL, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status < 500
    except Exception as e:
        logger.error(f"Moshi availability check failed: {e}")
        return False
