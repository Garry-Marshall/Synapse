import discord
from discord.ext import commands
import aiohttp
import json
import os
from typing import Optional, List, Dict
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime
import time
import base64
import io
import logging
from logging.handlers import RotatingFileHandler
import asyncio

# Load environment variables from .env file
load_dotenv()

# Check if .env file exists, if not create one with defaults
env_file_path = ".env"
if not os.path.exists(env_file_path):
    default_env_content = """# Discord Bot Configuration
# Fill in your bot token and channel IDs below

# REQUIRED: Your Discord bot token from https://discord.com/developers/applications
DISCORD_BOT_TOKEN=your-discord-bot-token-here

# REQUIRED: Comma-separated list of channel IDs where the bot should listen
# Enable Developer Mode in Discord, right-click channels, and select "Copy ID"
DISCORD_CHANNEL_IDS=

# LMStudio API Configuration
LMSTUDIO_URL=http://localhost:1234/v1/chat/completions

# Conversation Settings
MAX_HISTORY_MESSAGES=10
CONTEXT_MESSAGES=5

# Bot Behavior
IGNORE_BOTS=true
ALLOW_DMS=true

# Image Support
ALLOW_IMAGES=true
MAX_IMAGE_SIZE=5

# Text File Support
ALLOW_TEXT_FILES=true
MAX_TEXT_FILE_SIZE=2

# Reasoning Model Settings
HIDE_THINKING=true

# Voice/TTS Settings
ENABLE_TTS=true
ALLTALK_URL=http://127.0.0.1:7851
ALLTALK_VOICE=alloy
"""
    with open(env_file_path, 'w', encoding='utf-8') as f:
        f.write(default_env_content)
    print(f"Created default .env file at {env_file_path}")
    print("Please edit the .env file and add your DISCORD_BOT_TOKEN and DISCORD_CHANNEL_IDS")
    print("")
    # Reload after creating the file
    load_dotenv()

# Setup logging
log_dir = "Logs"
os.makedirs(log_dir, exist_ok=True)

# Create log filename with date stamp
log_filename = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y-%m-%d')}.log")

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        # File handler with rotation (max 10MB per file, keep 5 backup files)
        RotatingFileHandler(log_filename, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'),
        # Console handler
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your-discord-bot-token-here')
LMSTUDIO_URL = os.getenv('LMSTUDIO_URL', 'http://localhost:1234/v1/chat/completions')
MAX_HISTORY = int(os.getenv('MAX_HISTORY_MESSAGES', '10'))
CONTEXT_MESSAGES = int(os.getenv('CONTEXT_MESSAGES', '5'))
IGNORE_BOTS = os.getenv('IGNORE_BOTS', 'true').lower() == 'true'
ALLOW_DMS = os.getenv('ALLOW_DMS', 'true').lower() == 'true'
ALLOW_IMAGES = os.getenv('ALLOW_IMAGES', 'true').lower() == 'true'
MAX_IMAGE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', '5'))
ALLOW_TEXT_FILES = os.getenv('ALLOW_TEXT_FILES', 'true').lower() == 'true'
MAX_TEXT_FILE_SIZE = int(os.getenv('MAX_TEXT_FILE_SIZE', '2'))
HIDE_THINKING = os.getenv('HIDE_THINKING', 'true').lower() == 'true'
ENABLE_TTS = os.getenv('ENABLE_TTS', 'true').lower() == 'true'
ALLTALK_URL = os.getenv('ALLTALK_URL', 'http://127.0.0.1:7851')
ALLTALK_VOICE = os.getenv('ALLTALK_VOICE', 'alloy')
GUILD_SETTINGS_FILE = "guild_settings.json"

# OpenAI-compatible voice names for AllTalk TTS
AVAILABLE_VOICES = ['alloy', 'echo', 'fable', 'nova', 'onyx', 'shimmer']

# Parse channel IDs from environment variable (comma-separated)
CHANNEL_IDS_STR = os.getenv('DISCORD_CHANNEL_IDS', '0')
CHANNEL_IDS = set()
if CHANNEL_IDS_STR and CHANNEL_IDS_STR != '0':
    try:
        CHANNEL_IDS = set(int(cid.strip()) for cid in CHANNEL_IDS_STR.split(',') if cid.strip())
    except ValueError:
        logger.error("DISCORD_CHANNEL_IDS must be comma-separated numbers")
        CHANNEL_IDS = set()

# Store conversation history per channel/DM
conversation_histories: Dict[int, List[Dict[str, str]]] = defaultdict(list)

# Track whether context has been loaded for each conversation
context_loaded: Dict[int, bool] = defaultdict(bool)

# Store statistics per channel/DM
channel_stats: Dict[int, Dict] = defaultdict(lambda: {
    'total_messages': 0,
    'total_tokens_estimate': 0,
    'start_time': datetime.now(),
    'last_message_time': None,
    'response_times': []
})

# Store voice channel connections per guild
voice_clients: Dict[int, discord.VoiceClient] = {}

# Store selected voice per guild
selected_voices: Dict[int, str] = defaultdict(lambda: ALLTALK_VOICE)

# Store available models and selected model per guild
available_models: List[str] = []
default_model: str = "local-model"
selected_models: Dict[int, str] = {}

# Bot setup with message content intent
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Need this for voice channels
bot = commands.Bot(command_prefix='!', intents=intents)

async def get_recent_context(channel, limit: int = CONTEXT_MESSAGES) -> List[Dict[str, str]]:
    """Fetch recent messages from the Discord channel to provide context."""
    context = []
    try:
        async for msg in channel.history(limit=limit * 3):
            if IGNORE_BOTS and msg.author.bot:
                continue
            if msg.author == bot.user:
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

def get_guild_max_tokens(guild_id: Optional[int]) -> int:
    if guild_id and guild_id in guild_settings:
        return int(guild_settings[guild_id].get("max_tokens", -1))
    return -1

def get_guild_temperature(guild_id: Optional[int]) -> float:
    if guild_id and guild_id in guild_settings:
        return float(guild_settings[guild_id].get("temperature", 0.7))
    return 0.7

def is_guild_admin(interaction: discord.Interaction) -> bool:
    """Check if the user has admin permissions in the guild."""
    if not interaction.guild or not interaction.user:
        return False
    return interaction.user.guild_permissions.administrator

def load_guild_settings():
    global guild_settings
    if os.path.exists(GUILD_SETTINGS_FILE):
        try:
            with open(GUILD_SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                guild_settings = {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.error(f"Failed to load guild settings: {e}")
            guild_settings = {}
    else:
        guild_settings = {}


def save_guild_settings():
    try:
        with open(GUILD_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in guild_settings.items()},
                f,
                indent=2,
                ensure_ascii=False
            )
    except Exception as e:
        logger.error(f"Failed to save guild settings: {e}")

def estimate_tokens(text: str) -> int:
    """Rough estimation of tokens (approximately 4 characters per token)."""
    return len(text) // 4

def remove_thinking_tags(text: str) -> str:
    """Remove thinking tags and box markers from reasoning model outputs."""
    import re
    
    if not HIDE_THINKING:
        return text
    
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'\[THINK\].*?\[/THINK\]', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<think\s*/>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\[THINK\s*/\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<\|begin_of_box\|>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<\|end_of_box\|>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def is_inside_thinking_tags(text: str) -> bool:
    """Check if we're currently inside an unclosed thinking tag."""
    import re
    
    if not HIDE_THINKING:
        return False
    
    open_tags = len(re.findall(r'<think>', text, flags=re.IGNORECASE))
    close_tags = len(re.findall(r'</think>', text, flags=re.IGNORECASE))
    open_brackets = len(re.findall(r'\[THINK\]', text, flags=re.IGNORECASE))
    close_brackets = len(re.findall(r'\[/THINK\]', text, flags=re.IGNORECASE))
    
    return (open_tags > close_tags) or (open_brackets > close_brackets)

async def process_image_attachment(attachment) -> Optional[Dict]:
    """Download and convert an image attachment to base64 for the vision model."""
    if not attachment.content_type or not attachment.content_type.startswith('image/'):
        return None
    
    if attachment.size > MAX_IMAGE_SIZE * 1024 * 1024:
        logger.warning(f"Image too large: {attachment.size / (1024*1024):.2f}MB (max: {MAX_IMAGE_SIZE}MB)")
        return None
    
    try:
        image_data = await attachment.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
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
        logger.debug(f"  Content type was: {attachment.content_type}")
        logger.debug(f"  Filename was: {attachment.filename}")
        return None

async def process_text_attachment(attachment) -> Optional[str]:
    """Download and read a text file attachment."""
    text_extensions = ['.txt', '.md', '.py', '.js', '.java', '.c', '.cpp', '.h', '.html', 
                      '.css', '.json', '.xml', '.yaml', '.yml', '.csv', '.log', '.sh', 
                      '.bat', '.ps1', '.sql', '.r', '.php', '.go', '.rs', '.swift', '.kt']
    
    filename_lower = attachment.filename.lower()
    
    is_text = any(filename_lower.endswith(ext) for ext in text_extensions)
    if attachment.content_type:
        is_text = is_text or 'text/' in attachment.content_type or 'application/json' in attachment.content_type
    
    if not is_text:
        return None
    
    if attachment.size > MAX_TEXT_FILE_SIZE * 1024 * 1024:
        logger.warning(f"Text file too large: {attachment.size / (1024*1024):.2f}MB (max: {MAX_TEXT_FILE_SIZE}MB)")
        return None
    
    try:
        file_data = await attachment.read()
        
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                text_content = file_data.decode(encoding)
                logger.info(f"Processing text file: {attachment.filename} ({attachment.size / 1024:.2f}KB)")
                return f"\n\n--- Content of {attachment.filename} ---\n{text_content}\n--- End of {attachment.filename} ---\n"
            except UnicodeDecodeError:
                continue
        
        logger.error(f"Could not decode text file {attachment.filename}")
        return None
        
    except Exception as e:
        logger.error(f"Error processing text file {attachment.filename}: {e}")
        return None

async def fetch_available_models() -> List[str]:
    """Fetch available (loaded) models from LM Studio."""
    try:
        base_url = (
            LMSTUDIO_URL.split('/v1/')[0]
            if '/v1/' in LMSTUDIO_URL
            else LMSTUDIO_URL.rsplit('/', 1)[0]
        )

        models_url = f"{base_url}/api/v1/models"
        logger.info(f"Fetching models from: {models_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(models_url) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to fetch models: {response.status} - {await response.text()}"
                    )
                    return []

                data = await response.json()

                all_models = data.get("models", [])

                # Only return models that are actually loaded
                models = [
                    model["key"]
                    for model in all_models
                    if model.get("loaded_instances")
                ]

                if models:
                    logger.info(f"Loaded LM Studio model(s): {models}")
                else:
                    logger.warning("No loaded models found in LM Studio")

                return models

    except Exception:
        logger.error("Error fetching models from LM Studio", exc_info=True)
        return []


async def text_to_speech(text: str, voice: str = None) -> Optional[bytes]:
    """Convert text to speech using AllTalk TTS (OpenAI compatible endpoint)."""
    if not voice or voice not in AVAILABLE_VOICES:
        voice = ALLTALK_VOICE
    
    try:
        # Remove any remaining thinking tags or markers from the text
        clean_text = remove_thinking_tags(text)
        
        if not clean_text.strip():
            logger.warning("No text to speak after filtering")
            return None
        
        # Use OpenAI-compatible endpoint
        payload = {
            "model": "tts-1",
            "input": clean_text,
            "voice": voice
        }
        
        logger.info(f"Generating TTS with voice '{voice}': {clean_text[:100]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ALLTALK_URL}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    logger.info(f"Generated {len(audio_data)} bytes of audio")
                    return audio_data
                else:
                    error_text = await response.text()
                    logger.error(f"AllTalk TTS error: {response.status} - {error_text}")
                    return None
    except asyncio.TimeoutError:
        logger.error("AllTalk TTS request timed out")
        return None
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return None

async def query_lmstudio(conversation_id: int, message_text: str, channel, username: str, images: List[Dict] = None, guild_id: int = None) -> Optional[str]:
    """Send a message to LMStudio API with conversation history and return the response."""
    start_time = time.time()
    
    # Get the selected model for this guild
    model_to_use = default_model
    if guild_id and guild_id in selected_models:
        model_to_use = selected_models[guild_id]
    elif available_models:
        model_to_use = available_models[0]
    
    if len(conversation_histories[conversation_id]) == 0 and not context_loaded[conversation_id] and CONTEXT_MESSAGES > 0:
        recent_context = await get_recent_context(channel, CONTEXT_MESSAGES)
        conversation_histories[conversation_id].extend(recent_context)
        context_loaded[conversation_id] = True
        logger.info(f"Loaded {len(recent_context)} context messages")
    
    if images and len(images) > 0:
        message_content = []
        
        if message_text.strip():
            message_content.append({"type": "text", "text": message_text})
        else:
            message_content.append({"type": "text", "text": "What's in this image?"})
        
        message_content.extend(images)
        
        conversation_histories[conversation_id].append({
            "role": "user",
            "content": message_content
        })
    else:
        conversation_histories[conversation_id].append({
            "role": "user",
            "content": message_text
        })
    
    is_dm = isinstance(channel, discord.DMChannel)
    if is_dm:
        context_type = f"DM from {username} (ID: {conversation_id})"
    else:
        channel_name = getattr(channel, 'name', 'Unknown')
        guild_name = getattr(channel.guild, 'name', 'Unknown') if hasattr(channel, 'guild') else 'Unknown'
        context_type = f"#{channel_name} in {guild_name} - User: {username}"
    
    image_info = f" [with {len(images)} image(s)]" if images and len(images) > 0 else ""
    logger.info(f"[{context_type}]{image_info}")
    logger.info(f"Message: {message_text}")
    logger.info(f"Using model: {model_to_use}")
    
    if len(conversation_histories[conversation_id]) > MAX_HISTORY * 2:
        conversation_histories[conversation_id] = conversation_histories[conversation_id][-(MAX_HISTORY * 2):]
    
    api_messages = []

    # ------------------------------------------------------------------
    # ✅ INSERT SYSTEM PROMPT (per guild, persisted)
    # ------------------------------------------------------------------
    if guild_id and guild_id in guild_settings:
        system_prompt = guild_settings[guild_id].get("system_prompt")
        if system_prompt:
            api_messages.append({
                "role": "system",
                "content": system_prompt
            })
    # ------------------------------------------------------------------
    
    for msg in conversation_histories[conversation_id]:
        current_role = msg["role"]
        
        if api_messages:
            last_role = api_messages[-1]["role"]
            
            if current_role == last_role:
                if current_role == "user":
                    api_messages.append({"role": "assistant", "content": "Understood."})
                else:
                    continue
        
        api_messages.append(msg)
    
    if api_messages and api_messages[-1]["role"] == "assistant":
        api_messages.pop()
    
    logger.debug(f"Sending {len(api_messages)} messages to API:")
    for i, msg in enumerate(api_messages):
        content_preview = str(msg["content"])[:100] if isinstance(msg["content"], str) else f"[complex content with {len(msg['content'])} parts]"
        logger.debug(f"  {i+1}. {msg['role']}: {content_preview}")
    
    payload = {
        "model": model_to_use,
        "messages": api_messages,
        "temperature": get_guild_temperature(guild_id),
        "max_tokens": get_guild_max_tokens(guild_id),
        "stream": True
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(LMSTUDIO_URL, json=payload) as response:
                if response.status == 200:
                    assistant_message = ""
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        assistant_message += content
                                        yield content
                            except json.JSONDecodeError:
                                continue
                    
                    response_time = time.time() - start_time
                    
                    logger.info(f"Full Response (with thinking): {assistant_message}")
                    
                    assistant_message_filtered = remove_thinking_tags(assistant_message)
                    
                    logger.info(f"Filtered Response (shown to user): {assistant_message_filtered}")
                    logger.info(f"Response time: {response_time:.2f}s")
                    
                    if HIDE_THINKING and assistant_message != assistant_message_filtered:
                        logger.info(f"Thinking tags removed. Original length: {len(assistant_message)}, Filtered length: {len(assistant_message_filtered)}")
                    
                    conversation_histories[conversation_id].append({
                        "role": "assistant",
                        "content": assistant_message
                    })
                    
                    stats = channel_stats[conversation_id]
                    stats['total_messages'] += 2
                    stats['total_tokens_estimate'] += estimate_tokens(message_text) + estimate_tokens(assistant_message)
                    stats['last_message_time'] = datetime.now()
                    stats['response_times'].append(response_time)
                else:
                    error_text = await response.text()
                    logger.error(f"LMStudio API error: {response.status} - {error_text}")
                    conversation_histories[conversation_id].pop()
                    yield f"Error: LMStudio API returned status {response.status}"
    except aiohttp.ClientError as e:
        logger.error(f"Connection error to LMStudio: {e}")
        conversation_histories[conversation_id].pop()
        yield "Error: Could not connect to LMStudio. Is it running?"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        conversation_histories[conversation_id].pop()
        yield f"Error: {str(e)}"

@bot.tree.command(name='reset', description='Reset the conversation history for this channel or DM')
async def reset_conversation(interaction: discord.Interaction):
    """Slash command to reset the conversation history for the current channel or DM."""
    conversation_id = interaction.channel_id if interaction.guild else interaction.user.id
    
    if interaction.guild and interaction.channel_id not in CHANNEL_IDS:
        await interaction.response.send_message("❌ This command only works in monitored channels.", ephemeral=True)
        return
    
    if not interaction.guild and not ALLOW_DMS:
        await interaction.response.send_message("❌ DM conversations are not enabled.", ephemeral=True)
        return
    
    conversation_histories[conversation_id].clear()
    context_loaded[conversation_id] = False
    channel_stats[conversation_id] = {
        'total_messages': 0,
        'total_tokens_estimate': 0,
        'start_time': datetime.now(),
        'last_message_time': None,
        'response_times': []
    }
    await interaction.response.send_message("✅ Conversation history and statistics have been reset. Starting fresh!", ephemeral=True)

@bot.tree.command(name='history', description='Show the conversation history length')
async def show_history(interaction: discord.Interaction):
    """Slash command to show how many messages are in the current channel's or DM's history."""
    conversation_id = interaction.channel_id if interaction.guild else interaction.user.id
    
    if interaction.guild and interaction.channel_id not in CHANNEL_IDS:
        await interaction.response.send_message("❌ This command only works in monitored channels.", ephemeral=True)
        return
    
    if not interaction.guild and not ALLOW_DMS:
        await interaction.response.send_message("❌ DM conversations are not enabled.", ephemeral=True)
        return
    
    msg_count = len(conversation_histories[conversation_id])
    await interaction.response.send_message(
        f"📊 This conversation has {msg_count} messages in its history (max: {MAX_HISTORY * 2}).",
        ephemeral=True
    )

@bot.tree.command(name='stats', description='Show conversation statistics')
async def show_stats(interaction: discord.Interaction):
    """Slash command to show conversation statistics."""
    conversation_id = interaction.channel_id if interaction.guild else interaction.user.id
    
    if interaction.guild and interaction.channel_id not in CHANNEL_IDS:
        await interaction.response.send_message("❌ This command only works in monitored channels.", ephemeral=True)
        return
    
    if not interaction.guild and not ALLOW_DMS:
        await interaction.response.send_message("❌ DM conversations are not enabled.", ephemeral=True)
        return
    
    stats = channel_stats[conversation_id]
    
    avg_response_time = 0
    if stats['response_times']:
        avg_response_time = sum(stats['response_times']) / len(stats['response_times'])
    
    duration = datetime.now() - stats['start_time']
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    last_msg = "Never"
    if stats['last_message_time']:
        last_msg = stats['last_message_time'].strftime("%Y-%m-%d %H:%M:%S")
    
    stats_message = f"""📈 **Conversation Statistics**
    
**Total Messages:** {stats['total_messages']}
**Estimated Tokens:** {stats['total_tokens_estimate']:,}
**Session Duration:** {hours}h {minutes}m {seconds}s
**Average Response Time:** {avg_response_time:.2f}s
**Last Message:** {last_msg}
**Messages in History:** {len(conversation_histories[conversation_id])}
    """
    
    await interaction.response.send_message(stats_message, ephemeral=True)

@bot.tree.command(name='join', description='Join your voice channel')
async def join_voice(interaction: discord.Interaction):
    """Join the voice channel the user is currently in."""
    if not ENABLE_TTS:
        await interaction.response.send_message("❌ TTS is currently disabled in the bot configuration.", ephemeral=True)
        return
    
    # Check if user is in a voice channel
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You need to be in a voice channel first!", ephemeral=True)
        return
    
    voice_channel = interaction.user.voice.channel
    guild_id = interaction.guild.id
    
    # Check if already connected
    if guild_id in voice_clients and voice_clients[guild_id].is_connected():
        if voice_clients[guild_id].channel.id == voice_channel.id:
            await interaction.response.send_message("✅ Already in your voice channel!", ephemeral=True)
            return
        else:
            # Move to the new channel
            await voice_clients[guild_id].move_to(voice_channel)
            await interaction.response.send_message(f"✅ Moved to {voice_channel.name}!", ephemeral=True)
            logger.info(f"Moved to voice channel: {voice_channel.name} in {interaction.guild.name}")
            return
    
    try:
        # Connect to voice channel
        voice_client = await voice_channel.connect()
        voice_clients[guild_id] = voice_client
        await interaction.response.send_message(f"✅ Joined {voice_channel.name}! I'll speak my responses here.", ephemeral=True)
        logger.info(f"Joined voice channel: {voice_channel.name} in {interaction.guild.name}")
    except Exception as e:
        logger.error(f"Error joining voice channel: {e}")
        await interaction.response.send_message(f"❌ Failed to join voice channel: {str(e)}", ephemeral=True)

@bot.tree.command(name='leave', description='Leave the voice channel')
async def leave_voice(interaction: discord.Interaction):
    """Leave the current voice channel."""
    if not ENABLE_TTS:
        await interaction.response.send_message("❌ TTS is currently disabled in the bot configuration.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    
    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
        return
    
    try:
        await voice_clients[guild_id].disconnect()
        del voice_clients[guild_id]
        await interaction.response.send_message("✅ Left the voice channel.", ephemeral=True)
        logger.info(f"Left voice channel in {interaction.guild.name}")
    except Exception as e:
        logger.error(f"Error leaving voice channel: {e}")
        await interaction.response.send_message(f"❌ Failed to leave voice channel: {str(e)}", ephemeral=True)

class VoiceSelectView(discord.ui.View):
    """View with dropdown for voice selection."""
    def __init__(self, current_voice: str):
        super().__init__(timeout=60)
        self.add_item(VoiceSelectDropdown(current_voice))

class VoiceSelectDropdown(discord.ui.Select):
    """Dropdown menu for selecting TTS voice."""
    def __init__(self, current_voice: str):
        options = [
            discord.SelectOption(
                label=voice.capitalize(),
                value=voice,
                description=f"OpenAI voice: {voice}",
                default=(voice == current_voice)
            )
            for voice in AVAILABLE_VOICES
        ]
        
        super().__init__(
            placeholder="Select a voice...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_voice = self.values[0]
        guild_id = interaction.guild.id
        selected_voices[guild_id] = selected_voice
        
        await interaction.response.send_message(
            f"✅ Voice changed to: **{selected_voice}**",
            ephemeral=True
        )
        logger.info(f"Voice changed to '{selected_voice}' in {interaction.guild.name}")

@bot.tree.command(name='voice', description='Select TTS voice')
async def select_voice(interaction: discord.Interaction):
    """Show dropdown to select TTS voice."""
    if not ENABLE_TTS:
        await interaction.response.send_message("❌ TTS is currently disabled in the bot configuration.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    current_voice = selected_voices.get(guild_id, ALLTALK_VOICE)
    
    view = VoiceSelectView(current_voice)
    await interaction.response.send_message(
        f"**Current voice:** {current_voice}\n\n**Available voices:**\n"
        f"• **alloy** - Neutral and balanced\n"
        f"• **echo** - Clear and expressive\n"
        f"• **fable** - Warm and engaging\n"
        f"• **nova** - Energetic and bright\n"
        f"• **onyx** - Deep and authoritative\n"
        f"• **shimmer** - Soft and soothing\n\n"
        f"Select a new voice:",
        view=view,
        ephemeral=True
    )

class ModelSelectView(discord.ui.View):
    """View with dropdown for model selection."""
    def __init__(self, current_model: str):
        super().__init__(timeout=60)
        self.add_item(ModelSelectDropdown(current_model))

class ModelSelectDropdown(discord.ui.Select):
    """Dropdown menu for selecting AI model."""
    def __init__(self, current_model: str):
        if not available_models:
            options = [discord.SelectOption(label="No models available", value="none")]
        else:
            options = [
                discord.SelectOption(
                    label=model,
                    value=model,
                    default=(model == current_model)
                )
                for model in available_models[:25]  # Discord limit
            ]
        
        super().__init__(
            placeholder="Select a model...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No models available.", ephemeral=True)
            return
        
        selected_model = self.values[0]
        guild_id = interaction.guild.id
        selected_models[guild_id] = selected_model
        
        await interaction.response.send_message(
            f"✅ Model changed to: **{selected_model}**",
            ephemeral=True
        )
        logger.info(f"Model changed to '{selected_model}' in {interaction.guild.name}")

@bot.tree.command(name='model', description='Select AI model')
async def select_model(interaction: discord.Interaction):
    """Show dropdown to select AI model."""
    await interaction.response.defer(ephemeral=True)
    
    # Refresh available models
    global available_models, default_model
    models = await fetch_available_models()
    
    if models:
        available_models = models
        if not default_model or default_model == "local-model":
            default_model = models[0]
    
    if not available_models:
        await interaction.followup.send(
            "❌ No models found in LMStudio. Please load a model first.",
            ephemeral=True
        )
        return
    
    guild_id = interaction.guild.id
    current_model = selected_models.get(guild_id, default_model)
    
    view = ModelSelectView(current_model)
    await interaction.followup.send(
        f"**Current model:** {current_model}\n\n**Available models:**\n" + 
        "\n".join(f"• {model}" for model in available_models) + 
        "\n\nSelect a new model:",
        view=view,
        ephemeral=True
    )

@bot.tree.command(name="config", description="Configure bot settings for this server")
async def config(
    interaction: discord.Interaction,
    category: str,
    action: str,
    value: Optional[str] = None
):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Configuration is only available in servers.",
            ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    # ---------------- SYSTEM PROMPT ----------------
    if category.lower() == "system":
        if action.lower() == "show":
            current = guild_settings.get(guild_id, {}).get("system_prompt")
            if current:
                await interaction.response.send_message(
                    f"🧠 **System prompt:**\n```{current}```",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ No system prompt set.",
                    ephemeral=True
                )
            return

        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can modify the system prompt.",
                ephemeral=True
            )
            return

        if action.lower() == "clear":
            guild_settings.get(guild_id, {}).pop("system_prompt", None)
            save_guild_settings()
            await interaction.response.send_message(
                "✅ System prompt cleared.",
                ephemeral=True
            )
            return

        if action.lower() == "set":
            if not value or not value.strip():
                await interaction.response.send_message(
                    "❌ Please provide a system prompt.",
                    ephemeral=True
                )
                return

            guild_settings.setdefault(guild_id, {})["system_prompt"] = value.strip()
            save_guild_settings()
            await interaction.response.send_message(
                "✅ System prompt updated.",
                ephemeral=True
            )
            return

    # ---------------- TEMPERATURE ----------------
    if category.lower() == "temperature":
        if action.lower() == "show":
            temp = get_guild_temperature(guild_id)
            await interaction.response.send_message(
                f"🌡️ Current temperature: **{temp}**",
                ephemeral=True
            )
            return

        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can change temperature.",
                ephemeral=True
            )
            return

        if action.lower() == "reset":
            guild_settings.get(guild_id, {}).pop("temperature", None)
            save_guild_settings()
            await interaction.response.send_message(
                "✅ Temperature reset to default (0.7).",
                ephemeral=True
            )
            return

        if action.lower() == "set":
            try:
                temp = float(value)
                if not 0.0 <= temp <= 2.0:
                    raise ValueError
            except Exception:
                await interaction.response.send_message(
                    "❌ Temperature must be a number between 0.0 and 2.0.",
                    ephemeral=True
                )
                return

            guild_settings.setdefault(guild_id, {})["temperature"] = temp
            save_guild_settings()
            await interaction.response.send_message(
                f"✅ Temperature set to **{temp}**.",
                ephemeral=True
            )
            return

    # ---------------- MAX TOKENS ----------------
    if category.lower() == "max_tokens":
        if action.lower() == "show":
            current = get_guild_max_tokens(guild_id)
            display = "unlimited" if current == -1 else str(current)
            await interaction.response.send_message(
                f"📏 Current max_tokens: **{display}**",
                ephemeral=True
            )
            return

        if not is_guild_admin(interaction):
            await interaction.response.send_message(
                "❌ Only admins can change max_tokens.",
                ephemeral=True
            )
            return

        if action.lower() == "reset":
            guild_settings.get(guild_id, {}).pop("max_tokens", None)
            save_guild_settings()
            await interaction.response.send_message(
                "✅ max_tokens reset to unlimited.",
                ephemeral=True
            )
            return

        if action.lower() == "set":
            try:
                value_int = int(value)
                if value_int <= 0 and value_int != -1:
                    raise ValueError
            except Exception:
                await interaction.response.send_message(
                    "❌ max_tokens must be a positive integer or `-1` (unlimited).",
                    ephemeral=True
                )
                return

            guild_settings.setdefault(guild_id, {})["max_tokens"] = value_int
            save_guild_settings()

            display = "unlimited" if value_int == -1 else str(value_int)
            await interaction.response.send_message(
                f"✅ max_tokens set to **{display}**.",
                ephemeral=True
            )
            return

    # ---------------- CLEAR LAST ----------------
    if category.lower() == "clear" and action.lower() == "last":
        conversation_id = interaction.channel_id

        history = conversation_histories.get(conversation_id, [])
        if not history:
            await interaction.response.send_message(
                "ℹ️ No conversation history to clear.",
                ephemeral=True
            )
            return

        # Remove last assistant + user messages
        removed = 0
        while history and removed < 2:
            if history[-1]["role"] in {"assistant", "user"}:
                history.pop()
                removed += 1
            else:
                break

        await interaction.response.send_message(
            "🧹 Last interaction removed.",
            ephemeral=True
        )
        logger.info(f"Cleared last interaction in channel {interaction.channel_id}")
        return

    # ---------------- FALLBACK ----------------
    await interaction.response.send_message(
        "❌ Invalid config command.\n\n"
        "**Usage examples:**\n"
        "`/config system show`\n"
        "`/config system set <prompt>`\n"
        "`/config temperature set 0.3`\n"
        "`/config clear last`",
        ephemeral=True
    )

@bot.tree.command(name="help", description="Show all available bot commands")
async def help_command(interaction: discord.Interaction):
    help_text = """
🤖 **Jarvis – Help**

---
### 💬 Core Commands
• Just type a message in a monitored channel or DM to chat with the AI  
• Attach images or text files to include them in the prompt  
• Prefix a message with `*` to prevent the bot from responding

---
### ⚙️ Configuration (`/config`)
*(Some options require admin permissions)*

**System prompt**
• `/config system show`  
• `/config system set <prompt>` *(admin)*  
• `/config system clear` *(admin)*  

**Temperature**
• `/config temperature show`  
• `/config temperature set <0.0–2.0>` *(admin)*  
• `/config temperature reset` *(admin)*  

**Max tokens**
• `/config max_tokens show`  
• `/config max_tokens set <number | -1>` *(admin)*  
• `/config max_tokens reset` *(admin)*  

**Conversation tools**
• `/config clear last` – Remove the last user/assistant exchange

---
### 🧠 Model Management
• `/model` – Select the active AI model for this server

---
### 🔊 Voice / TTS
• `/join` – Join your current voice channel  
• `/leave` – Leave the voice channel  
• `/voice` – Select the TTS voice  

---
### 📊 Utilities
• `/reset` – Reset conversation history  
• `/history` – Show conversation history size  
• `/stats` – Show conversation statistics  

---
### ℹ️ Notes
• Settings are saved per server and persist across restarts  
• System prompts affect **all users** in the server  
• Temperature and max_tokens affect response style and length  

---
"""
    await interaction.response.send_message(help_text, ephemeral=True)

@bot.event
async def on_ready():
    load_guild_settings()
    logger.info(f"Loaded settings for {len(guild_settings)} guild(s)")

    """Called when the bot successfully connects to Discord."""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} server(s)')
    logger.info(f'Listening in {len(CHANNEL_IDS)} channel(s): {CHANNEL_IDS}')
    logger.info(f'LMStudio URL: {LMSTUDIO_URL}')
    
    # Fetch available models from LMStudio
    global available_models, default_model
    models = await fetch_available_models()
    if models:
        available_models = models
        default_model = models[0]
        logger.info(f'Default model set to: {default_model}')
    else:
        logger.warning('No models found in LMStudio. Please load a model.')
    
    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel:
            logger.info(f'  - #{channel.name} in {channel.guild.name}')
        else:
            logger.warning(f'  - Channel ID {channel_id} not found (bot may not have access)')
    
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} slash command(s)')
    except Exception as e:
        logger.error(f'Failed to sync slash commands: {e}')
    
    logger.info(f'IGNORE_BOTS setting: {IGNORE_BOTS}')
    logger.info(f'CONTEXT_MESSAGES setting: {CONTEXT_MESSAGES}')
    logger.info(f'ALLOW_DMS setting: {ALLOW_DMS}')
    logger.info(f'ALLOW_IMAGES setting: {ALLOW_IMAGES}')
    logger.info(f'MAX_IMAGE_SIZE setting: {MAX_IMAGE_SIZE}MB')
    logger.info(f'ALLOW_TEXT_FILES setting: {ALLOW_TEXT_FILES}')
    logger.info(f'MAX_TEXT_FILE_SIZE setting: {MAX_TEXT_FILE_SIZE}MB')
    logger.info(f'HIDE_THINKING setting: {HIDE_THINKING}')
    logger.info(f'ENABLE_TTS setting: {ENABLE_TTS}')
    logger.info(f'ALLTALK_URL setting: {ALLTALK_URL}')
    logger.info(f'ALLTALK_VOICE setting: {ALLTALK_VOICE}')
    logger.info(f'Logging to: {log_filename}')

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
    if not message.content.strip():
        return
    
    # Process any attachments if enabled
    images = []
    text_files_content = ""
    
    if message.attachments:
        for attachment in message.attachments:
            if ALLOW_IMAGES:
                image_data = await process_image_attachment(attachment)
                if image_data:
                    images.append(image_data)
                    continue
            
            if ALLOW_TEXT_FILES:
                text_content = await process_text_attachment(attachment)
                if text_content:
                    text_files_content += text_content
    
    if not message.content.strip() and not images and not text_files_content:
        return
    
    combined_message = message.content
    if text_files_content:
        combined_message = f"{message.content}\n{text_files_content}" if message.content.strip() else text_files_content
    
    status_msg = await message.channel.send("🤔 Thinking...")
    
    try:
        response_text = ""
        last_update = time.time()
        update_interval = 1.0
        
        username = message.author.display_name
        
        # Get guild_id for model selection (None for DMs)
        guild_id = message.guild.id if not is_dm else None
        
        async for chunk in query_lmstudio(conversation_id, combined_message, message.channel, username, images, guild_id):
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
        
        if response_text:
            final_response = remove_thinking_tags(response_text)
            
            if final_response.strip():
                if len(final_response) > 2000:
                    await status_msg.delete()
                    chunks = [final_response[i:i+2000] for i in range(0, len(final_response), 2000)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await status_msg.edit(content=final_response)
                
                # If bot is in a voice channel in this guild, speak the response
                if ENABLE_TTS and not is_dm and message.guild.id in voice_clients:
                    voice_client = voice_clients[message.guild.id]
                    if voice_client.is_connected() and not voice_client.is_playing():
                        try:
                            guild_voice = selected_voices.get(message.guild.id, ALLTALK_VOICE)
                            audio_data = await text_to_speech(final_response, guild_voice)
                            
                            if audio_data:
                                # Save audio to temporary file
                                temp_audio = f"temp_tts_{message.guild.id}.mp3"
                                with open(temp_audio, 'wb') as f:
                                    f.write(audio_data)
                                
                                # Play audio
                                voice_client.play(
                                    discord.FFmpegPCMAudio(temp_audio),
                                    after=lambda e: os.remove(temp_audio) if os.path.exists(temp_audio) else None
                                )
                                logger.info(f"Playing TTS audio in voice channel")
                        except Exception as e:
                            logger.error(f"Error playing TTS: {e}")
            else:
                await status_msg.edit(content="_[Response contained only thinking process]_")
        else:
            await status_msg.edit(content="Sorry, I couldn't generate a response.")
            
    except Exception as e:
        logger.error(f"Error in on_message: {e}", exc_info=True)
        try:
            await status_msg.edit(content="An error occurred while processing your message.")
        except:
            pass

# Run the bot
if __name__ == "__main__":
    if DISCORD_TOKEN == 'your-discord-bot-token-here':
        logger.error("Please set your DISCORD_BOT_TOKEN environment variable")
        logger.info("You can create a bot at: https://discord.com/developers/applications")
    elif not CHANNEL_IDS or CHANNEL_IDS == {0}:
        logger.error("Please set your DISCORD_CHANNEL_IDS environment variable")
        logger.info("Right-click channels in Discord (with Developer Mode on) and click 'Copy ID'")
        logger.info("Format: DISCORD_CHANNEL_IDS=123456789,987654321,111222333")
    else:
        logger.info("Starting bot...")
        bot.run(DISCORD_TOKEN)