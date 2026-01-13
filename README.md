<div align="center"> 
<h1></h1>🤖 Discord AI Bot with LMStudio Integration</div></h1><br>
<br>
A powerful, modular Discord bot with local AI integration via LMStudio, featuring web search, file processing, text-to-speech, and comprehensive server configuration.<br>
Features • Quick Start • Commands • Configuration • Development<br>
</div> 
<hr>
✨ Features<br>
<table> <tr> <td width="50%"> 
🧠 AI Capabilities<br>
•	✅ Local LLM Integration via LMStudio API<br>
•	✅ Model Selection - Switch between loaded models per server<br>
•	✅ Context-Aware Conversations - Maintains conversation history<br>
•	✅ Reasoning Model Support - Handles <think> tags automatically<br>
🔍 Enhanced Input Processing<br>
•	✅ Web Search - Automatic DuckDuckGo search when needed<br>
•	✅ URL Content Fetching - Extracts text from provided URLs<br>
•	✅ Image Processing - Vision model support for images<br>
•	✅ PDF Processing - Extracts and reads PDF content<br>
•	✅ Text File Support - Reads code files, documents, etc.<br>
</td> <td width="50%"> 
🎙️ Voice & TTS<br>
•	✅ Voice Channel Integration - Bot joins and speaks in voice channels<br>
•	✅ Multiple Voices - 6 OpenAI-compatible voices (AllTalk TTS)<br>
•	✅ Auto-Disconnect - Leaves when alone in voice channel<br>
⚙️ Server Configuration<br>
•	✅ Custom System Prompts - Per-server AI personality<br>
•	✅ Temperature Control - Adjust response creativity<br>
•	✅ Token Limits - Control response length<br>
•	✅ Debug Logging - Per-server debug modes<br>
•	✅ Web Search Toggle - Enable/disable per server<br>
📊 Statistics & Management<br>
•	✅ Conversation Stats - Track tokens, response times, messages<br>
•	✅ History Management - Clear, reset, or view conversation history<br>
•	✅ Persistent Storage - Stats and settings saved across restarts<br>
</td> </tr> </table> 
<hr>
📁 Project Structure
discord_bot/
│
├── 📄 bot.py                  # Main entry point
├── 📄 requirements.txt        # Python dependencies
├── 📄 .env                    # Configuration
│
├── 📁 config/                 # Settings and constants
│   ├── settings.py
│   ├── constants.py
│   └── __init__.py
│
├── 📁 utils/                  # Helper functions
│   ├── logging_config.py
│   ├── text_utils.py
│   ├── stats_manager.py
│   ├── guild_settings.py
│   └── __init__.py
│
├── 📁 services/               # Business logic
│   ├── lmstudio.py           # LMStudio API integration
│   ├── tts.py                # Text-to-speech
│   ├── search.py             # Web search
│   ├── content_fetch.py      # URL content fetching
│   ├── file_processor.py     # File processing
│   └── __init__.py
│
├── 📁 commands/               # Slash commands
│   ├── conversation.py       # /reset, /history
│   ├── stats.py              # /stats commands
│   ├── voice.py              # /join, /leave, /voice
│   ├── model.py              # /model selection
│   ├── config_cmd.py         # /config command
│   ├── help.py               # /help command
│   └── __init__.py
│
└── 📁 core/                   # Bot core
    ├── bot_instance.py       # Bot setup
    ├── events.py             # Event handlers
    └── __init__.py

________________________________________
🚀 Quick Start
Prerequisites
Requirement	Version	Link
Python	3.8+	Download

Discord Bot	Token Required	Create Bot

LMStudio	Latest	Download

AllTalk TTS	Optional	Download

Installation
<details> <summary><b>📥 Step 1: Clone Repository</b></summary> 
# Clone or download the repository
git clone https://github.com/Garry-Marshall/Jarvis
cd Jarvis

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
</details> <details> <summary><b>📦 Step 2: Install Dependencies</b></summary> 
pip install -r requirements.txt
</details> <details> <summary><b>⚙️ Step 3: Configure Bot</b></summary> 
Create a .env file in the project root:
# REQUIRED: Your Discord bot token
DISCORD_BOT_TOKEN=your-bot-token-here

# REQUIRED: Comma-separated channel IDs where bot should respond
DISCORD_CHANNEL_IDS=123456789012345678,987654321098765432

# LMStudio API (default: localhost)
LMSTUDIO_URL=http://localhost:1234/v1/chat/completions

# Conversation settings
MAX_HISTORY_MESSAGES=10
CONTEXT_MESSAGES=5

# Bot behavior
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

# Voice/TTS settings
ENABLE_TTS=true
ALLTALK_URL=http://127.0.0.1:7851
ALLTALK_VOICE=alloy
</details> <details> <summary><b>🔑 Step 4: Get Channel IDs</b></summary> 
1.	Enable Developer Mode in Discord 
o	Settings → Advanced → Developer Mode ✅
2.	Right-click a channel → Copy ID
3.	Add to DISCORD_CHANNEL_IDS in .env 
o	Multiple channels: comma-separated
</details> <details> <summary><b>▶️ Step 5: Run the Bot</b></summary> 
python bot.py
Expected output:
2024-01-13 10:00:00 [INFO] Bot has connected to Discord!
2024-01-13 10:00:00 [INFO] Loaded LM Studio model(s): ['llama-2-7b']
2024-01-13 10:00:00 [INFO] Synced 10 slash command(s)
✅ Success! Your bot is now online.
</details> 
________________________________________
📖 Usage
💬 Basic Conversation
<table> <tr> <td width="30%"><b>Action</b></td> <td width="70%"><b>Example</b></td> </tr> <tr> <td>Simple message</td> <td> 
User: What is the weather like today?
Bot: 🤔 Thinking...
Bot: [Searches web and responds with weather info]
</td> </tr> <tr> <td>With image</td> <td> 
User: [uploads sunset.jpg] What's in this image?
Bot: I can see a beautiful sunset over the ocean with 
     vibrant orange and pink colors reflecting on the water...
</td> </tr> <tr> <td>With PDF/Files</td> <td> 
User: [uploads report.pdf] Summarize this document
Bot: This document discusses quarterly sales performance,
     highlighting a 23% increase in revenue...
</td> </tr> </table> 
🎮 Slash Commands
🗨️ Conversation Management
Command	Description	Usage
/reset	Clear conversation history	/reset
/history	Show conversation length	/history
/stats	Display detailed statistics	/stats
/stats_reset	Reset statistics	/stats_reset
⚙️ Configuration
Note: Commands marked with 🔒 require Administrator permissions
Command	Description	Example
/config show show	View all settings	/config show show
/config system set 🔒	Set custom system prompt	/config system set You are a helpful coding assistant
/config system show	View current system prompt	/config system show
/config system clear 🔒	Reset to default prompt	/config system clear
/config temperature set 🔒	Adjust creativity (0.0-2.0)	/config temperature set 0.8
/config temperature show	View current temperature	/config temperature show
/config max_tokens set 🔒	Limit response length	/config max_tokens set 2000
/config max_tokens show	View current limit	/config max_tokens show
/config debug on/off 🔒	Toggle debug logging	/config debug on
/config search on/off 🔒	Toggle web search	/config search off
/config clear last	Remove last interaction	/config clear last
🧠 Model & Voice
Command	Description
/model	Select AI model from dropdown menu
/voice	Choose TTS voice (alloy, echo, fable, nova, onyx, shimmer)
/join	Join your current voice channel
/leave	Leave voice channel
❓ Help
Command	Description
/help	Show all commands and usage instructions
________________________________________
🔧 Advanced Configuration
<details> <summary><b>🧠 Custom System Prompts</b></summary> 
Set a unique personality per server:
/config system set You are a helpful coding assistant specializing in Python and JavaScript. Always provide code examples and explain your reasoning.
Examples:
•	Customer Support: You are a friendly customer support agent. Be empathetic and solution-focused.
•	Tutor: You are an experienced teacher. Explain concepts clearly with examples and analogies.
•	Creative Writer: You are a creative writing assistant. Help with storytelling, character development, and plot ideas.
</details> <details> <summary><b>🌡️ Temperature Settings</b></summary> 
Control response creativity and randomness:
Temperature	Behavior	Best For
0.0 - 0.3	Focused, deterministic	Code, facts, technical content
0.4 - 0.7	Balanced (default: 0.7)	General conversation
0.8 - 1.2	Creative, varied	Brainstorming, creative writing
1.3 - 2.0	Highly creative, unpredictable	Experimental, artistic content
/config temperature set 0.8
</details> <details> <summary><b>📝 Token Limits</b></summary> 
Control maximum response length:
# Limit to 2000 tokens
/config max_tokens set 2000

# Unlimited tokens
/config max_tokens set -1

# View current setting
/config max_tokens show
Note: Actual output length may be shorter depending on model and prompt.
</details> <details> <summary><b>🐞 Debug Logging</b></summary> 
Enable detailed logging for troubleshooting:
# Enable debug mode
/config debug on

# Set log level
/config debug level debug  # Verbose
/config debug level info   # Standard

# View current settings
/config debug show
Logs are saved to: Logs/bot_YYYY-MM-DD.log
Debug info includes:
•	Full API messages (with thinking tags)
•	Token counts and timing
•	Search context details
•	Error stack traces
</details> <details> <summary><b>🔍 Web Search Control</b></summary> 
Toggle automatic web search per server:
# Disable web search
/config search off

# Enable web search
/config search on

# Check status
/config search show
Search Triggers: The bot automatically searches when messages contain phrases like:
•	"search for..."
•	"what's the latest..."
•	"current news about..."
•	"weather in..."
</details> 
________________________________________
🛠️ Development
Project Architecture
graph TD
    A[bot.py - Entry Point] --> B[core/events.py]
    B --> C[commands/]
    B --> D[services/]
    D --> E[LMStudio API]
    D --> F[Web Search]
    D --> G[TTS Service]
    C --> H[utils/]
    D --> H
    H --> I[Stats Manager]
    H --> J[Guild Settings]
<details> <summary><b>📦 Package Details</b></summary> 
Package	Purpose	Key Files
config/	Configuration management	settings.py, constants.py
utils/	Helper functions	text_utils.py, stats_manager.py, guild_settings.py
services/	Business logic	lmstudio.py, tts.py, search.py, file_processor.py
commands/	Slash commands	All command handlers
core/	Bot core	bot_instance.py, events.py
</details> 

🐛 Troubleshooting
<details> <summary><b>Bot doesn't respond to messages</b></summary> 
Possible causes:
1.	Wrong channel IDs
2.	# Check your .env file
3.	DISCORD_CHANNEL_IDS=123456789012345678
4.	
5.	# Verify in logs:
6.	# Should see: "Listening in X channel(s)"
7.	Missing permissions
o	Bot needs: Read Messages, Send Messages, Embed Links, Attach Files
o	Check in Server Settings → Roles → Your Bot Role
8.	Bot not in channel
o	Ensure bot was invited with correct permissions
o	Re-invite with this URL (replace CLIENT_ID):
9.	https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=412317273088&scope=bot%20applications.commands
</details> <details> <summary><b>"No models found in LMStudio"</b></summary> 
Solution:
1.	Open LMStudio application
2.	Navigate to "Models" tab
3.	Click "Load Model" for your desired model
4.	Wait for model to fully load (status bar shows 100%)
5.	Restart the Discord bot
Verify:
# You should see in logs:
[INFO] Loaded LM Studio model(s): ['your-model-name']
</details> <details> <summary><b>Import errors / Module not found</b></summary> 
Cause: Running from wrong directory or missing __init__.py files
Solution:
# Always run from project root
cd Jarvis
python bot.py

# NOT from subdirectories:
# ❌ cd Jarvis/core && python ../bot.py

# Ensure all __init__.py files exist:
touch config/__init__.py
touch utils/__init__.py
touch services/__init__.py
touch commands/__init__.py
touch core/__init__.py
</details> <details> <summary><b>Slash commands not appearing</b></summary> 
Solution:
1.	Wait 1 hour - Discord caches slash commands globally
2.	Refresh Discord – Press CTRL-D in Discord.
3.	Check logs for sync errors: 
4.	[INFO] Synced 10 slash command(s)
5.	Test in DM - Slash commands appear faster in DMs
</details> <details> <summary><b>Permission errors</b></summary> 
Required bot permissions:
Permission	Why Needed
View Channels	See messages
Send Messages	Respond to users
Embed Links	Rich formatting
Attach Files	Send images/files
Read Message History	Load context
Use Slash Commands	Execute commands
Connect	Join voice (optional)
Speak	TTS playback (optional)
Bot invite URL template:
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=412317273088&scope=bot%20applications.commands
</details> <details> <summary><b>Voice/TTS not working</b></summary> 
Checklist:
•	[ ] ENABLE_TTS=true in .env
•	[ ] AllTalk TTS running at ALLTALK_URL
•	[ ] Bot is in voice channel (/join)
•	[ ] Bot has Connect and Speak permissions
•	[ ] FFmpeg installed (required for audio playback)
Install FFmpeg:
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html

________________________________________
📊 Statistics Files
The bot automatically creates and maintains these files:
File	Purpose	Can Delete?
channel_stats.json	Conversation statistics (tokens, times, messages)	✅ Yes - Will recreate with defaults
guild_settings.json	Server configurations (prompts, temperature, etc.)	⚠️ Caution - Settings will be lost
Logs/bot_*.log	Daily log files	✅ Yes - Old logs can be deleted
Example stats structure:
{
  "123456789": {
    "total_messages": 42,
    "prompt_tokens_estimate": 15230,
    "response_tokens_cleaned": 8450,
    "average_response_time": 2.3
  }
}
________________________________________
🔒 Security Best Practices
⚠️ IMPORTANT: Follow these security guidelines
Environment Variables
•	✅ DO: Keep .env file in .gitignore
•	✅ DO: Use separate tokens for dev/production
•	❌ DON'T: Commit .env to version control
•	❌ DON'T: Share your bot token publicly
Token Exposed?
If your bot token is accidentally exposed:
1.	Immediately regenerate in Discord Developer Portal
2.	Update .env with new token
3.	Restart bot
4.	Review bot's recent activity
Permissions
•	Principle of least privilege: Only grant permissions the bot actually needs
•	Review regularly: Audit bot permissions in all servers
•	Test in dev server first: Before adding new features
Rate Limiting
The bot includes built-in rate limiting for:
•	Web searches (10s cooldown per server)
•	API requests (handled by discord.py)
________________________________________
🤝 Contributing
We welcome contributions! Here's how to help:
Reporting Issues
<details> <summary><b>🐛 Bug Reports</b></summary> 
Please include:
•	Bot version or commit hash
•	Python version: python --version
•	OS: Windows/Mac/Linux
•	Error logs from Logs/ directory
•	Steps to reproduce
</details> <details> <summary><b>💡 Feature Requests</b></summary> 
Describe:
•	Use case: What problem does this solve?
•	Proposed solution: How should it work?
•	Alternatives considered: Other approaches?
</details> 
Development Workflow
1.	Fork the repository
2.	Create a branch: git checkout -b feature/amazing-feature
3.	Make changes with clear, focused commits
4.	Test thoroughly in a dev server
5.	Update docs if needed (README, docstrings)
6.	Submit PR with description of changes
Code Guidelines
•	Follow existing code style
•	Add docstrings to new functions
•	Update README.md for user-facing changes
•	Keep commits atomic and well-described
________________________________________
📝 License
This project is licensed under the MIT License - see the LICENSE file for details.
TL;DR: You can use, modify, and distribute this code freely, just keep the copyright notice.
________________________________________
🙏 Acknowledgments
This project is built on these amazing open-source projects:
<table> <tr> <td align="center" width="25%"> <a href="https://github.com/Rapptz/discord.py"> <img src="https://raw.githubusercontent.com/Rapptz/discord.py/master/docs/_static/discord_py_logo.png" width="60px" alt="discord.py"/><br/> <b>discord.py</b> </a><br/> Discord API wrapper </td> <td align="center" width="25%"> <a href="https://lmstudio.ai/"> <b>🖥️ LMStudio</b> </a><br/> Local LLM runtime </td> <td align="center" width="25%"> <a href="https://github.com/deedy5/ddgs"> <b>🦆 DuckDuckGo</b> </a><br/> Privacy-first search </td> <td align="center" width="25%"> <a href="https://github.com/adbar/trafilatura"> <b>📄 Trafilatura</b> </a><br/> Web scraping </td> </tr> </table> 
Special thanks to:
•	AllTalk TTS for OpenAI-compatible text-to-speech
•	The Discord.py community for excellent documentation
•	All contributors and users of this project
________________________________________
📧 Support & Community
<div align="center"> 
   
</div> 
•	🐛 Bug Reports: GitHub Issues
•	💬 Questions: GitHub Discussions
•	📖 Wiki: Documentation
________________________________________
<div align="center"> 
⭐ Star this repo if you find it useful! ⭐
Made with ❤️ by the community
⬆ Back to Top
</div>

