"""
Ogg/Opus writer for streaming audio to Moshi
Based on RFC 7845 (Ogg Encapsulation for Opus) and RFC 3533 (Ogg Bitstream)

This implementation focuses on compatibility with sphn.OpusStreamReader
"""

import logging
import struct
import os

logger = logging.getLogger(__name__)


class OggOpusWriterV2:
    """
    Writes Opus packets into Ogg container format for streaming to Moshi.
    Compatible with sphn.OpusStreamReader used by Moshi server.
    """
    
    # Ogg CRC32 lookup table (polynomial 0x04C11DB7)
    _crc_table = None
    
    @classmethod
    def _init_crc_table(cls):
        """Initialize CRC32 lookup table for Ogg"""
        if cls._crc_table is not None:
            return
        cls._crc_table = []
        for i in range(256):
            crc = i << 24
            for _ in range(8):
                if crc & 0x80000000:
                    crc = (crc << 1) ^ 0x04C11DB7
                else:
                    crc <<= 1
            cls._crc_table.append(crc & 0xFFFFFFFF)
    
    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        """
        Initialize Ogg/Opus writer
        
        Args:
            sample_rate: Sample rate in Hz (24000 for Moshi)
            channels: Number of channels (1 for mono)
        """
        self._init_crc_table()
        
        self.sample_rate = sample_rate
        self.channels = channels
        
        # Random serial number for this stream
        self.serial_number = struct.unpack('<I', os.urandom(4))[0]
        
        # State
        self.page_sequence = 0
        self.granule_position = 0
        self.pre_skip = 312  # Standard Opus encoder delay at 48kHz
        self.headers_written = False
        
    def _crc32(self, data: bytes) -> int:
        """Calculate Ogg CRC32 checksum"""
        crc = 0
        for byte in data:
            crc = ((crc << 8) ^ self._crc_table[((crc >> 24) ^ byte) & 0xFF]) & 0xFFFFFFFF
        return crc
    
    def _make_page(self, segments: list[bytes], bos: bool = False, eos: bool = False, 
                   granule: int = None) -> bytes:
        """
        Create an Ogg page containing the given segments
        
        Args:
            segments: List of segment data (max 255 bytes each)
            bos: Beginning of stream flag
            eos: End of stream flag  
            granule: Granule position (None = 0 for header pages)
            
        Returns:
            Complete Ogg page bytes
        """
        # Build segment table
        segment_table = b''
        payload = b''
        for seg in segments:
            seg_len = len(seg)
            # Each segment can be up to 255 bytes
            while seg_len >= 255:
                segment_table += bytes([255])
                seg_len -= 255
            segment_table += bytes([seg_len])
            payload += seg
        
        # Header type flags
        header_type = 0
        if bos:
            header_type |= 0x02
        if eos:
            header_type |= 0x04
        
        # Granule position (0 for header pages, sample count for audio)
        if granule is None:
            granule = 0
        
        # Build page header (without CRC)
        header = struct.pack(
            '<4sBBQIII',
            b'OggS',                    # Capture pattern
            0,                          # Version
            header_type,                # Header type
            granule,                    # Granule position
            self.serial_number,         # Bitstream serial number
            self.page_sequence,         # Page sequence number
            0                           # CRC placeholder
        )
        
        # Number of segments
        header += bytes([len(segment_table)])
        
        # Build full page without CRC
        page = header + segment_table + payload
        
        # Calculate and insert CRC (at offset 22)
        crc = self._crc32(page)
        page = page[:22] + struct.pack('<I', crc) + page[26:]
        
        self.page_sequence += 1
        return page
    
    def get_opus_head(self) -> bytes:
        """Create OpusHead identification header page"""
        # OpusHead packet (RFC 7845 Section 5.1)
        opus_head = struct.pack(
            '<8sBBHIhB',
            b'OpusHead',           # Magic signature
            1,                     # Version
            self.channels,         # Channel count
            self.pre_skip,         # Pre-skip (encoder delay)
            self.sample_rate,      # Input sample rate
            0,                     # Output gain (dB, Q7.8)
            0                      # Channel mapping family
        )
        
        return self._make_page([opus_head], bos=True, granule=0)
    
    def get_opus_tags(self) -> bytes:
        """Create OpusTags comment header page"""
        vendor = b'DiscordBot'
        
        # OpusTags packet (RFC 7845 Section 5.2)
        opus_tags = struct.pack('<8sI', b'OpusTags', len(vendor))
        opus_tags += vendor
        opus_tags += struct.pack('<I', 0)  # No user comments
        
        return self._make_page([opus_tags], granule=0)
    
    def get_headers(self) -> list[bytes]:
        """
        Get the required header pages for a new Ogg/Opus stream
        
        Returns:
            List of [OpusHead page, OpusTags page]
        """
        if self.headers_written:
            return []
        
        self.headers_written = True
        return [self.get_opus_head(), self.get_opus_tags()]
    
    def write_opus_packet(self, opus_packet: bytes, samples: int = 960) -> bytes:
        """
        Wrap an Opus packet in an Ogg page
        
        Args:
            opus_packet: Raw Opus packet bytes
            samples: Number of samples in the packet at 48kHz (default 960 = 20ms)
            
        Returns:
            Ogg page containing the Opus packet
        """
        # Update granule position (in 48kHz samples, as per RFC 7845)
        # Note: Opus always uses 48kHz internally for granule position
        self.granule_position += samples
        
        return self._make_page([opus_packet], granule=self.granule_position)
    
    def reset(self):
        """Reset for a new stream"""
        self.serial_number = struct.unpack('<I', os.urandom(4))[0]
        self.page_sequence = 0
        self.granule_position = 0
        self.headers_written = False


# Quick test
if __name__ == '__main__':
    writer = OggOpusWriterV2(24000, 1)
    
    # Get headers
    headers = writer.get_headers()
    print(f"Headers: {len(headers)} pages")
    for i, h in enumerate(headers):
        print(f"  Page {i}: {len(h)} bytes, hex: {h[:30].hex()}")
    
    # Fake Opus packet (silence marker)
    fake_opus = bytes([0xF8, 0xFF, 0xFE])  # Opus DTX/silence
    page = writer.write_opus_packet(fake_opus, samples=960)
    print(f"Audio page: {len(page)} bytes, hex: {page[:30].hex()}")
