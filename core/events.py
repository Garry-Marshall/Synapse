"""
Event handlers for the Discord bot.
Handles on_ready, on_message, and on_voice_state_update events.
"""
import discord
import logging
import time

from config.settings import ALLOW_DMS, IGNORE_BOTS, CONTEXT_MESSAGES, ENABLE_TTS, ENABLE_MOSHI, LMSTUDIO_URL, ENABLE_COMFYUI, COMFYUI_TRIGGERS
from config.constants import DEFAULT_SYSTEM_PROMPT, MAX_MESSAGE_EDITS_PER_WINDOW, MESSAGE_EDIT_WINDOW, STREAM_UPDATE_INTERVAL, MSG_THINKING, MSG_BUILDING_CONTEXT

from utils.text_utils import estimate_tokens, remove_thinking_tags, count_message_tokens
from utils.logging_config import log_effective_config, guild_debug_log, log_conversation
from utils.settings_manager import get_guild_setting, get_guild_temperature, get_guild_max_tokens, is_search_enabled, is_channel_monitored, get_monitored_channels, is_comfyui_enabled_for_guild
from utils.stats_manager import add_message_to_history, update_stats, get_conversation_history, cleanup_old_conversations

from services.lmstudio import build_api_messages
from services.search import should_trigger_search, check_search_cooldown, cleanup_old_cooldowns
from services.message_processor import MessageProcessor

from commands.model import initialize_models, get_selected_model
from commands.voice import remove_voice_client
from services.moshi_voice_handler import stop_moshi_voice, is_moshi_active

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
        logger.info(f'ENABLE_MOSHI setting: {ENABLE_MOSHI}')
        logger.info(f'ENABLE_COMFYUI setting: {ENABLE_COMFYUI}')
        if ENABLE_COMFYUI:
            logger.info(f'ComfyUI triggers: {", ".join(COMFYUI_TRIGGERS)}')

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

        # Check for ComfyUI trigger words if enabled (globally and for this guild)
        guild_id = message.guild.id if not is_dm else None
        comfyui_enabled = ENABLE_COMFYUI and (guild_id is None or is_comfyui_enabled_for_guild(guild_id))

        if comfyui_enabled and message.content.strip():
            message_lower = message.content.lower()
            for trigger in COMFYUI_TRIGGERS:
                if trigger in message_lower:
                    from services.comfyui import generate_and_send_image, extract_prompt_from_message
                    guild_debug_log(guild_id, "info", f"ComfyUI trigger word '{trigger}' detected in message")

                    # Extract the prompt
                    prompt = extract_prompt_from_message(message.content, trigger)
                    if prompt:
                        # Generate and send the image (this handles everything)
                        await generate_and_send_image(message, prompt, guild_id)
                        return  # Don't process as a normal message
                    else:
                        guild_debug_log(guild_id, "warning", f"No prompt found after trigger word '{trigger}'")

        # Send initial "thinking" status
        status_msg = await message.channel.send(MSG_THINKING)

        # Track message edits for rate limiting
        edit_tracker = {
            'count': 0,
            'window_start': time.time(),
            'last_update': time.time()
        }

        try:
            # Log message processing with guild debug system
            guild_debug_log(guild_id, "info", f"Processing message from {message.author.display_name} in conversation {conversation_id}")
            guild_debug_log(guild_id, "debug", f"Message content: '{message.content[:200]}{'...' if len(message.content) > 200 else ''}'")

            # Process attachments and track tool usage
            images, text_files_content, _ = await MessageProcessor.process_message_attachments(
                message, status_msg, edit_tracker, guild_id
            )

            # Check if we have any content to process
            if not message.content.strip() and not images and not text_files_content:
                await status_msg.delete()
                return

            # Combine message with file content
            combined_message = message.content
            if text_files_content:
                combined_message = f"{message.content}\n{text_files_content}" if message.content.strip() else text_files_content

            # Log user message to conversation log
            log_conversation(message.author.id, guild_id, combined_message, is_bot=False)

            # Load initial context if needed
            await MessageProcessor.load_conversation_context(
                conversation_id, message.channel, status_msg, edit_tracker, guild_id
            )

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
            web_context, url_context = await MessageProcessor.fetch_web_and_url_context(
                combined_message, guild_id, status_msg, edit_tracker, conversation_id
            )

            # Build final system prompt with context
            if web_context or url_context:
                await update_status(status_msg, MSG_BUILDING_CONTEXT, edit_tracker)

            final_system_prompt = MessageProcessor.build_system_prompt_with_context(
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

            # Count prompt tokens accurately for stats (using tiktoken if available)
            estimated_prompt_tokens = count_message_tokens(api_messages)
            guild_debug_log(guild_id, "debug", f"Prompt tokens (accurate): {estimated_prompt_tokens}")

            # Stream the response
            response_text, response_time = await MessageProcessor.stream_and_update_response(
                api_messages, model_to_use, temperature, max_tokens,
                status_msg, edit_tracker, guild_id
            )

            # Process final response
            if response_text:
                add_message_to_history(conversation_id, "assistant", response_text)

                # Log bot response to conversation log
                log_conversation(message.author.id, guild_id, response_text, is_bot=True)

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

                guild_debug_log(
                    guild_id, "info",
                    f"Response tokens | convo={conversation_id} | raw={raw_token_count} | cleaned={cleaned_token_count} | removed={raw_token_count - cleaned_token_count} | time={response_time:.2f}s"
                )

                # Send the final response
                await MessageProcessor.send_final_response(
                    response_text, status_msg, message, conversation_id, guild_id, is_dm
                )
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
                guild_id = member.guild.id
                logger.info(f"Bot left alone in VC {voice_client.channel.id}. Disconnecting...")

                # Stop Moshi if active before disconnecting
                if is_moshi_active(guild_id):
                    logger.info(f"Stopping Moshi for guild {guild_id} before leaving VC")
                    await stop_moshi_voice(guild_id)

                await voice_client.disconnect()
                remove_voice_client(guild_id)
