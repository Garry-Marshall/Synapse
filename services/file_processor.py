"""
File processing service for Discord attachments.
Handles images, PDFs, and text files.
"""
import base64
import io
import logging
from typing import Optional, List, Dict

from pypdf import PdfReader

from config import (
    ALLOW_IMAGES,
    MAX_IMAGE_SIZE,
    ALLOW_TEXT_FILES,
    MAX_TEXT_FILE_SIZE,
    ALLOW_PDF,
    MAX_PDF_SIZE,
    TEXT_FILE_EXTENSIONS,
    FILE_ENCODINGS,
    MAX_PDF_CHARS
)

logger = logging.getLogger(__name__)


async def process_image_attachment(attachment, channel) -> Optional[Dict]:
    """
    Download and convert an image attachment to base64 for the vision model.
    
    Args:
        attachment: Discord attachment object
        channel: Discord channel (for error messages)
        
    Returns:
        Dictionary with image data, or None if failed/rejected
    """
    if not ALLOW_IMAGES:
        return None
    
    if not attachment.content_type or not attachment.content_type.startswith('image/'):
        return None
    
    if attachment.size > MAX_IMAGE_SIZE * 1024 * 1024:
        logger.warning(f"Image too large: {attachment.size / (1024*1024):.2f}MB (max: {MAX_IMAGE_SIZE}MB)")
        await channel.send(
            f"⚠️ Image **{attachment.filename}** is too large "
            f"({attachment.size / (1024*1024):.2f}MB). Maximum size is {MAX_IMAGE_SIZE}MB."
        )
        return None
    
    try:
        image_data = await attachment.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine media type
        media_type = attachment.content_type.lower().strip()
        
        if 'png' in media_type or attachment.filename.lower().endswith('.png'):
            media_type = 'image/png'
        elif 'jpeg' in media_type or 'jpg' in media_type or attachment.filename.lower().endswith(('.jpg', '.jpeg')):
            media_type = 'image/jpeg'
        elif 'gif' in media_type or attachment.filename.lower().endswith('.gif'):
            media_type = 'image/gif'
        elif 'webp' in media_type or attachment.filename.lower().endswith('.webp'):
            media_type = 'image/webp'
        else:
            logger.warning(f"Unknown image type '{attachment.content_type}', defaulting to image/jpeg")
            media_type = 'image/jpeg'
        
        logger.info(f"Processing image: {attachment.filename} ({attachment.size / 1024:.2f}KB, {media_type})")
        
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{base64_image}"
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing image {attachment.filename}: {e}")
        await channel.send(f"❌ Failed to process image **{attachment.filename}**: {str(e)}")
        return None


async def process_text_attachment(attachment, channel) -> Optional[str]:
    """
    Download and read a text file attachment.
    
    Args:
        attachment: Discord attachment object
        channel: Discord channel (for error messages)
        
    Returns:
        Formatted text content, or None if not a text file/failed
    """
    if not ALLOW_TEXT_FILES:
        return None
    
    filename_lower = attachment.filename.lower()
    
    # Check if it's a text file
    is_text = any(filename_lower.endswith(ext) for ext in TEXT_FILE_EXTENSIONS)
    if attachment.content_type:
        is_text = is_text or 'text/' in attachment.content_type or 'application/json' in attachment.content_type
    
    if not is_text:
        return None
    
    if attachment.size > MAX_TEXT_FILE_SIZE * 1024 * 1024:
        logger.warning(f"Text file too large: {attachment.size / (1024*1024):.2f}MB (max: {MAX_TEXT_FILE_SIZE}MB)")
        await channel.send(
            f"⚠️ Text file **{attachment.filename}** is too large "
            f"({attachment.size / (1024*1024):.2f}MB). Maximum size is {MAX_TEXT_FILE_SIZE}MB."
        )
        return None
    
    try:
        file_data = await attachment.read()
        
        # Try different encodings
        for encoding in FILE_ENCODINGS:
            try:
                text_content = file_data.decode(encoding)
                logger.info(f"Processing text file: {attachment.filename} ({attachment.size / 1024:.2f}KB)")
                return f"\n\n--- Content of {attachment.filename} ---\n{text_content}\n--- End of {attachment.filename} ---\n"
            except UnicodeDecodeError:
                continue
        
        # If all encodings failed
        logger.error(f"Could not decode text file {attachment.filename}")
        await channel.send(
            f"❌ Could not decode text file **{attachment.filename}**. "
            f"Please ensure it's a valid text file."
        )
        return None
        
    except Exception as e:
        logger.error(f"Error processing text file {attachment.filename}: {e}")
        await channel.send(f"❌ Failed to process text file **{attachment.filename}**: {str(e)}")
        return None


async def process_pdf_attachment(attachment, channel) -> Optional[str]:
    """
    Download and extract text from a PDF with character truncation.
    
    Args:
        attachment: Discord attachment object
        channel: Discord channel (for error messages)
        
    Returns:
        Formatted PDF text content, or None if failed
    """
    if not ALLOW_PDF:
        return None
    
    # Check if it's a PDF
    is_pdf = attachment.filename.lower().endswith('.pdf') or attachment.content_type == 'application/pdf'
    if not is_pdf:
        return None
    
    if attachment.size > MAX_PDF_SIZE * 1024 * 1024:
        logger.warning(f"PDF too large: {attachment.size / (1024*1024):.2f}MB (max: {MAX_PDF_SIZE}MB)")
        await channel.send(
            f"⚠️ PDF **{attachment.filename}** is too large "
            f"({attachment.size / (1024*1024):.2f}MB). Maximum size is {MAX_PDF_SIZE}MB."
        )
        return None
    
    try:
        file_data = await attachment.read()
        pdf_stream = io.BytesIO(file_data)
        reader = PdfReader(pdf_stream)
        
        extracted_text = []
        current_length = 0
        
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                # Check if adding this page exceeds our limit
                if current_length + len(page_text) > MAX_PDF_CHARS:
                    remaining_space = MAX_PDF_CHARS - current_length
                    extracted_text.append(f"--- Page {i+1} (TRUNCATED) ---\n{page_text[:remaining_space]}")
                    logger.info(f"✂️ PDF {attachment.filename} truncated at page {i+1}")
                    break
                
                extracted_text.append(f"--- Page {i+1} ---\n{page_text}")
                current_length += len(page_text)
        
        if not extracted_text:
            return f"\n[Note: PDF {attachment.filename} had no extractable text.]\n"

        full_content = "\n".join(extracted_text)
        logger.info(f"Processing PDF: {attachment.filename} ({len(full_content)} chars extracted)")
        return f"\n\n--- Content of PDF: {attachment.filename} ---\n{full_content}\n--- End of PDF ---\n"
        
    except Exception as e:
        logger.error(f"Error processing PDF {attachment.filename}: {e}")
        await channel.send(f"❌ Failed to process PDF **{attachment.filename}**: {str(e)}")
        return None


async def process_all_attachments(attachments, channel) -> tuple[List[Dict], str]:
    """
    Process all attachments in a message.
    
    Args:
        attachments: List of Discord attachment objects
        channel: Discord channel (for error messages)
        
    Returns:
        Tuple of (images_list, text_content_string)
    """
    images = []
    text_files_content = ""
    
    for attachment in attachments:
        # Try image processing
        image_data = await process_image_attachment(attachment, channel)
        if image_data:
            images.append(image_data)
            continue  # Don't process as other types if it's an image
        
        # Try PDF processing
        pdf_content = await process_pdf_attachment(attachment, channel)
        if pdf_content:
            text_files_content += pdf_content
            continue
        
        # Try text file processing
        text_content = await process_text_attachment(attachment, channel)
        if text_content:
            text_files_content += text_content
    
    return images, text_files_content