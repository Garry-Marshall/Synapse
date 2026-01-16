# 🤖 Discord AI Bot with LMStudio Integration

A powerful, modular Discord bot with local AI integration via LMStudio, featuring web search, file processing, text-to-speech, and comprehensive per-server configuration with SQLite persistence.

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
- ✅ **Auto-Disconnect** - Leaves when alone in voice channel
- ✅ **Per-Server TTS Toggle** - Enable/disable TTS per guild

### ⚙️ Server Configuration
- ✅ **Channel Monitoring** - Select specific channels for bot responses
- ✅ **Custom System Prompts** - Per-server AI personality
- ✅ **Temperature Control** - Adjust response creativity (0.0-2.0)
- ✅ **Token Limits** - Control response length
- ✅ **Debug Logging** - Per-server debug modes with level control
- ✅ **Web Search Toggle** - Enable/disable per server
- ✅ **TTS Toggle** - Enable/disable TTS per server

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
├── 📄 jarvis_bot.db             # SQLite database (auto-created)
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
│   ├── permissions.py
│   └── __init__.py
│
├── 📂 services/                # Business logic
│   ├── lmstudio.py             # LMStudio API integration
│   ├── tts.py                  # Text-to-speech
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
└── 📂 core/                    # Bot core
    ├── bot_instance.py         # Bot setup
    ├── events.py               # Event handlers
    ├── shutdown_handler.py     # Graceful shutdown
    └── __init__.py
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

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/Garry-Marshall/Jarvis
   cd Jarvis
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
   DB_FILE=jarvis_bot.db
   
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
   
   # TTS settings
   ENABLE_TTS=true
   ALLTALK_URL=http://127.0.0.1:7851
   ALLTALK_VOICE=alloy
   ```

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

### 🎮 Slash Commands

#### 📊 Statistics & Monitoring

- `/stats` - Display detailed conversation statistics
- `/context` - Show token usage and context window analysis
- `/status` - Display bot health and system status
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

- **`jarvis_bot.db`** - Main database (auto-created)
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
  cd Jarvis
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

| [DDGS](https://github.com/deedy5/ddgs) | [Trafilatura](https://github.com/adbar/trafilatura) | [PyPDF](https://pypdf.readthedocs.io/) |
|:---:|:---:|:---:|
| Privacy-first search | Web scraping | PDF processing |

---

## 📧 Support & Community

- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/Garry-Marshall/Jarvis/issues)
- 💬 **Questions:** [GitHub Discussions](https://github.com/Garry-Marshall/Jarvis/discussions)

---

<div align="center">

⭐ **Star this repo if you find it useful!** ⭐

Made with ❤️ by the community

[↑ Back to Top](#-discord-ai-bot-with-lmstudio-integration)

</div>
