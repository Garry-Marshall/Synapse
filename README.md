# 🤖 Discord AI Bot with LMStudio Integration

A powerful, modular Discord bot with local AI integration via LMStudio, featuring web search, file processing, text-to-speech, AI image generation, and comprehensive per-server configuration with SQLite persistence.

**[Features](#-features)** • **[Quick Start](#-quick-start)** • **[Commands](#-slash-commands)** • **[Configuration](#️-configuration)** • **[Troubleshooting](#-troubleshooting)**
---

## ✨ Features

### 🧠 AI Capabilities
- ✅ Local LLM Integration via LMStudio API
- ✅ Model Selection - Switch between loaded models per server
- ✅ Context-Aware Conversations - Maintains conversation history with rolling window
- ✅ Reasoning Model Support - Automatically handles `<think>` tags
- ✅ Multi-modal Support - Vision models for image analysis

### 🔍 Enhanced Input Processing
- ✅ **Web Search** - Automatic web search with cooldown management
- ✅ **URL Content Fetching** - Extracts text from provided URLs
- ✅ **Image Processing** - Vision model support (PNG, JPG, GIF, WebP)
- ✅ **PDF Processing** - Extracts and reads PDF content with character limits
- ✅ **Text File Support** - Reads code files, documents, and more

### 🎙️ Voice & TTS
- ✅ **Voice Channel Integration** - Bot joins and speaks in voice channels
- ✅ **Multiple Voices** - 6 OpenAI-compatible voices via AllTalk TTS
- ✅ **Moshi AI Voice** - Real-time AI voice conversations with custom prompts
- ✅ **Auto-Disconnect** - Leaves when alone in voice channel
- ✅ **Per-Server TTS Toggle** - Enable/disable TTS per guild
- ✅ **Per-Server Moshi Prompts** - Customize Moshi's personality per server

### 🎨 Image Generation
- ✅ **ComfyUI Integration** - Generate images using ComfyUI workflows
- ✅ **Trigger Word Detection** - Use 'imagine' or 'generate' keywords
- ✅ **Per-Server Toggle** - Enable/disable image generation per guild
- ✅ **Customizable Workflows** - Use your own ComfyUI workflow JSON files

### ⚙️ Server Configuration
- ✅ **Channel Monitoring** - Select specific channels for bot responses
- ✅ **Custom System Prompts** - Per-server AI personality
- ✅ **Temperature Control** - Adjust response creativity (0.0-2.0)
- ✅ **Token Limits** - Control response length
- ✅ **Debug Logging** - Per-server debug modes with level control
- ✅ **Web Search Toggle** - Enable/disable per server
- ✅ **TTS Toggle** - Enable/disable TTS per server
- ✅ **Image Generation Toggle** - Enable/disable ComfyUI per server

### 📊 Statistics & Management
- ✅ **Conversation Stats** - Track tokens, response times, messages, tool usage
- ✅ **History Management** - Clear, reset, or view conversation history
- ✅ **Persistent Storage** - SQLite database for settings and stats
- ✅ **Context Analysis** - Shows token usage with rolling window support
- ✅ **Health Check** - Monitor bot status and service health
- ✅ **Automatic Migration** - Migrates from old JSON files to database

---

## 📁 Project Structure

```
discord_bot/
│
├── 📄 bot.py                    # Main entry point
├── 📄 requirements.txt          # Python dependencies
├── 📄 .env                      # Configuration
├── 📄 synapse_bot.db             # SQLite database (auto-created)
│
├── 📂 config/                   # Settings and constants
│   ├── settings.py
│   ├── constants.py
│   └── __init__.py
│
├── 📂 utils/                    # Helper functions
│   ├── logging_config.py
│   ├── text_utils.py
│   ├── stats_manager.py
│   ├── settings_manager.py
│   ├── database.py              # SQLite database layer
│   ├── file_utils.py
│   ├── image_utils.py           # ComfyUI integration
│   ├── opus_transcoder.py       # Opus audio transcoding
│   ├── ogg_opus_parser.py       # Ogg container parsing
│   ├── ogg_opus_writer_v2.py    # Ogg container writer
│   ├── permissions.py
│   └── __init__.py
│
├── 📂 services/                # Business logic
│   ├── lmstudio.py             # LMStudio API integration
│   ├── tts.py                  # Text-to-speech
│   ├── moshi.py                # Moshi AI voice assistant
│   ├── moshi_voice_handler.py  # Moshi Discord integration
│   ├── comfyui.py              # Image generation
│   ├── search.py               # Web search (DDGS)
│   ├── content_fetch.py        # URL content fetching
│   ├── file_processor.py       # File processing
│   ├── message_processor.py    # Message processing
│   └── __init__.py
│
├── 📂 commands/                # Slash commands
│   ├── stats.py                # /stats command
│   ├── status.py               # /status command
│   ├── voice.py                # /join, /leave, /voice
│   ├── model.py                # /model selection
│   ├── config_cmd.py           # /config command
│   ├── context_cmd.py          # /context command
│   ├── help.py                 # /help command
│   ├── channel_management.py   # Channel monitoring commands
│   └── __init__.py
│
├── 📂 core/                    # Bot core
│   ├── bot_instance.py         # Bot setup
│   ├── events.py               # Event handlers
│   ├── shutdown_handler.py     # Graceful shutdown
│   └── __init__.py
│
└── 📂 comfyUI-workflows/       # ComfyUI workflow files
    └── workflow_flux_api.json  # Example Flux workflow
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Link |
|------------|---------|------|
| Python | 3.9+ | [Download](https://www.python.org/downloads/) |
| Discord Bot | Token Required | [Create Bot](https://discord.com/developers/applications) |
| LMStudio | Latest | [Download](https://lmstudio.ai/) |
| AllTalk TTS | Optional | [Download](https://github.com/erew123/alltalk_tts/tree/alltalkbeta) |
| PersonaPlex | Optional | [Download](https://github.com/NVIDIA/personaplex) |
| ComfyUI | Optional | [Download](https://github.com/comfyanonymous/ComfyUI) |

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/Garry-Marshall/Synapse
   cd Synapse
   ```

2. **Create Virtual Environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Linux/Mac:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Bot**

   The `.env` file will be created automatically on first run. Edit it to add your Discord bot token:

   ```env
   # REQUIRED: Your Discord bot token
   DISCORD_BOT_TOKEN=your-discord-bot-token-here

   # Database file (auto-created)
   DB_FILE=synapse_bot.db

    # Logging and Debug Settings
    DEBUG=true
    DEBUG_LEVEL=info # options: info, debug

    # Permission system (optional but recommended)
    # Bot owner user IDs (comma-separated Discord user IDs)
    BOT_OWNER_IDS=123456789012345678,987654321098765432
    # Default bot admin role name
    # BOT_ADMIN_ROLE_NAME=Bot Admin

   # LMStudio API Configuration
   LMSTUDIO_URL=http://localhost:1234/v1/chat/completions

   # Bot behavior
   MAX_HISTORY_MESSAGES=10
   CONTEXT_MESSAGES=5
   IGNORE_BOTS=true
   ALLOW_DMS=true

   # File processing
   ALLOW_IMAGES=true
   MAX_IMAGE_SIZE=5
   ALLOW_TEXT_FILES=true
   MAX_TEXT_FILE_SIZE=2
   ALLOW_PDF=true
   MAX_PDF_SIZE=10

   # Model settings
   HIDE_THINKING=true

   # TTS settings (optional)
   ENABLE_TTS=false
   ALLTALK_URL=http://127.0.0.1:7851
   ALLTALK_VOICE=alloy

   # PersonaPlex (Moshi) Voice AI settings (optional)
   ENABLE_MOSHI=false
   MOSHI_URL=https://127.0.0.1:8998
   MOSHI_VOICE=NATF2.pt  # Female voices: NATF0-3.pt, Male voices: NATM0-3.pt
   MOSHI_TEXT_PROMPT=You are a helpful AI assistant.

   # ComfyUI settings (optional)
   ENABLE_COMFYUI=false
   COMFYUI_URL=127.0.0.1:8188
   COMFYUI_WORKFLOW=comfyUI-workflows/workflow_flux_api.json
   COMFYUI_PROMPT_NODES=6
   COMFYUI_RAND_SEED_NODES=36
   COMFYUI_TRIGGERS=imagine,generate
   ```

   **Permission System Setup:**

   The bot includes a three-tier permission system for better security:

   1. **Bot Owners** (highest) - Full access to all commands
      - Set your Discord user ID(s) in `BOT_OWNER_IDS`
      - To find your Discord user ID: Enable Developer Mode (User Settings → Advanced → Developer Mode), then right-click your username and select "Copy User ID"
      - Multiple owners: `BOT_OWNER_IDS=123456789,987654321`

   2. **Bot Admin Role** (medium) - Server-specific bot administration
      - Create a role named "Bot Admin" (or customize with `BOT_ADMIN_ROLE_NAME`)
      - Users with this role can use `/config` and other admin commands
      - Separates bot management from full Discord server admin

   3. **Discord Administrator** (basic) - Falls back to Discord's admin permission
      - Users with Discord's Administrator permission can use admin commands
      - Least privileged of the admin tiers

5. **Run the Bot**
   ```bash
   python bot.py
   ```
   
   Expected output:
   ```
   [INFO] Bot has connected to Discord!
   [INFO] Loaded LM Studio model(s): ['your-model-name']
   [INFO] Synced X slash command(s)
   ```

---

## 📖 Usage

### 💬 Basic Conversation

Simply type in a monitored channel or DM the bot:

```
User: What is the weather like today?
Bot: 🤔 Thinking...
Bot: [Searches web and responds with weather info]
```

**With images:**
```
User: [uploads sunset.jpg] What's in this image?
Bot: I can see a beautiful sunset over the ocean...
```

**With PDFs:**
```
User: [uploads report.pdf] Summarize this document
Bot: This document discusses quarterly sales performance...
```

**Image Generation:**
```
User: imagine a sunset over mountains
Bot: [Generating image...] ⏳ This may take a minute...
Bot: [Shows generated image]
```

### 🎮 Slash Commands

#### 📊 Statistics & Monitoring

- `/stats` - Display detailed conversation statistics
  - Track total messages, tokens, response times
  - Monitor tool usage (web searches, images analyzed, PDFs read, TTS replies, images generated)
- `/context` - Show token usage and context window analysis
- `/status` - Display bot health and system status
  - Check LMStudio, AllTalk TTS, and ComfyUI connectivity
  - View system resources and bot statistics
- `/help` - Show all available commands

#### ⚙️ Configuration (Admin Only)

- `/config` - Open interactive configuration panel
  - Edit system prompt
  - Adjust temperature (0.0-2.0)
  - Set max tokens
  - Toggle debug mode
  - Set debug level (info/debug)
  - Toggle web search
  - Toggle TTS
  - Toggle image generation (ComfyUI)
  - Clear conversation history
  - Reset to defaults

#### 📡 Channel Management (Admin Only)

- `/add_channel` - Add current channel to monitored channels
- `/remove_channel` - Remove current channel from monitoring
- `/list_channels` - List all monitored channels in server

#### 🧠 Model & Voice

- `/model` - Select AI model from dropdown
- `/voice` - Choose TTS voice (alloy, echo, fable, nova, onyx, shimmer)
- `/join` - Join your current voice channel
- `/leave` - Leave voice channel

#### 🎙️ Moshi AI Voice

- `/moshi start` - Start real-time AI voice conversation
- `/moshi stop` - Stop AI voice conversation
- `/moshi prompt` - Customize Moshi's system prompt (per-server)
- `/moshi status` - Check Moshi service availability and connection status

---

## ⚙️ Configuration

### 🌡️ Temperature Settings

Control response creativity and randomness:

| Temperature | Behavior | Best For |
|------------|----------|----------|
| 0.0 - 0.3 | Focused, deterministic | Code, facts, technical content |
| 0.4 - 0.7 | Balanced (default: 0.7) | General conversation |
| 0.8 - 1.2 | Creative, varied | Brainstorming, creative writing |
| 1.3 - 2.0 | Highly creative | Experimental, artistic content |

### 📝 System Prompts

Set custom AI personalities per server:

```
Example: "You are a helpful Python coding assistant."
Example: "You always respond as a pirate."
```

### 💾 Database Storage

The bot uses SQLite for persistent storage:

- **`synapse_bot.db`** - Main database (auto-created)
  - Guild settings (system prompts, temperature, etc.)
  - Conversation statistics
  - Monitored channels per guild

**Migration:** Old JSON files (`channel_stats.json`, `guild_settings.json`) are automatically migrated to the database on first run and backed up.

---

## 🛠 Troubleshooting

### Bot doesn't respond to messages

**Possible causes:**

1. **Channel not monitored**
   - Use `/add_channel` in the desired channel
   - Check with `/list_channels`

2. **Missing permissions**
   - Bot needs: Read Messages, Send Messages, Embed Links, Attach Files
   - Check Server Settings → Roles → Bot Role

3. **Wrong bot invite**
   - Use invite URL with correct permissions:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=412317273088&scope=bot%20applications.commands
   ```

### "No models found in LMStudio"

**Solution:**
1. Open LMStudio application
2. Navigate to "Models" tab
3. Click "Load Model" for your desired model
4. Wait for model to fully load (100%)
5. Start the server under "Developer"
6. Restart the Discord bot

### Import errors / Module not found

**Solution:**
- Always run from project root:
  ```bash
  cd Synapse
  python bot.py
  ```

### Slash commands not appearing

**Solution:**
1. Refresh Discord (Ctrl+R)
2. Wait up to 1 hour (Discord caches globally)
3. Check logs for: `[INFO] Synced X slash command(s)`

### Voice/TTS not working

**Checklist:**
- [ ] `ENABLE_TTS=true` in `.env`
- [ ] AllTalk TTS running at `ALLTALK_URL`
- [ ] TTS enabled in server via `/config`
- [ ] Bot in voice channel (`/join`)
- [ ] Bot has Connect and Speak permissions
- [ ] FFmpeg installed

**Install FFmpeg:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html
```

### ComfyUI image generation not working

**Checklist:**
- [ ] `ENABLE_COMFYUI=true` in `.env`
- [ ] ComfyUI running at `COMFYUI_URL`
- [ ] Image generation enabled in server via `/config`
- [ ] Trigger words used ('imagine' or 'generate' by default)
- [ ] ComfyUI workflow JSON file exists at configured path
- [ ] ComfyUI has required models loaded (e.g., Flux)

**Check ComfyUI status:**
1. Open `http://127.0.0.1:8188` in browser
2. Load your workflow manually to test
3. Check ComfyUI console for errors
4. Verify node IDs in `.env` match your workflow

**Common issues:**
- **"No images returned"**: Workflow failed - check ComfyUI console
- **Missing models**: Download required models in ComfyUI
- **Wrong node IDs**: Update `COMFYUI_PROMPT_NODES` and `COMFYUI_RAND_SEED_NODES` to match your workflow

### Moshi AI Voice not working

**Checklist:**
- [ ] `ENABLE_MOSHI=true` in `.env`
- [ ] Moshi server running at `MOSHI_URL`
- [ ] Bot in voice channel (`/moshi start` automatically joins)
- [ ] Bot has Connect, Speak, and Use Voice Activity permissions
- [ ] `discord-ext-voice-recv` package installed (included in requirements.txt)

**Check Moshi status:**
1. Use `/moshi status` to verify server connectivity
2. Test Moshi server manually at the configured URL
3. Check bot logs for WebSocket connection errors
4. Verify `MOSHI_URL` uses correct protocol (ws:// or wss://)

**Common issues:**
- **"Failed to start Moshi"**: Server not running or URL incorrect
- **No audio response**: Check Moshi server logs for errors
- **Audio quality issues**: Verify network latency and server performance
- **Custom prompt not working**: Use `/moshi prompt` to set per-server prompt

**Voice settings:**
- **Female voices**: NATF0.pt, NATF1.pt, NATF2.pt, NATF3.pt
- **Male voices**: NATM0.pt, NATM1.pt, NATM2.pt, NATM3.pt
- Configure via `MOSHI_VOICE` in `.env`

---

## 🔒 Security Best Practices

⚠️ **IMPORTANT:** Follow these security guidelines

### Environment Variables
- ✅ **DO:** Keep `.env` file in `.gitignore`
- ✅ **DO:** Use separate tokens for dev/production
- ❌ **DON'T:** Commit `.env` to version control
- ❌ **DON'T:** Share your bot token publicly

### Token Exposed?

If your bot token is accidentally exposed:
1. Immediately regenerate in Discord Developer Portal
2. Update `.env` with new token
3. Restart bot
4. Review bot's recent activity

### Permissions

- Use principle of least privilege
- Only grant permissions the bot actually needs
- Review regularly and audit bot permissions
- Test in dev server first before production

---

## 🤝 Contributing

We welcome contributions! Here's how to help:

### 🐛 Bug Reports

Please include:
- Bot version or commit hash
- Python version: `python --version`
- OS: Windows/Mac/Linux
- Error logs from `Logs/` directory
- Steps to reproduce

### 💡 Feature Requests

Describe:
- Use case: What problem does this solve?
- Proposed solution: How should it work?
- Alternatives considered: Other approaches?

### Development Workflow

1. Fork the repository
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Make changes with clear, focused commits
4. Test thoroughly in a dev server
5. Update docs if needed (README, docstrings)
6. Submit PR with description of changes

### Code Guidelines

- Follow existing code style
- Add docstrings to new functions
- Update README.md for user-facing changes
- Keep commits atomic and well-described

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

**TL;DR:** You can use, modify, and distribute this code freely, just keep the copyright notice.

---

## 🙏 Acknowledgments

This project is built on these amazing open-source projects:

| [discord.py](https://github.com/Rapptz/discord.py) | [LMStudio](https://lmstudio.ai/) | [AllTalk TTS](https://github.com/erew123/alltalk_tts/tree/alltalkbeta) |
|:---:|:---:|:---:|
| Discord API wrapper | Local LLM runtime | Text-to-Speech |

| [PersonaPlex](https://github.com/NVIDIA/personaplex) | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | [DDGS](https://github.com/deedy5/ddgs) |
|:---:|:---:|:---:|
| AI Voice Assistant (Moshi) | Image generation | Privacy-first search |

| [Trafilatura](https://github.com/adbar/trafilatura) | [PyPDF](https://pypdf.readthedocs.io/) | [discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv) |
|:---:|:---:|:---:|
| Web scraping | PDF processing | Voice receiving |

---

## 📧 Support & Community

- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/Garry-Marshall/Synapse/issues)
- 💬 **Questions:** [GitHub Discussions](https://github.com/Garry-Marshall/Synapse/discussions)

---

<div align="center">

⭐ **Star this repo if you find it useful!** ⭐

Made with ❤️ by the community

[↑ Back to Top](#-discord-ai-bot-with-lmstudio-integration)

</div>
