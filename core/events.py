"""
Event handlers for the Discord bot.
Handles on_ready, on_message, and on_voice_state_update events.
"""
import discord
import logging
import time
import os
import threading

from config.settings import ALLOW_DMS, IGNORE_BOTS, CONTEXT_MESSAGES, ENABLE_TTS, LMSTUDIO_URL
from config.constants import (
    DEFAULT_SYSTEM_PROMPT,
    MAX_MESSAGE_EDITS_PER_WINDOW,
    MESSAGE_EDIT_WINDOW,
    STREAM_UPDATE_INTERVAL,
    DISCORD_SAFE_DISPLAY_LIMIT,
    MAX_SYSTEM_PROMPT_CONTEXT,
    SYSTEM_PROMPT_TRUNCATE_TO,
    SYSTEM_PROMPT_SAFE_TRUNCATE,
    MSG_THINKING,
    MSG_PROCESSING_ATTACHMENTS,
    MSG_LOADING_CONTEXT,
    MSG_SEARCHING_WEB,
    MSG_FETCHING_URL,
    MSG_BUILDING_CONTEXT,
    MSG_WRITING_RESPONSE,
)

from utils.text_utils import estimate_tokens, remove_thinking_tags, is_inside_thinking_tags, split_message
from utils.logging_config import log_effective_config, guild_debug_log
from utils.settings_manager import get_guild_setting, is_tts_enabled_for_guild, get_guild_voice, get_guild_temperature, get_guild_max_tokens, is_search_enabled, is_channel_monitored, get_monitored_channels
from utils.stats_manager import add_message_to_history, update_stats, is_context_loaded, set_context_loaded, get_conversation_history, cleanup_old_conversations

from services.lmstudio import build_api_messages, stream_completion
from services.content_fetch import process_message_urls
from services.file_processor import process_all_attachments
from services.search import should_trigger_search, check_search_cooldown, get_web_context, update_search_cooldown, cleanup_old_cooldowns
from services.tts import text_to_speech

from commands.model import initialize_models, get_selected_model
from commands.voice import get_voice_client, remove_voice_client

from commands import setup_all_commands


logger = logging.getLogger(__name__)


async def get_recent_context(channel, limit: int = CONTEXT_MESSAGES) -> list:
    """
    Fetch recent messages from the Discord channel to provide context.

    Args:
        channel: Discord channel object
        limit: Number of messages to fetch

    Returns:
        List of message dictionaries
    """
    context = []
    try:
        async for msg in channel.history(limit=limit * 3):
            if IGNORE_BOTS and msg.author.bot:
                continue
            if hasattr(channel, 'guild') and channel.guild is not None:
                if msg.author == channel.guild.me:
                    continue

            if isinstance(channel, discord.DMChannel):
                context.append({"role": "user", "content": msg.content})
            else:
                context.append({"role": "user", "content": f"{msg.author.display_name}: {msg.content}"})

            if len(context) >= limit:
                break

        context.reverse()
        return context
    except Exception as e:
        logger.error(f"Error fetching message history: {e}")
        return []


async def update_status(status_msg, content: str, edit_tracker: dict):
    """
    Update status message with rate limit protection.

    Args:
        status_msg: Discord message to edit
        content: New content
        edit_tracker: Dict tracking edits (count, window_start, last_update)
    """
    current_time = time.time()

    # Reset edit counter if we're in a new window
    if current_time - edit_tracker['window_start'] >= MESSAGE_EDIT_WINDOW:
        edit_tracker['count'] = 0
        edit_tracker['window_start'] = current_time

    # Check if enough time passed and we haven't hit rate limit
    if (current_time - edit_tracker['last_update'] >= STREAM_UPDATE_INTERVAL and
        edit_tracker['count'] < MAX_MESSAGE_EDITS_PER_WINDOW):
        try:
            await status_msg.edit(content=content)
            edit_tracker['last_update'] = current_time
            edit_tracker['count'] += 1
        except discord.errors.HTTPException as e:
            logger.warning(f"Failed to edit message: {e}")


async def process_message_attachments(message, status_msg, edit_tracker, guild_id):
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
    if message.attachments:
        await update_status(status_msg, MSG_PROCESSING_ATTACHMENTS, edit_tracker)
        guild_debug_log(guild_id, "debug", f"Processing {len(message.attachments)} attachment(s): {[a.filename for a in message.attachments]}")

    images, text_files_content = await process_all_attachments(message.attachments, message.channel, guild_id)

    # For DMs, use author ID as conversation ID
    is_dm = isinstance(message.channel, discord.DMChannel)
    conversation_id = message.author.id if is_dm else message.channel.id

    # Track successful image analysis
    if images:
        for _ in images:
            update_stats(conversation_id, tool_used="image_analysis")

    # Track successful PDF reading
    if text_files_content:
        for attachment in message.attachments:
            if attachment.filename.lower().endswith('.pdf'):
                update_stats(conversation_id, tool_used="pdf_read")

    return images, text_files_content, conversation_id


async def load_conversation_context(conversation_id, channel, status_msg, edit_tracker, guild_id):
    """
    Load initial conversation context if needed.

    Args:
        conversation_id: ID for the conversation
        channel: Discord channel object
        status_msg: Status message to update
        edit_tracker: Edit tracking dict
        guild_id: Guild ID for logging
    """
    if len(get_conversation_history(conversation_id)) == 0 and not is_context_loaded(conversation_id) and CONTEXT_MESSAGES > 0:
        await update_status(status_msg, MSG_LOADING_CONTEXT, edit_tracker)
        guild_debug_log(guild_id, "debug", "Loading initial conversation context")
        recent_context = await get_recent_context(channel, CONTEXT_MESSAGES)
        for ctx_msg in recent_context:
            add_message_to_history(conversation_id, ctx_msg["role"], ctx_msg["content"])
        set_context_loaded(conversation_id, True)
        logger.info(f"Loaded {len(recent_context)} context messages")


async def fetch_web_and_url_context(combined_message, guild_id, status_msg, edit_tracker, conversation_id):
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
    web_context = ""
    url_context = ""
    web_search_triggered = False

    # Check for web search FIRST
    if should_trigger_search(combined_message):
        if is_search_enabled(guild_id):
            cooldown = check_search_cooldown(guild_id)
            if cooldown:
                # Return empty contexts, cooldown message will be sent by caller if needed
                return "", ""
            else:
                await update_status(status_msg, MSG_SEARCHING_WEB, edit_tracker)
                logger.info(f"🔎 Triggering web search for: '{combined_message[:50]}...'")
                web_context = await get_web_context(combined_message, guild_id=guild_id)

                if web_context:
                    update_search_cooldown(guild_id)
                    web_search_triggered = True
                    update_stats(conversation_id, tool_used="web_search")
                else:
                    logger.warning("Web search returned no results")

    # Only check for URLs if web search wasn't triggered
    if not web_search_triggered:
        if any(url in combined_message for url in ['http://', 'https://']):
            await update_status(status_msg, MSG_FETCHING_URL, edit_tracker)

        url_context = await process_message_urls(combined_message)
        if url_context:
            update_stats(conversation_id, tool_used="url_fetch")

    return web_context, url_context


def build_system_prompt_with_context(base_prompt, web_context, url_context, guild_id):
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
            logger.warning(f"⚠️ Total system context too large ({len(final_system_prompt)}). Truncating to {MAX_SYSTEM_PROMPT_CONTEXT // 1000}k.")
            truncated = final_system_prompt[:SYSTEM_PROMPT_TRUNCATE_TO]
            last_paragraph = truncated.rfind('\n\n')
            if last_paragraph > SYSTEM_PROMPT_SAFE_TRUNCATE:
                final_system_prompt = truncated[:last_paragraph]
            else:
                final_system_prompt = truncated
            final_system_prompt += "\n\n[System: Context truncated due to length limits]"

    return final_system_prompt


async def stream_and_update_response(api_messages, model_to_use, temperature, max_tokens,
                                    status_msg, edit_tracker, guild_id):
    """
    Stream response from LLM and update status message.

    Args:
        api_messages: Messages to send to API
        model_to_use: Model identifier
        temperature: Temperature setting
        max_tokens: Max tokens setting
        status_msg: Status message to update
        edit_tracker: Edit tracking dict
        guild_id: Guild ID for logging

    Returns:
        Tuple of (response_text, response_time)
    """
    await update_status(status_msg, MSG_WRITING_RESPONSE, edit_tracker)
    guild_debug_log(guild_id, "info", "Streaming response from LMStudio")

    start_time = time.time()
    response_text = ""

    async for chunk in stream_completion(api_messages, model_to_use, temperature, max_tokens, guild_id):
        response_text += chunk

        current_time = time.time()

        # Reset edit counter if we're in a new window
        if current_time - edit_tracker['window_start'] >= MESSAGE_EDIT_WINDOW:
            edit_tracker['count'] = 0
            edit_tracker['window_start'] = current_time

        # Only update if enough time passed AND we haven't hit rate limit
        if current_time - edit_tracker['last_update'] >= STREAM_UPDATE_INTERVAL and edit_tracker['count'] < MAX_MESSAGE_EDITS_PER_WINDOW:
            display_text = remove_thinking_tags(response_text)

            if not is_inside_thinking_tags(response_text):
                display_text = display_text[:DISCORD_SAFE_DISPLAY_LIMIT] + "..." if len(display_text) > DISCORD_SAFE_DISPLAY_LIMIT else display_text

                if display_text.strip():
                    try:
                        await status_msg.edit(content=display_text if display_text else MSG_WRITING_RESPONSE)
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
    return response_text, response_time


async def play_tts_audio(final_response, guild_id, conversation_id):
    """
    Generate and play TTS audio in voice channel.

    Args:
        final_response: Text to convert to speech
        guild_id: Guild ID
        conversation_id: Conversation ID for stats
    """
    voice_client = get_voice_client(guild_id)
    if voice_client and voice_client.is_connected() and not voice_client.is_playing():
        try:
            guild_voice = get_guild_voice(guild_id)
            guild_debug_log(guild_id, "debug", f"Generating TTS audio with voice: {guild_voice}")
            audio_data = await text_to_speech(final_response, guild_voice)

            if audio_data:
                update_stats(conversation_id, tool_used="tts_voice")
                guild_debug_log(guild_id, "info", f"TTS audio generated successfully ({len(audio_data)} bytes)")

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
                                logger.warning(f"Could not delete TTS file {path} after {max_attempts} attempts")
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
                logger.info(f"Playing TTS audio for guild {guild_id} with voice {guild_voice}")
        except Exception as e:
            logger.error(f"Error playing TTS: {e}", exc_info=True)


def setup_events(bot):
    """
    Register all event handlers with the bot.

    Args:
        bot: Discord bot instance
    """

    @bot.event
    async def on_ready():
        """Called when the bot successfully connects to Discord."""
        log_effective_config()
        logger.info(
            "Logger initialized | log_level=%s",
            logging.getLevelName(logger.getEffectiveLevel())
        )

        logger.info(f'{bot.user} has connected to Discord!')
        logger.info(f'Bot is in {len(bot.guilds)} server(s)')
        logger.info(f'LMStudio URL: {LMSTUDIO_URL}')

        # Fetch available models from LMStudio with validation
        try:
            models_loaded = await initialize_models()
            if not models_loaded:
                logger.error("⚠️ CRITICAL: No models loaded from LMStudio!")
                logger.error("⚠️ The bot will not be able to respond to messages.")
                logger.error("⚠️ Please ensure LMStudio is running with at least one model loaded.")
        except Exception as e:
            logger.error(f"⚠️ CRITICAL: Failed to initialize models: {e}", exc_info=True)
            logger.error("⚠️ The bot may not function correctly.")

        # Log monitored channels per guild
        logger.info("=" * 60)
        logger.info("MONITORED CHANNELS:")
        total_monitored = 0

        for guild in bot.guilds:
            monitored_channels = get_monitored_channels(guild.id)

            if monitored_channels:
                logger.info(f"  📁 {guild.name} (ID: {guild.id}):")
                for channel_id in sorted(monitored_channels):
                    channel = guild.get_channel(channel_id)
                    if channel:
                        logger.info(f"    ✓ #{channel.name} (ID: {channel_id})")
                        total_monitored += 1
                    else:
                        logger.warning(f"    ⚠ Channel ID {channel_id} not found (may be deleted)")
            else:
                logger.info(f"  📁 {guild.name} (ID: {guild.id}): No channels monitored")

        if total_monitored == 0:
            logger.warning("⚠️ No channels are being monitored! Use /add_channel to add channels.")
        else:
            logger.info(f"✅ Total monitored channels: {total_monitored}")
        logger.info("=" * 60)

        # Sync slash commands
        try:
            setup_all_commands(bot.tree)
            synced = await bot.tree.sync()
            logger.info(f'Synced {len(synced)} slash command(s)')
        except Exception as e:
            logger.error(f'Failed to sync slash commands: {e}')

        # Log configuration
        logger.info(f'IGNORE_BOTS setting: {IGNORE_BOTS}')
        logger.info(f'CONTEXT_MESSAGES setting: {CONTEXT_MESSAGES}')
        logger.info(f'ALLOW_DMS setting: {ALLOW_DMS}')
        logger.info(f'ENABLE_TTS setting: {ENABLE_TTS}')

        # Clean up old conversations on startup
        cleanup_old_conversations()

        # Clean up old search cooldowns
        cleanup_old_cooldowns()


    @bot.event
    async def on_message(message):
        """Called when any message is sent in a channel the bot can see."""
        # Ignore messages from the bot itself
        if message.author == bot.user:
            return

        # Ignore messages from other bots if enabled
        if IGNORE_BOTS and message.author.bot:
            return

        # Check if it's a DM
        is_dm = isinstance(message.channel, discord.DMChannel)

        # For DMs, check if they're allowed
        if is_dm:
            if not ALLOW_DMS:
                return
            conversation_id = message.author.id
        else:
            # For guild channels, check if it's a monitored channel
            guild_id = message.guild.id

            # Check guild-specific monitored channels
            if not is_channel_monitored(guild_id, message.channel.id):
                return  # Don't respond if channel isn't monitored

            conversation_id = message.channel.id

        # Ignore messages starting with * (user wants to exclude from bot)
        if message.content.startswith('*'):
            logger.info(f"Ignoring message starting with asterisk from {message.author.display_name}")
            return

        # Ignore empty messages
        if not message.content.strip() and not message.attachments:
            return

        # Send initial "thinking" status
        status_msg = await message.channel.send(MSG_THINKING)

        # Track message edits for rate limiting
        edit_tracker = {
            'count': 0,
            'window_start': time.time(),
            'last_update': time.time()
        }

        try:
            # Get guild_id for settings (None for DMs)
            guild_id = message.guild.id if not is_dm else None

            # DIAGNOSTIC: Log with regular logger to verify it's working
            logger.info(f"Processing message from {message.author.display_name} | guild_id={guild_id} | conversation_id={conversation_id}")

            # Check debug settings and log diagnostic
            from utils.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            debug_enabled = settings_mgr.is_debug_enabled(guild_id) if guild_id else False
            debug_level = settings_mgr.get_debug_level(guild_id) if guild_id else "info"

            logger.info(f"Debug settings: enabled={debug_enabled}, level={debug_level}")

            guild_debug_log(guild_id, "info", f"Processing message from {message.author.display_name} in conversation {conversation_id}")
            guild_debug_log(guild_id, "debug", f"Message content: '{message.content[:200]}{'...' if len(message.content) > 200 else ''}'")

            # Process attachments and track tool usage
            images, text_files_content, _ = await process_message_attachments(message, status_msg, edit_tracker, guild_id)

            # Check if we have any content to process
            if not message.content.strip() and not images and not text_files_content:
                await status_msg.delete()
                return

            # Combine message with file content
            combined_message = message.content
            if text_files_content:
                combined_message = f"{message.content}\n{text_files_content}" if message.content.strip() else text_files_content

            # Load initial context if needed
            await load_conversation_context(conversation_id, message.channel, status_msg, edit_tracker, guild_id)

            # Build the system prompt with web search and URL context
            base_system_prompt = get_guild_setting(guild_id, "system_prompt", DEFAULT_SYSTEM_PROMPT)

            # Check for web search cooldown message
            if should_trigger_search(combined_message) and is_search_enabled(guild_id):
                cooldown = check_search_cooldown(guild_id)
                if cooldown:
                    await message.channel.send(
                        f"⏱️ Search is on cooldown. Please wait {cooldown} more seconds.",
                        delete_after=10
                    )

            # Fetch web and URL context
            web_context, url_context = await fetch_web_and_url_context(
                combined_message, guild_id, status_msg, edit_tracker, conversation_id
            )

            # Build final system prompt with context
            if web_context or url_context:
                await update_status(status_msg, MSG_BUILDING_CONTEXT, edit_tracker)

            final_system_prompt = build_system_prompt_with_context(
                base_system_prompt, web_context, url_context, guild_id
            )

            # Prepare user message content
            current_content = combined_message
            if images and len(images) > 0:
                current_content = [{"type": "text", "text": combined_message or "What's in this image?"}] + images

            # Add to conversation history
            add_message_to_history(conversation_id, "user", current_content)

            # Build API messages
            api_messages = build_api_messages(get_conversation_history(conversation_id), final_system_prompt)

            guild_debug_log(guild_id, "debug", f"=== API REQUEST ===")
            guild_debug_log(guild_id, "debug", f"System prompt: {final_system_prompt[:500]}{'...' if len(final_system_prompt) > 500 else ''}")
            guild_debug_log(guild_id, "debug", f"Total API messages: {len(api_messages)}")

            # Log last user message (most recent)
            for msg in reversed(api_messages):
                if msg["role"] == "user":
                    content_preview = str(msg["content"])[:300]
                    guild_debug_log(guild_id, "debug", f"Latest user message: {content_preview}{'...' if len(str(msg['content'])) > 300 else ''}")
                    break

            # Get model and settings
            model_to_use = get_selected_model(guild_id)
            temperature = get_guild_temperature(guild_id)
            max_tokens = get_guild_max_tokens(guild_id)

            guild_debug_log(guild_id, "debug", f"Using model: {model_to_use}, temp: {temperature}, max_tokens: {max_tokens}")
            guild_debug_log(guild_id, "debug", f"Conversation history length: {len(get_conversation_history(conversation_id))} messages")

            # Estimate prompt tokens for stats
            estimated_prompt_tokens = estimate_tokens(str(api_messages))
            guild_debug_log(guild_id, "debug", f"Estimated prompt tokens: {estimated_prompt_tokens}")

            # Stream the response
            response_text, response_time = await stream_and_update_response(
                api_messages, model_to_use, temperature, max_tokens,
                status_msg, edit_tracker, guild_id
            )

            # Process final response
            if response_text:
                add_message_to_history(conversation_id, "assistant", response_text)

                # Calculate stats
                final_response = remove_thinking_tags(response_text)
                raw_token_count = estimate_tokens(response_text)
                cleaned_token_count = estimate_tokens(final_response)

                # DEBUG: Log the actual response content
                guild_debug_log(guild_id, "debug", "=== RAW LLM RESPONSE (WITH THINKING BLOCKS) ===")
                guild_debug_log(guild_id, "debug", f"Full raw response:\n{response_text}")
                guild_debug_log(guild_id, "debug", "=== CLEANED RESPONSE (THINKING REMOVED) ===")
                guild_debug_log(guild_id, "debug", f"Final response:\n{final_response}")
                guild_debug_log(guild_id, "debug", "=" * 50)

                guild_debug_log(
                    guild_id, "info",
                    f"Response completed in {response_time:.2f}s | Raw: {raw_token_count} tokens | Cleaned: {cleaned_token_count} tokens"
                )
                guild_debug_log(
                    guild_id, "debug",
                    f"Thinking tokens removed: {raw_token_count - cleaned_token_count}"
                )

                # Update statistics
                update_stats(
                    conversation_id,
                    prompt_tokens=estimated_prompt_tokens,
                    response_tokens_raw=raw_token_count,
                    response_tokens_cleaned=cleaned_token_count,
                    response_time=response_time
                )

                logger.info(
                    "Response tokens | convo=%s | raw=%d | cleaned=%d | removed=%d | time=%.2fs",
                    conversation_id,
                    raw_token_count,
                    cleaned_token_count,
                    raw_token_count - cleaned_token_count,
                    response_time
                )

                # Send the response
                if final_response.strip():
                    if len(final_response) > 2000:
                        await status_msg.delete()
                        chunks = split_message(final_response)
                        for chunk in chunks:
                            await message.channel.send(chunk)
                    else:
                        await status_msg.edit(content=final_response)

                    # TTS in voice channel if enabled
                    if ENABLE_TTS and not is_dm and guild_id:
                        if is_tts_enabled_for_guild(guild_id):
                            await play_tts_audio(final_response, guild_id, conversation_id)
                else:
                    await status_msg.edit(content="_[Response contained only thinking process]_")
            else:
                await status_msg.edit(content="Sorry, I couldn't generate a response.")
                update_stats(conversation_id, failed=True)

        except Exception as e:
            logger.error(f"Error in on_message: {e}", exc_info=True)
            try:
                await status_msg.edit(content="An error occurred while processing your message.")
            except discord.errors.HTTPException as edit_error:
                logger.error(f"Failed to edit error message: {edit_error}")
            except Exception as edit_error:
                logger.error(f"Unexpected error editing status message: {edit_error}")
            update_stats(conversation_id, failed=True)


    @bot.event
    async def on_voice_state_update(member, before, after):
        """Event listener to auto-leave when the bot is left alone in a VC."""
        voice_client = member.guild.voice_client

        if not voice_client:
            return

        if before.channel is not None and before.channel.id == voice_client.channel.id:
            non_bot_members = [m for m in voice_client.channel.members if not m.bot]

            if len(non_bot_members) == 0:
                logger.info(f"Bot left alone in VC {voice_client.channel.id}. Disconnecting...")
                await voice_client.disconnect()
                remove_voice_client(member.guild.id)
