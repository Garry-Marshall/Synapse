"""
Ogg/Opus parser to extract Opus packets from Ogg container
Moshi sends Opus audio wrapped in Ogg containers
"""

import logging
import struct

logger = logging.getLogger(__name__)

# Module-level counter for reduced logging
_parse_count = 0


def extract_opus_packets(ogg_data: bytes) -> list[bytes]:
    """
    Extract Opus packets from Ogg container

    Ogg pages can contain one or more Opus packets.
    Segments in the segment table represent packet boundaries:
    - Segments < 255 bytes end a packet
    - Segments == 255 bytes continue the packet

    Args:
        ogg_data: Ogg container bytes

    Returns:
        List of Opus packet bytes
    """
    global _parse_count
    _parse_count += 1
    
    packets = []
    offset = 0
    page_num = 0
    should_log = _parse_count <= 3 or _parse_count % 50 == 0

    try:
        while offset < len(ogg_data):
            # Check for OggS signature
            if offset + 4 > len(ogg_data):
                break

            if ogg_data[offset:offset+4] != b'OggS':
                # Not an Ogg page, skip
                if should_log:
                    logger.debug(f"No OggS signature at offset {offset}")
                break

            page_num += 1

            # Parse Ogg page header (27 bytes minimum)
            if offset + 27 > len(ogg_data):
                break

            version = ogg_data[offset + 4]
            header_type = ogg_data[offset + 5]
            num_segments = ogg_data[offset + 26]

            # Read segment table
            segment_table_offset = offset + 27
            if segment_table_offset + num_segments > len(ogg_data):
                break

            segment_table = list(ogg_data[segment_table_offset:segment_table_offset + num_segments])

            # Calculate total payload size
            payload_size = sum(segment_table)

            # Extract payload
            payload_offset = segment_table_offset + num_segments
            if payload_offset + payload_size > len(ogg_data):
                logger.warning(f"Page {page_num}: payload extends beyond data (need {payload_offset + payload_size}, have {len(ogg_data)})")
                break

            payload = ogg_data[payload_offset:payload_offset + payload_size]

            # Skip Opus header/tag pages
            if payload.startswith(b'OpusHead'):
                logger.debug(f"Page {page_num}: OpusHead (skipping)")
                offset = payload_offset + payload_size
                continue
            elif payload.startswith(b'OpusTags'):
                logger.debug(f"Page {page_num}: OpusTags (skipping)")
                offset = payload_offset + payload_size
                continue

            # Parse segments into individual Opus packets
            # Segments form packets: a packet ends when segment size < 255
            segment_offset = 0
            current_packet = bytearray()

            for i, segment_size in enumerate(segment_table):
                # Append segment data to current packet
                segment_data = payload[segment_offset:segment_offset + segment_size]
                current_packet.extend(segment_data)
                segment_offset += segment_size

                # If segment < 255 bytes, packet is complete
                if segment_size < 255:
                    if len(current_packet) > 0:
                        packets.append(bytes(current_packet))
                    current_packet = bytearray()

            # If there's remaining data (all segments were 255), it's also a packet
            if len(current_packet) > 0:
                packets.append(bytes(current_packet))

            # Move to next Ogg page
            offset = payload_offset + payload_size

        if should_log:
            logger.debug(f"Extracted {len(packets)} Opus packets from {page_num} Ogg pages")

    except Exception as e:
        logger.error(f"Error parsing Ogg container: {e}", exc_info=True)

    return packets
