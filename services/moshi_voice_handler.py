"""
Discord voice integration for Moshi AI
Handles voice input/output between Discord and Moshi
Uses discord-ext-voice-recv for receiving audio
"""

import asyncio
import logging
import discord
from discord.ext import voice_recv
import io
import time
import threading
from typing import Optional
from services.moshi import MoshiSession, start_moshi_session, stop_moshi_session, get_moshi_session
from utils.opus_transcoder import OpusTranscoder
from utils.ogg_opus_writer_v2 import OggOpusWriterV2
from utils.settings_manager import get_guild_setting
from config.settings import MOSHI_TEXT_PROMPT

logger = logging.getLogger(__name__)

# Opus silence packet - sent during pauses to maintain continuous stream
OPUS_SILENCE = b'\xF8\xFF\xFE'


class MoshiAudioSink(voice_recv.AudioSink):
    """
    Audio sink that captures Discord voice input and sends to Moshi.
    Includes a silence generator thread to ensure continuous audio flow to Moshi.
    """

    def __init__(self, guild_id: int, moshi_session: MoshiSession, loop: asyncio.AbstractEventLoop, transcoder: OpusTranscoder):
        """
        Initialize audio sink

        Args:
            guild_id: Discord guild ID
            moshi_session: Active Moshi session
            loop: Event loop for scheduling async tasks
            transcoder: Opus transcoder for sample rate conversion
        """
        super().__init__()
        self.guild_id = guild_id
        self.moshi_session = moshi_session
        self.transcoder = transcoder
        self.loop = loop
        self.ogg_writer = OggOpusWriterV2(sample_rate=24000, channels=1)  # Wrap Opus in Ogg for Moshi

        # Timing for silence generation
        self._last_audio_time = 0.0
        self._running = True
        self._headers_sent = False
        self._write_count = 0

        # Pre-generate silence packet for Moshi (24kHz mono)
        self._silence_opus_24k = self.transcoder.discord_to_moshi(OPUS_SILENCE)

        # Start silence generator thread
        self._silence_thread = threading.Thread(target=self._silence_generator, daemon=True, name="MoshiSilenceGen")
        self._silence_thread.start()

    def _send_headers_if_needed(self):
        """Send Ogg headers if not already sent"""
        if self._headers_sent:
            return

        headers = self.ogg_writer.get_headers()
        for header in headers:
            self.moshi_session.queue_audio(header)
        self._headers_sent = True

    def _silence_generator(self):
        """
        Background thread that sends silence packets to Moshi when no real audio is received.
        This ensures continuous audio flow for proper Moshi operation.
        """
        # Wait for handshake before starting
        while self._running:
            handshake_done = getattr(self.moshi_session.client, '_handshake_complete', False)
            if handshake_done:
                break
            time.sleep(0.1)

        if not self._running:
            return

        # Send silence at 20ms intervals when no real audio
        silence_interval = 0.020
        last_send_time = time.time()

        while self._running:
            current_time = time.time()
            time_since_audio = current_time - self._last_audio_time
            time_since_send = current_time - last_send_time

            # Send silence if: headers sent, no recent audio (>40ms), and 20ms since last send
            if self._headers_sent and time_since_audio > 0.040 and time_since_send >= silence_interval:
                if self._silence_opus_24k:
                    ogg_page = self.ogg_writer.write_opus_packet(self._silence_opus_24k, samples=960)
                    self.moshi_session.queue_audio(ogg_page)
                    last_send_time = current_time

            time.sleep(0.005)

    def wants_opus(self) -> bool:
        """We want Opus audio (Moshi expects Opus-encoded input)"""
        return True

    def write(self, user, data: voice_recv.VoiceData):
        """
        Called when audio data is received from a user (in player thread).
        Does transcoding here to avoid blocking event loop.
        """
        if user and user.bot:
            return  # Ignore bot audio

        # Get Opus-encoded audio from the RTP packet
        if hasattr(data, 'opus') and data.opus:
            opus_packet = data.opus

            if len(opus_packet) > 0:
                # Check handshake status
                handshake_done = getattr(self.moshi_session.client, '_handshake_complete', False)
                if not handshake_done:
                    return

                # Update last audio time (even for silence, to track activity)
                self._last_audio_time = time.time()

                # Transcode HERE in player thread (not on event loop!)
                transcoded = self.transcoder.discord_to_moshi(opus_packet)

                if transcoded:
                    # Send headers if needed
                    self._send_headers_if_needed()

                    # Wrap audio in Ogg container - samples=960 for 20ms at 48kHz
                    ogg_page = self.ogg_writer.write_opus_packet(transcoded, samples=960)

                    # Queue directly to Moshi client (thread-safe)
                    self.moshi_session.queue_audio(ogg_page)

    def cleanup(self):
        """Cleanup resources"""
        self._running = False
        if hasattr(self, '_silence_thread') and self._silence_thread.is_alive():
            self._silence_thread.join(timeout=1.0)

# Jitter buffer settings - Moshi sends audio in bursts, so we need a larger buffer
JITTER_BUFFER_MIN_FRAMES = 20   # Start playback after this many frames buffered (400ms)
JITTER_BUFFER_MAX_FRAMES = 200  # Max buffer size (4 seconds)


class MoshiAudioSource(discord.AudioSource):
    """
    Audio source that plays Moshi's voice responses in Discord
    Transcoding happens in Discord's player thread to avoid blocking the event loop
    """

    def __init__(self, guild_id: int, moshi_session: MoshiSession, transcoder: OpusTranscoder):
        """
        Initialize audio source
        """
        self.guild_id = guild_id
        self.moshi_session = moshi_session
        self.transcoder = transcoder
        
        # Thread-safe queues
        import queue
        self.raw_ogg_queue = queue.Queue()  # Raw Ogg data from WebSocket
        self.opus_packets = queue.Queue()   # Transcoded frames ready for Discord

        self._running = True
        self._ogg_buffer = b''
        self._started_playback = False
        self._consecutive_underruns = 0

    def setup_direct_callback(self):
        """
        Set up callback that just queues raw data (no processing).
        Uses sync callback to avoid async scheduling overhead.
        """
        def sync_audio_callback(audio_data: bytes):
            self.raw_ogg_queue.put(audio_data)

        self.moshi_session.client.set_sync_audio_callback(sync_audio_callback)
    
    def _process_raw_queue(self):
        """
        Process raw Ogg data from queue and transcode to Discord frames.
        Called from Discord's player thread (read() method).
        """
        from utils.ogg_opus_parser import extract_opus_packets
        import queue as queue_module
        
        # Drain all available raw data
        while True:
            try:
                raw_data = self.raw_ogg_queue.get_nowait()
                self._ogg_buffer += raw_data
            except queue_module.Empty:
                break
        
        # Process complete Ogg pages
        while len(self._ogg_buffer) >= 27:
            ogg_start = self._ogg_buffer.find(b'OggS')
            if ogg_start < 0:
                self._ogg_buffer = b''
                break
            elif ogg_start > 0:
                self._ogg_buffer = self._ogg_buffer[ogg_start:]
            
            if len(self._ogg_buffer) < 27:
                break
            
            num_segments = self._ogg_buffer[26]
            header_size = 27 + num_segments
            
            if len(self._ogg_buffer) < header_size:
                break
            
            page_size = header_size + sum(self._ogg_buffer[27:header_size])
            
            if len(self._ogg_buffer) < page_size:
                break
            
            page = self._ogg_buffer[:page_size]
            self._ogg_buffer = self._ogg_buffer[page_size:]
            
            # Extract and transcode (this is CPU work, but we're in player thread)
            opus_packets = extract_opus_packets(page)
            
            for packet in opus_packets:
                frames = self.transcoder.moshi_to_discord_all(packet)
                for frame in frames:
                    self.opus_packets.put(frame)

    async def start_receive_task(self):
        """Start audio processing - sets up direct callback"""
        try:
            self.setup_direct_callback()
            await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"Error setting up audio callback: {e}", exc_info=True)

    def read(self) -> bytes:
        """
        Read Opus packet for Discord playback with minimal jitter buffering
        Called by Discord to get next Opus frame at 50fps
        Also processes raw Ogg data since we're in a separate thread.

        Returns:
            Opus packet bytes (or silence frame if no data)
        """
        import queue
        
        # Process any pending raw Ogg data (transcoding happens here, in player thread)
        self._process_raw_queue()
        
        current_size = self.opus_packets.qsize()
        
        # Only buffer at the very start - wait for first few frames
        if not self._started_playback:
            if current_size >= JITTER_BUFFER_MIN_FRAMES:
                self._started_playback = True
            else:
                return b'\xF8\xFF\xFE'
        
        try:
            packet = self.opus_packets.get_nowait()
            self._consecutive_underruns = 0
            return packet

        except queue.Empty:
            self._consecutive_underruns += 1
            return b'\xF8\xFF\xFE'

    def is_opus(self) -> bool:
        """We provide Opus-encoded audio"""
        return True

    def cleanup(self):
        """Cleanup resources"""
        self._running = False


class MoshiVoiceHandler:
    """
    Manages Moshi voice conversation for a Discord guild
    """

    def __init__(self, guild_id: int):
        """
        Initialize voice handler

        Args:
            guild_id: Discord guild ID
        """
        self.guild_id = guild_id
        self.moshi_session: Optional[MoshiSession] = None
        self.audio_sink: Optional[MoshiAudioSink] = None
        self.audio_source: Optional[MoshiAudioSource] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.transcoder: Optional[OpusTranscoder] = None
        self.active = False

    async def start(self, voice_client: discord.VoiceClient, custom_prompt: Optional[str] = None) -> bool:
        """
        Start Moshi voice conversation

        Args:
            voice_client: Discord voice client
            custom_prompt: Optional custom prompt for this session

        Returns:
            bool: True if started successfully
        """
        try:
            # Start Moshi session with custom prompt
            self.moshi_session = await start_moshi_session(self.guild_id, custom_prompt)
            if not self.moshi_session:
                logger.error("Failed to start Moshi session")
                return False

            self.voice_client = voice_client
            loop = asyncio.get_event_loop()

            # Initialize Opus transcoder for sample rate conversion
            self.transcoder = OpusTranscoder()

            # Create audio sink to capture user voice
            self.audio_sink = MoshiAudioSink(self.guild_id, self.moshi_session, loop, self.transcoder)
            voice_client.listen(self.audio_sink)

            # Create audio source to play Moshi's responses
            self.audio_source = MoshiAudioSource(self.guild_id, self.moshi_session, self.transcoder)
            await self.audio_source.start_receive_task()

            # Start playing Moshi's audio
            voice_client.play(self.audio_source, after=self._on_playback_error)

            self.active = True
            logger.info(f"Moshi voice started for guild {self.guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting Moshi voice handler: {e}", exc_info=True)
            await self.stop()
            return False

    async def stop(self):
        """Stop Moshi voice conversation"""
        try:
            self.active = False

            # Stop listening
            if self.voice_client and hasattr(self.voice_client, 'stop_listening'):
                self.voice_client.stop_listening()

            # Stop playback
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()

            # Cleanup audio components
            if self.audio_sink:
                self.audio_sink.cleanup()
                self.audio_sink = None

            if self.audio_source:
                self.audio_source.cleanup()
                self.audio_source = None

            # Cleanup transcoder
            if self.transcoder:
                self.transcoder.cleanup()
                self.transcoder = None

            # Stop Moshi session
            if self.moshi_session:
                await stop_moshi_session(self.guild_id)
                self.moshi_session = None

            logger.info(f"Moshi voice stopped for guild {self.guild_id}")

        except Exception as e:
            logger.error(f"Error stopping Moshi voice handler: {e}")

    def _on_playback_error(self, exc: Optional[Exception]):
        """Callback for playback errors"""
        if exc:
            logger.error(f"Playback error: {exc}")


# Global handler manager
_active_handlers: dict[int, MoshiVoiceHandler] = {}


async def start_moshi_voice(guild_id: int, voice_client: discord.VoiceClient) -> bool:
    """
    Start Moshi voice conversation for a guild

    Args:
        guild_id: Discord guild ID
        voice_client: Discord voice client

    Returns:
        bool: True if started successfully
    """
    # Stop existing handler if any
    if guild_id in _active_handlers:
        await stop_moshi_voice(guild_id)

    # Get guild-specific prompt or use default
    custom_prompt = get_guild_setting(guild_id, "moshi_prompt", MOSHI_TEXT_PROMPT)

    handler = MoshiVoiceHandler(guild_id)
    success = await handler.start(voice_client, custom_prompt)

    if success:
        _active_handlers[guild_id] = handler
        return True

    return False


async def stop_moshi_voice(guild_id: int):
    """
    Stop Moshi voice conversation for a guild

    Args:
        guild_id: Discord guild ID
    """
    handler = _active_handlers.pop(guild_id, None)
    if handler:
        await handler.stop()


def is_moshi_active(guild_id: int) -> bool:
    """
    Check if Moshi is active for a guild

    Args:
        guild_id: Discord guild ID

    Returns:
        bool: True if Moshi is active and connected
    """
    handler = _active_handlers.get(guild_id)
    if handler is None or not handler.active:
        return False

    # Also verify the Moshi client is actually connected
    if handler.moshi_session and handler.moshi_session.client:
        return handler.moshi_session.client.connected

    return False
