"""
Opus audio transcoding utilities
Handles conversion between different Opus sample rates (48kHz <-> 24kHz)
Uses discord.py's built-in Opus support for Discord audio
Uses PyAV for 24kHz Opus encoding for Moshi
"""

import logging
import discord.opus
import av
import struct
import io
from fractions import Fraction
from typing import Optional

logger = logging.getLogger(__name__)

# Sample rates
DISCORD_SAMPLE_RATE = 48000  # Discord uses 48kHz
MOSHI_SAMPLE_RATE = 24000    # Moshi uses 24kHz

# Frame sizes (20ms of audio)
DISCORD_FRAME_SIZE = 960   # 20ms at 48kHz = 960 samples
MOSHI_FRAME_SIZE = 480     # 20ms at 24kHz = 480 samples

# Channels
DISCORD_CHANNELS = 2  # Stereo
MOSHI_CHANNELS = 1    # Mono


class OpusTranscoder:
    """
    Transcodes Opus audio between Discord (48kHz stereo) and Moshi (24kHz mono) formats
    Uses discord.opus for Discord audio and PyAV for Moshi audio
    """

    def __init__(self):
        """Initialize Opus encoder and decoder"""
        try:
            # Load Opus library (discord.py includes it via PyNaCl)
            if not discord.opus.is_loaded():
                try:
                    discord.opus.load_opus('opus')
                except:
                    pass
            
            # Discord's 48kHz stereo decoder and encoder
            self.discord_decoder = discord.opus.Decoder()
            self.discord_encoder = discord.opus.Encoder()
            
            # PyAV codec for encoding to 24kHz Opus (persistent, stateful)
            self.moshi_encoder = av.CodecContext.create('opus', 'w')
            self.moshi_encoder.rate = MOSHI_SAMPLE_RATE
            self.moshi_encoder.layout = 'mono'
            self.moshi_encoder.format = av.AudioFormat('s16')
            self.moshi_encoder.bit_rate = 24000
            self.moshi_encoder.time_base = Fraction(1, MOSHI_SAMPLE_RATE)
            self.moshi_encoder.open()
            self._pts = 0  # Track presentation timestamp
            
            # PyAV codec for decoding Moshi's Opus (persistent, stateful)
            # Opus always decodes to 48kHz internally
            self.moshi_decoder = av.CodecContext.create('opus', 'r')
            self.moshi_decoder.rate = DISCORD_SAMPLE_RATE  # 48kHz output
            self.moshi_decoder.layout = 'mono'
            self.moshi_decoder.open()
            
            # PCM buffer for frame splitting
            self._pcm_buffer = b''
            
            logger.info("OpusTranscoder initialized successfully using discord.opus and PyAV")

        except Exception as e:
            logger.error(f"Failed to initialize OpusTranscoder: {e}", exc_info=True)
            raise

    def discord_to_moshi(self, opus_packet: bytes) -> Optional[bytes]:
        """
        Convert Discord's 48kHz stereo Opus to Moshi's 24kHz mono Opus (raw packet)

        Args:
            opus_packet: Opus packet from Discord (48kHz stereo)

        Returns:
            Raw Opus packet for Moshi (24kHz mono), or None if conversion fails
        """
        try:
            # Step 1: Decode Discord's 48kHz stereo Opus to PCM
            pcm_48k_stereo = self.discord_decoder.decode(opus_packet)

            # Step 2: Resample from 48kHz to 24kHz and convert stereo to mono
            pcm_24k_mono = self._resample_and_mono(pcm_48k_stereo)

            # Step 3: Encode to 24kHz mono Opus (raw packet)
            opus_24k = self._encode_opus_24k(pcm_24k_mono)

            return opus_24k

        except Exception as e:
            # Decoder may have lost sync - try to recover by recreating it
            if "corrupted" in str(e).lower() or "invalid" in str(e).lower():
                try:
                    logger.warning(f"Discord Opus decoder corrupted, recreating...")
                    self.discord_decoder = discord.opus.Decoder()
                except Exception as re:
                    logger.error(f"Failed to recreate decoder: {re}")
            else:
                logger.error(f"Error transcoding Discord to Moshi: {e}")
            return None

    def moshi_to_discord(self, opus_packet: bytes) -> Optional[bytes]:
        """
        Convert Moshi's Opus to Discord's 48kHz stereo Opus
        
        NOTE: Moshi sends 80ms frames. Opus decodes to 48kHz regardless of encoding rate.
        Discord expects 20ms frames (960 samples at 48kHz stereo).
        This method returns ONE 20ms frame and buffers the rest.
        Call repeatedly until it returns None to get all frames.

        Args:
            opus_packet: Opus packet from Moshi, or None to drain buffer

        Returns:
            Opus packet for Discord (48kHz stereo), or None if no more data
        """
        try:
            # Check if we have buffered PCM data from previous call
            if not hasattr(self, '_pcm_buffer'):
                self._pcm_buffer = b''
            
            # If we have a new packet, decode and add to buffer
            if opus_packet is not None:
                # Step 1: Decode Moshi's Opus to PCM (outputs 48kHz mono)
                pcm_48k_mono = self._decode_opus_24k(opus_packet)
                
                if not pcm_48k_mono:
                    # Decode failed - try to continue with buffered data
                    if len(self._pcm_buffer) == 0:
                        return None
                else:
                    # Step 2: Convert mono to stereo (just duplicate channels)
                    pcm_48k_stereo = self._mono_to_stereo(pcm_48k_mono)
                    self._pcm_buffer += pcm_48k_stereo
            
            # Discord expects exactly 960 samples per channel (20ms at 48kHz)
            # That's 960 * 2 channels * 2 bytes = 3840 bytes
            expected_bytes = DISCORD_FRAME_SIZE * 4  # stereo int16
            
            if len(self._pcm_buffer) < expected_bytes:
                # Not enough data for a frame
                return None
            
            # Extract one 20ms frame
            frame_pcm = self._pcm_buffer[:expected_bytes]
            self._pcm_buffer = self._pcm_buffer[expected_bytes:]

            # Step 3: Encode to 48kHz stereo Opus for Discord
            try:
                opus_48k = self.discord_encoder.encode(frame_pcm, DISCORD_FRAME_SIZE)
                return opus_48k
            except Exception as enc_err:
                # Encoder error - try to recreate it
                logger.warning(f"Discord encoder error, recreating: {enc_err}")
                try:
                    self.discord_encoder = discord.opus.Encoder()
                    opus_48k = self.discord_encoder.encode(frame_pcm, DISCORD_FRAME_SIZE)
                    return opus_48k
                except:
                    return None

        except Exception as e:
            logger.error(f"Error transcoding Moshi to Discord: {e}", exc_info=True)
            return None
    
    def moshi_to_discord_all(self, opus_packet: bytes) -> list[bytes]:
        """
        Convert Moshi's 24kHz mono Opus to multiple Discord 48kHz stereo Opus frames.
        Moshi sends 80ms frames, Discord needs 20ms frames, so this returns up to 4 frames.
        
        Args:
            opus_packet: Opus packet from Moshi (24kHz mono)
            
        Returns:
            List of Opus packets for Discord (48kHz stereo)
        """
        frames = []
        
        # First call decodes the packet and returns first frame
        frame = self.moshi_to_discord(opus_packet)
        while frame is not None:
            frames.append(frame)
            # Subsequent calls drain the buffer
            frame = self.moshi_to_discord(None)
        
        # Log frame count for debugging (first few times)
        if not hasattr(self, '_frame_log_count'):
            self._frame_log_count = 0
        self._frame_log_count += 1
        if self._frame_log_count <= 5:
            logger.info(f"moshi_to_discord_all: {len(opus_packet)} bytes -> {len(frames)} Discord frames")
        
        return frames

    def _resample_and_mono(self, pcm_48k_stereo: bytes) -> bytes:
        """
        Resample 48kHz stereo PCM to 24kHz mono PCM
        Uses simple decimation (take every other sample) and channel averaging

        Args:
            pcm_48k_stereo: PCM int16 data at 48kHz stereo

        Returns:
            PCM int16 data at 24kHz mono
        """
        import struct

        # Convert bytes to int16 samples
        num_samples = len(pcm_48k_stereo) // 2
        samples = struct.unpack(f'{num_samples}h', pcm_48k_stereo)

        # Process in stereo pairs
        mono_24k = []

        # Decimation: take every other frame (48kHz -> 24kHz is 2:1)
        # Also convert stereo to mono by averaging channels
        for i in range(0, len(samples), 4):  # Step by 4 (2 stereo pairs)
            if i + 1 < len(samples):
                # Average left and right channels of first pair
                mono_sample = (samples[i] + samples[i + 1]) // 2
                mono_24k.append(mono_sample)

        # Convert back to bytes
        return struct.pack(f'{len(mono_24k)}h', *mono_24k)

    def _mono_to_stereo(self, pcm_mono: bytes) -> bytes:
        """
        Convert mono PCM to stereo PCM by duplicating channels
        
        Args:
            pcm_mono: PCM int16 mono data
            
        Returns:
            PCM int16 stereo data (interleaved L, R, L, R, ...)
        """
        import struct
        
        # Convert bytes to int16 samples
        num_samples = len(pcm_mono) // 2
        samples = struct.unpack(f'{num_samples}h', pcm_mono)
        
        # Duplicate each sample for left and right channels
        stereo = []
        for sample in samples:
            stereo.append(sample)  # Left
            stereo.append(sample)  # Right
        
        return struct.pack(f'{len(stereo)}h', *stereo)

    def _resample_and_stereo(self, pcm_24k_mono: bytes) -> bytes:
        """
        Resample 24kHz mono PCM to 48kHz stereo PCM
        Uses simple sample duplication (24kHz -> 48kHz is 1:2)

        Args:
            pcm_24k_mono: PCM int16 data at 24kHz mono

        Returns:
            PCM int16 data at 48kHz stereo
        """
        import struct

        # Convert bytes to int16 samples
        num_samples = len(pcm_24k_mono) // 2
        samples = struct.unpack(f'{num_samples}h', pcm_24k_mono)

        # Upsample and convert to stereo
        stereo_48k = []

        for sample in samples:
            # Duplicate each sample twice (24kHz -> 48kHz)
            # and duplicate to both channels (mono -> stereo)
            stereo_48k.append(sample)  # Left channel, first copy
            stereo_48k.append(sample)  # Right channel, first copy
            stereo_48k.append(sample)  # Left channel, second copy
            stereo_48k.append(sample)  # Right channel, second copy

        # Convert back to bytes
        return struct.pack(f'{len(stereo_48k)}h', *stereo_48k)

    def _encode_opus_24k(self, pcm_data: bytes) -> Optional[bytes]:
        """
        Encode PCM int16 audio to 24kHz mono Opus using PyAV
        Returns raw Opus packet (not Ogg-wrapped)
        Uses persistent codec context for proper state management
        
        Args:
            pcm_data: PCM int16 data at 24kHz mono
            
        Returns:
            Raw Opus-encoded bytes or None if encoding fails
        """
        try:
            # Convert PCM bytes to AudioFrame
            num_samples = len(pcm_data) // 2
            frame = av.AudioFrame(format='s16', layout='mono', samples=num_samples)
            frame.sample_rate = MOSHI_SAMPLE_RATE
            frame.planes[0].update(pcm_data)
            frame.pts = self._pts
            self._pts += num_samples  # Increment PTS for next frame
            
            # Encode frame using persistent codec
            packets = list(self.moshi_encoder.encode(frame))
            
            if packets:
                # Return the first packet's raw bytes
                return bytes(packets[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error encoding Opus at 24kHz: {e}", exc_info=True)
            return None

    def _decode_opus_24k(self, opus_data: bytes) -> Optional[bytes]:
        """
        Decode Moshi's Opus to PCM int16 using persistent PyAV decoder
        Handles raw Opus packets (not Ogg-wrapped)
        
        Args:
            opus_data: Raw Opus-encoded bytes
            
        Returns:
            PCM int16 bytes at 48kHz mono, or None if decoding fails
        """
        try:
            # Create packet from raw Opus data
            packet = av.Packet(opus_data)
            
            # Decode packet using persistent decoder
            frames = list(self.moshi_decoder.decode(packet))
            
            if frames:
                # Convert first frame to PCM int16 bytes
                frame = frames[0]
                
                # Log actual sample rate for debugging (once)
                if not hasattr(self, '_logged_decode_info'):
                    self._logged_decode_info = True
                    logger.info(f"Opus decode: rate={frame.sample_rate}Hz, samples={frame.samples}, layout={frame.layout}")
                
                # Get audio data as numpy array and convert to int16
                audio_array = frame.to_ndarray()
                # Opus decodes to float, convert to int16
                if audio_array.dtype != 'int16':
                    import numpy as np
                    audio_array = (audio_array * 32767).astype(np.int16)
                pcm_data = audio_array.tobytes()
                return pcm_data
            
            return None
            
        except Exception as e:
            # Try to recover by recreating decoder
            if not hasattr(self, '_decode_error_count'):
                self._decode_error_count = 0
            self._decode_error_count += 1
            
            if self._decode_error_count <= 3:
                logger.warning(f"Opus decode error #{self._decode_error_count}, recreating decoder: {e}")
            
            try:
                self.moshi_decoder = av.CodecContext.create('opus', 'r')
                self.moshi_decoder.rate = DISCORD_SAMPLE_RATE
                self.moshi_decoder.layout = 'mono'
                self.moshi_decoder.open()
            except:
                pass
            
            return None

    def cleanup(self):
        """Cleanup encoder/decoder resources"""
        try:
            # Cleanup decoders and encoders
            if hasattr(self, 'discord_decoder'):
                del self.discord_decoder
            if hasattr(self, 'discord_encoder'):
                del self.discord_encoder
            if hasattr(self, 'moshi_decoder'):
                del self.moshi_decoder
            if hasattr(self, 'moshi_encoder'):
                del self.moshi_encoder

            logger.info("OpusTranscoder cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up OpusTranscoder: {e}")
