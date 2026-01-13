"""
Event handlers for the Discord bot.
Handles on_ready, on_message, and on_voice_state_update events.
"""
import discord
import logging
import time
import os

from config import (
    CHANNEL_IDS,
    ALLOW_DMS,
    IGNORE_BOTS,
    CONTEXT_MESSAGES,
    ENABLE_TTS,
    LMSTUDIO_URL,
    DEFAULT_SYSTEM_PROMPT
)
from utils import (
    estimate_tokens,
    remove_thinking_tags,
    is_inside_thinking_tags,
    split_message,
    log_effective_config,
    guild_debug_log,
    add_message_to_history,
    update_stats,
    is_context_loaded,
    set_context_loaded,
    get_conversation_history,
    guild_settings
)
from services import (
    build_api_messages,
    stream_completion,
    should_trigger_search,
    check_search_cooldown,
    get_web_context,
    update_search_cooldown,
    process_message_urls,
    process_all_attachments,
    text_to_speech
)
from commands import (
    setup_all_commands,
    initialize_models,
    get_selected_model,
    get_voice_client,
    get_selected_voice,
    voice_clients
)

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
            if msg.author == channel.guild.me if hasattr(channel, 'guild') else msg.author.bot:
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
            "Logger initialized | python_level=%s",
            logging.getLevelName(logger.getEffectiveLevel())
        )
        
        logger.info(f'{bot.user} has connected to Discord!')
        logger.info(f'Bot is in {len(bot.guilds)} server(s)')
        logger.info(f'Listening in {len(CHANNEL_IDS)} channel(s): {CHANNEL_IDS}')
        logger.info(f'LMStudio URL: {LMSTUDIO_URL}')
        
        # Fetch available models from LMStudio
        await initialize_models()
        
        # Log channel details
        for channel_id in CHANNEL_IDS:
            channel = bot.get_channel(channel_id)
            if channel:
                logger.info(f'  - #{channel.name} in {channel.guild.name}')
            else:
                logger.warning(f'  - Channel ID {channel_id} not found (bot may not have access)')
        
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
            if message.channel.id not in CHANNEL_IDS:
                return
            conversation_id = message.channel.id
        
        # Ignore messages starting with * (user wants to exclude from bot)
        if message.content.startswith('*'):
            logger.info(f"Ignoring message starting with asterisk from {message.author.display_name}")
            return
        
        # Ignore empty messages
        if not message.content.strip() and not message.attachments:
            return
        
        # Process attachments
        images, text_files_content = await process_all_attachments(message.attachments, message.channel)
        
        # Check if we have any content to process
        if not message.content.strip() and not images and not text_files_content:
            return
        
        # Combine message with file content
        combined_message = message.content
        if text_files_content:
            combined_message = f"{message.content}\n{text_files_content}" if message.content.strip() else text_files_content
        
        # Send "thinking" status
        status_msg = await message.channel.send("🤔 Thinking...")
        
        try:
            # Get guild_id for settings (None for DMs)
            guild_id = message.guild.id if not is_dm else None
            
            # Load initial context if needed
            if len(get_conversation_history(conversation_id)) == 0 and not is_context_loaded(conversation_id) and CONTEXT_MESSAGES > 0:
                recent_context = await get_recent_context(message.channel, CONTEXT_MESSAGES)
                for ctx_msg in recent_context:
                    add_message_to_history(conversation_id, ctx_msg["role"], ctx_msg["content"])
                set_context_loaded(conversation_id, True)
                logger.info(f"Loaded {len(recent_context)} context messages")
            
            # Build the system prompt with web search and URL context
            base_system_prompt = guild_settings.get(guild_id, {}).get("system_prompt", DEFAULT_SYSTEM_PROMPT)
            final_system_prompt = base_system_prompt
            
            # Check for web search
            web_context = ""
            if should_trigger_search(combined_message):
                from utils import is_search_enabled
                if is_search_enabled(guild_id):
                    cooldown = check_search_cooldown(guild_id)
                    if cooldown:
                        await message.channel.send(
                            f"⏱️ Search is on cooldown. Please wait {cooldown} more seconds.",
                            delete_after=10
                        )
                    else:
                        logger.info(f"🔍 Triggering web search for: '{combined_message[:50]}...'")
                        web_context = await get_web_context(combined_message)
                        update_search_cooldown(guild_id)
            
            # Check for URLs in message
            url_context = await process_message_urls(combined_message)
            
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
                if len(final_system_prompt) > 60000:
                    logger.warning(f"⚠️ Total system context too large ({len(final_system_prompt)}). Truncating to 60k.")
                    final_system_prompt = final_system_prompt[:60000] + "\n[System: Context truncated due to length limits]"
            
            # Debug logging
            if web_context:
                guild_debug_log(
                    guild_id,
                    "debug",
                    "Web search context added | chars=%d | est_tokens=%d",
                    len(web_context),
                    estimate_tokens(web_context),
                    guild_settings=guild_settings
                )
            
            # Prepare user message content
            username = message.author.display_name
            current_content = combined_message
            if images and len(images) > 0:
                current_content = [{"type": "text", "text": combined_message or "What's in this image?"}] + images
            
            # Add to conversation history
            add_message_to_history(conversation_id, "user", current_content)
            
            # Build API messages
            api_messages = build_api_messages(get_conversation_history(conversation_id), final_system_prompt)
            
            # Get model and settings
            from utils import get_guild_temperature, get_guild_max_tokens
            model_to_use = get_selected_model(guild_id) if guild_id else "local-model"
            temperature = get_guild_temperature(guild_id)
            max_tokens = get_guild_max_tokens(guild_id)
            
            # Estimate prompt tokens for stats
            estimated_prompt_tokens = estimate_tokens(str(api_messages))
            
            # Stream the response
            start_time = time.time()
            response_text = ""
            last_update = time.time()
            update_interval = 1.0
            
            async for chunk in stream_completion(api_messages, model_to_use, temperature, max_tokens):
                response_text += chunk
                
                current_time = time.time()
                if current_time - last_update >= update_interval:
                    display_text = remove_thinking_tags(response_text)
                    
                    if not is_inside_thinking_tags(response_text):
                        display_text = display_text[:1900] + "..." if len(display_text) > 1900 else display_text
                        
                        if display_text.strip():
                            try:
                                await status_msg.edit(content=display_text if display_text else "🤔 Thinking...")
                                last_update = current_time
                            except discord.errors.HTTPException:
                                pass
                    else:
                        try:
                            await status_msg.edit(content="🤔 Thinking...")
                            last_update = current_time
                        except discord.errors.HTTPException:
                            pass
            
            # Process final response
            if response_text:
                # Log full raw response (with thinking tags)
                guild_debug_log(
                    guild_id,
                    "debug",
                    "Full raw response (with thinking) | convo=%s:\n%s",
                    conversation_id,
                    response_text,
                    guild_settings=guild_settings
                )
                
                # Add to conversation history
                add_message_to_history(conversation_id, "assistant", response_text)
                
                # Calculate stats
                response_time = time.time() - start_time
                final_response = remove_thinking_tags(response_text)
                raw_token_count = estimate_tokens(response_text)
                cleaned_token_count = estimate_tokens(final_response)
                
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
                        voice_client = get_voice_client(guild_id)
                        if voice_client and voice_client.is_connected() and not voice_client.is_playing():
                            try:
                                guild_voice = get_selected_voice(guild_id)
                                audio_data = await text_to_speech(final_response, guild_voice)
                                
                                if audio_data:
                                    # Unique filename to prevent access errors
                                    ts = int(time.time())
                                    temp_audio = f"temp_tts_{guild_id}_{ts}.mp3"
                                    with open(temp_audio, 'wb') as f:
                                        f.write(audio_data)
                                    
                                    def cleanup(error):
                                        if os.path.exists(temp_audio):
                                            try:
                                                time.sleep(0.1)
                                                os.remove(temp_audio)
                                            except:
                                                pass
                                    
                                    voice_client.play(discord.FFmpegPCMAudio(temp_audio), after=cleanup)
                                    logger.info(f"Playing TTS audio for guild {guild_id}")
                            except Exception as e:
                                logger.error(f"Error playing TTS: {e}")
                else:
                    await status_msg.edit(content="_[Response contained only thinking process]_")
            else:
                await status_msg.edit(content="Sorry, I couldn't generate a response.")
                update_stats(conversation_id, failed=True)
                
        except Exception as e:
            logger.error(f"Error in on_message: {e}", exc_info=True)
            try:
                await status_msg.edit(content="An error occurred while processing your message.")
            except:
                pass
            update_stats(conversation_id, failed=True)
    
    
    @bot.event
    async def on_voice_state_update(member, before, after):
        """Event listener to auto-leave when the bot is left alone in a VC."""
        # Find the voice client for this guild
        voice_client = member.guild.voice_client
        
        # If the bot isn't in a voice channel, we don't need to do anything
        if not voice_client:
            return

        # Check if the channel that was updated is the one the bot is in
        if before.channel is not None and before.channel.id == voice_client.channel.id:
            # Count the members left (excluding bots)
            non_bot_members = [m for m in voice_client.channel.members if not m.bot]
            
            if len(non_bot_members) == 0:
                logger.info(f"Bot left alone in VC {voice_client.channel.id}. Disconnecting...")
                await voice_client.disconnect()
                # Clean up from voice_clients dict
                if member.guild.id in voice_clients:
                    del voice_clients[member.guild.id]