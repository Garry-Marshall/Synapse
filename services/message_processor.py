"""
Message processing service.
Handles the business logic for processing Discord messages and generating responses.
"""
import time
import logging
import asyncio
from typing import Optional, Dict, Tuple

import discord

from config.settings import CONTEXT_MESSAGES, ENABLE_TTS
from config.constants import MSG_PROCESSING_ATTACHMENTS, MSG_LOADING_CONTEXT, MSG_WRITING_RESPONSE, DISCORD_SAFE_DISPLAY_LIMIT

from utils.text_utils import remove_thinking_tags, is_inside_thinking_tags, split_message
from utils.logging_config import guild_debug_log
from utils.settings_manager import is_tts_enabled_for_guild, get_guild_voice, is_search_enabled
from utils.stats_manager import add_message_to_history, update_stats, is_context_loaded, set_context_loaded, get_conversation_history

from services.lmstudio import stream_completion
from services.content_fetch import process_message_urls
from services.file_processor import process_all_attachments
from services.search import should_trigger_search, check_search_cooldown, get_web_context, update_search_cooldown
from services.tts import text_to_speech

from commands.voice import get_voice_client


logger = logging.getLogger(__name__)


class MessageProcessor:
    """Handles processing of Discord messages and response generation."""

    @staticmethod
    async def process_message_attachments(
        message: discord.Message,
        status_msg: discord.Message,
        edit_tracker: Dict,
        guild_id: Optional[int]
    ) -> Tuple[list, str, int]:
        """
        Process message attachments (images and files).

        Args:
            message: Discord message object
            status_msg: Status message to update
            edit_tracker: Edit tracking dict
            guild_id: Guild ID for logging

        Returns:
            Tuple of (images, text_files_content, conversation_id)
        """
        from core.events import update_status

        if message.attachments:
            await update_status(status_msg, MSG_PROCESSING_ATTACHMENTS, edit_tracker)
            guild_debug_log(
                guild_id,
                "debug",
                f"Processing {len(message.attachments)} attachment(s): {[a.filename for a in message.attachments]}"
            )

        images, text_files_content = await process_all_attachments(
            message.attachments, message.channel, guild_id
        )

        # For DMs, use author ID as conversation ID
        is_dm = isinstance(message.channel, discord.DMChannel)
        conversation_id = message.author.id if is_dm else message.channel.id

        # Track successful image analysis
        if images:
            for _ in images:
                update_stats(conversation_id, tool_used="image_analysis", guild_id=guild_id)

        # Track successful PDF reading
        if text_files_content:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith('.pdf'):
                    update_stats(conversation_id, tool_used="pdf_read", guild_id=guild_id)

        return images, text_files_content, conversation_id

    @staticmethod
    async def load_conversation_context(
        conversation_id: int,
        channel: discord.TextChannel,
        status_msg: discord.Message,
        edit_tracker: Dict,
        guild_id: Optional[int]
    ) -> None:
        """
        Load initial conversation context if needed.

        Args:
            conversation_id: ID for the conversation
            channel: Discord channel object
            status_msg: Status message to update
            edit_tracker: Edit tracking dict
            guild_id: Guild ID for logging
        """
        from core.events import update_status, get_recent_context

        if (len(get_conversation_history(conversation_id)) == 0 and
            not is_context_loaded(conversation_id) and
            CONTEXT_MESSAGES > 0):

            await update_status(status_msg, MSG_LOADING_CONTEXT, edit_tracker)
            guild_debug_log(guild_id, "debug", "Loading initial conversation context")

            recent_context = await get_recent_context(channel, CONTEXT_MESSAGES)
            for ctx_msg in recent_context:
                add_message_to_history(conversation_id, ctx_msg["role"], ctx_msg["content"])

            set_context_loaded(conversation_id, True)
            guild_debug_log(guild_id, "info", f"Loaded {len(recent_context)} context messages")

    @staticmethod
    async def fetch_web_and_url_context(
        combined_message: str,
        guild_id: Optional[int],
        status_msg: discord.Message,
        edit_tracker: Dict,
        conversation_id: int
    ) -> Tuple[str, str]:
        """
        Fetch web search results or URL content.

        Args:
            combined_message: Message text to process
            guild_id: Guild ID
            status_msg: Status message to update
            edit_tracker: Edit tracking dict
            conversation_id: Conversation ID for stats

        Returns:
            Tuple of (web_context, url_context)
        """
        from core.events import update_status
        from config.constants import MSG_SEARCHING_WEB, MSG_FETCHING_URL

        web_context = ""
        url_context = ""
        web_search_triggered = False

        # Check for web search FIRST
        if should_trigger_search(combined_message):
            if is_search_enabled(guild_id):
                cooldown = check_search_cooldown(guild_id)
                if cooldown:
                    # Return empty contexts, cooldown message will be sent by caller
                    return "", ""
                else:
                    await update_status(status_msg, MSG_SEARCHING_WEB, edit_tracker)
                    guild_debug_log(guild_id, "info", f"🔎 Triggering web search for: '{combined_message[:50]}...'")
                    web_context = await get_web_context(combined_message, guild_id=guild_id)

                    if web_context:
                        update_search_cooldown(guild_id)
                        web_search_triggered = True
                        update_stats(conversation_id, tool_used="web_search", guild_id=guild_id)
                    else:
                        logger.warning("Web search returned no results")

        # Only check for URLs if web search wasn't triggered
        if not web_search_triggered:
            if any(url in combined_message for url in ['http://', 'https://']):
                await update_status(status_msg, MSG_FETCHING_URL, edit_tracker)

            url_context = await process_message_urls(combined_message)
            if url_context:
                update_stats(conversation_id, tool_used="url_fetch", guild_id=guild_id)

        return web_context, url_context

    @staticmethod
    def build_system_prompt_with_context(
        base_prompt: str,
        web_context: str,
        url_context: str,
        guild_id: Optional[int]
    ) -> str:
        """
        Build final system prompt with web/URL context.

        Args:
            base_prompt: Base system prompt
            web_context: Web search results
            url_context: URL content
            guild_id: Guild ID for logging

        Returns:
            Final system prompt string
        """
        from config.constants import (
            MAX_SYSTEM_PROMPT_CONTEXT,
            SYSTEM_PROMPT_TRUNCATE_TO,
            SYSTEM_PROMPT_SAFE_TRUNCATE,
        )

        final_system_prompt = base_prompt

        # Add contexts to system prompt
        if web_context or url_context:
            final_system_prompt += "\n\nADDITIONAL CONTEXT FOR THIS REQUEST:"
            if web_context:
                final_system_prompt += f"\n[Web Search Results]:\n{web_context}"
            if url_context:
                final_system_prompt += f"\n{url_context}"

            final_system_prompt += (
                "\n\nINSTRUCTION: Prioritize using the provided context (Search Results or URL content) "
                "to answer. If the answer is found in the context, cite the source if possible."
            )

            # Truncate if too long
            if len(final_system_prompt) > MAX_SYSTEM_PROMPT_CONTEXT:
                logger.warning(
                    f"⚠️ Total system context too large ({len(final_system_prompt)}). "
                    f"Truncating to {MAX_SYSTEM_PROMPT_CONTEXT // 1000}k."
                )
                truncated = final_system_prompt[:SYSTEM_PROMPT_TRUNCATE_TO]
                last_paragraph = truncated.rfind('\n\n')
                if last_paragraph > SYSTEM_PROMPT_SAFE_TRUNCATE:
                    final_system_prompt = truncated[:last_paragraph]
                else:
                    final_system_prompt = truncated
                final_system_prompt += "\n\n[System: Context truncated due to length limits]"

        return final_system_prompt

    @staticmethod
    async def stream_and_update_response(
        api_messages: list,
        model_to_use: str,
        temperature: float,
        max_tokens: int,
        status_msg: discord.Message,
        edit_tracker: Dict,
        guild_id: Optional[int],
        conversation_id: Optional[int] = None
    ) -> Tuple[str, float, bool]:
        """
        Stream response from LLM and update status message.
        Includes runaway generation detection.

        Args:
            api_messages: Messages to send to API
            model_to_use: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            status_msg: Status message to update
            edit_tracker: Edit tracking dict
            guild_id: Guild ID for logging
            conversation_id: Conversation ID for clearing context on runaway

        Returns:
            Tuple of (response_text, response_time, was_runaway)
        """
        from core.events import update_status
        from config.constants import MESSAGE_EDIT_WINDOW, STREAM_UPDATE_INTERVAL, MAX_MESSAGE_EDITS_PER_WINDOW
        from config.settings import RUNAWAY_DETECTION_ENABLED, RUNAWAY_MAX_TIME, RUNAWAY_MAX_TOKENS
        from utils.stats_manager import clear_conversation_history
        from utils.text_utils import estimate_tokens

        await update_status(status_msg, MSG_WRITING_RESPONSE, edit_tracker)
        guild_debug_log(guild_id, "info", "Streaming response from LMStudio")

        start_time = time.time()
        response_text = ""
        was_runaway = False

        async for chunk in stream_completion(api_messages, model_to_use, temperature, max_tokens, guild_id):
            response_text += chunk

            current_time = time.time()
            elapsed_time = current_time - start_time

            # Runaway detection
            if RUNAWAY_DETECTION_ENABLED:
                token_count = estimate_tokens(response_text)

                # Check if generation has gone on too long or too many tokens
                if elapsed_time > RUNAWAY_MAX_TIME or token_count > RUNAWAY_MAX_TOKENS:
                    guild_debug_log(
                        guild_id, "warning",
                        f"🚨 RUNAWAY GENERATION DETECTED! Time: {elapsed_time:.1f}s, Tokens: {token_count} | "
                        f"Limits: {RUNAWAY_MAX_TIME}s, {RUNAWAY_MAX_TOKENS} tokens"
                    )

                    # Clear conversation history to prevent further issues
                    if conversation_id:
                        clear_conversation_history(conversation_id)
                        guild_debug_log(guild_id, "info", "Automatically cleared conversation history due to runaway generation")

                    was_runaway = True

                    # Truncate the response
                    response_text = response_text[:10000]  # Keep only first 10k chars
                    break  # Stop streaming

            # Reset edit counter if we're in a new window
            if current_time - edit_tracker['window_start'] >= MESSAGE_EDIT_WINDOW:
                edit_tracker['count'] = 0
                edit_tracker['window_start'] = current_time

            # Only update if enough time passed AND we haven't hit rate limit
            if (current_time - edit_tracker['last_update'] >= STREAM_UPDATE_INTERVAL and
                edit_tracker['count'] < MAX_MESSAGE_EDITS_PER_WINDOW):

                display_text = remove_thinking_tags(response_text)

                if not is_inside_thinking_tags(response_text):
                    display_text = (
                        display_text[:DISCORD_SAFE_DISPLAY_LIMIT] + "..."
                        if len(display_text) > DISCORD_SAFE_DISPLAY_LIMIT
                        else display_text
                    )

                    if display_text.strip():
                        try:
                            await status_msg.edit(
                                content=display_text if display_text else MSG_WRITING_RESPONSE
                            )
                            edit_tracker['last_update'] = current_time
                            edit_tracker['count'] += 1
                        except discord.errors.HTTPException as e:
                            logger.warning(f"Failed to edit message: {e}")
                else:
                    try:
                        await status_msg.edit(content=MSG_WRITING_RESPONSE)
                        edit_tracker['last_update'] = current_time
                        edit_tracker['count'] += 1
                    except discord.errors.HTTPException as e:
                        logger.warning(f"Failed to edit message: {e}")

        response_time = time.time() - start_time
        return response_text, response_time, was_runaway

    @staticmethod
    async def play_tts_audio(
        final_response: str,
        guild_id: int,
        conversation_id: int
    ) -> None:
        """
        Generate and play TTS audio in voice channel.

        Args:
            final_response: Text to convert to speech
            guild_id: Guild ID
            conversation_id: Conversation ID for stats
        """
        import os
        import threading

        voice_client = get_voice_client(guild_id)
        if voice_client and voice_client.is_connected() and not voice_client.is_playing():
            try:
                guild_voice = get_guild_voice(guild_id)
                guild_debug_log(
                    guild_id, "debug", f"Generating TTS audio with voice: {guild_voice}"
                )
                audio_data = await text_to_speech(final_response, guild_voice)

                if audio_data:
                    update_stats(conversation_id, tool_used="tts_voice", guild_id=guild_id)
                    guild_debug_log(
                        guild_id,
                        "info",
                        f"TTS audio generated successfully ({len(audio_data)} bytes)"
                    )

                    ts = int(time.time())
                    temp_audio = f"temp_tts_{guild_id}_{ts}.mp3"
                    with open(temp_audio, 'wb') as f:
                        f.write(audio_data)
                    guild_debug_log(guild_id, "debug", f"Playing TTS audio file: {temp_audio}")

                    def _safe_remove(path: str):
                        max_attempts = 10
                        for attempt in range(max_attempts):
                            try:
                                if os.path.exists(path):
                                    os.remove(path)
                                    logger.debug(f"Cleaned up TTS file: {path}")
                                    return
                            except PermissionError:
                                if attempt < max_attempts - 1:
                                    time.sleep(0.5)
                                else:
                                    logger.warning(
                                        f"Could not delete TTS file {path} after {max_attempts} attempts"
                                    )
                            except Exception as e:
                                logger.error(f"Error deleting TTS file {path}: {e}")
                                return

                    def cleanup(error):
                        if error:
                            logger.error(f"Error during TTS playback: {error}")
                        try:
                            threading.Timer(2.0, _safe_remove, args=(temp_audio,)).start()
                        except Exception as e:
                            logger.error(f"Error scheduling TTS cleanup: {e}")

                    voice_client.play(discord.FFmpegPCMAudio(temp_audio), after=cleanup)
                    guild_debug_log(guild_id, "info", f"Playing TTS audio for guild {guild_id} with voice {guild_voice}")
            except Exception as e:
                logger.error(f"Error playing TTS: {e}", exc_info=True)

    @staticmethod
    async def send_final_response(
        response_text: str,
        status_msg: discord.Message,
        message: discord.Message,
        conversation_id: int,
        guild_id: Optional[int],
        is_dm: bool
    ) -> None:
        """
        Send the final response to Discord, handling long messages and TTS.

        Args:
            response_text: Raw response from LLM
            status_msg: Status message to edit
            message: Original Discord message
            conversation_id: Conversation ID
            guild_id: Guild ID (None for DMs)
            is_dm: Whether this is a DM
        """
        if not response_text:
            await status_msg.edit(content="Sorry, I couldn't generate a response.")
            update_stats(conversation_id, failed=True, guild_id=guild_id)
            return

        # Process final response
        final_response = remove_thinking_tags(response_text)

        # Send the response
        if final_response.strip():
            if len(final_response) > 2000:
                await status_msg.delete()
                chunks = split_message(final_response)
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                # Try to edit with retry logic to ensure thinking tags are removed
                # This is critical because rate limiting during streaming might leave tags visible
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await status_msg.edit(content=final_response)
                        break  # Success
                    except discord.errors.HTTPException as e:
                        if attempt < max_retries - 1:
                            # Wait with exponential backoff
                            wait_time = 2 ** attempt  # 1s, 2s, 4s
                            logger.warning(f"Failed to edit final response (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                            await asyncio.sleep(wait_time)
                        else:
                            # Final attempt failed - log error but don't crash
                            logger.error(f"Failed to edit final response after {max_retries} attempts: {e}")
                            # As last resort, delete and send new message
                            try:
                                await status_msg.delete()
                                await message.channel.send(final_response)
                            except Exception as delete_error:
                                logger.error(f"Could not recover from edit failure: {delete_error}")

            # TTS in voice channel if enabled
            if ENABLE_TTS and not is_dm and guild_id:
                if is_tts_enabled_for_guild(guild_id):
                    await MessageProcessor.play_tts_audio(
                        final_response, guild_id, conversation_id
                    )
        else:
            await status_msg.edit(content="_[Response contained only thinking process]_")
