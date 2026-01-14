<div align="center"> 
<h1>🤖 Discord AI Bot with LMStudio Integration</h1>
<h2>A powerful, modular Discord bot with local AI integration via LMStudio, featuring web search, file processing, text-to-speech, and comprehensive server configuration.</h2>
This my personal Discord bot, but feel free to play with it as you see fit.
<h3><a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#-features">Features</a> • <a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#-quick-start">Quick Start</a> • <a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#-slash-commands">Commands</a> • <a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#%EF%B8%8F-configuration">Configuration</a> • <a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#-troubleshooting">Troubleshooting</a></h3>
</div> 
<hr>
<h4>✨ Features</h4>
<br>
<b>🧠 AI Capabilities</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Local LLM Integration via LMStudio API<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Model Selection - Switch between loaded models per server<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Context-Aware Conversations - Maintains conversation history<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Reasoning Model Support - Handles &ltthink&gt tags automatically<br>
<b>🔍 Enhanced Input Processing</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Web Search - Automatic web search when needed<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ URL Content Fetching - Extracts text from provided URLs<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Image Processing - Vision model support for images<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ PDF Processing - Extracts and reads PDF content<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Text File Support - Reads code files, documents, etc.<br>
<b>🎙️ Voice & TTS</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Voice Channel Integration - Bot joins and speaks in voice channels<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Multiple Voices - 6 OpenAI-compatible voices (AllTalk TTS)<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Auto-Disconnect - Leaves when alone in voice channel<br>
<b>⚙️ Server Configuration</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Custom System Prompts - Per-server AI personality<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Temperature Control - Adjust response creativity<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Token Limits - Control response length<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Debug Logging - Per-server debug modes<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Web Search Toggle - Enable/disable per server<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ TTS Toggle - Enable/disable TTS per server<br>
<b>📊 Statistics & Management</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Conversation Stats - Track tokens, response times, messages, tool usage<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ History Management - Clear, reset, or view conversation history<br>
&nbsp;&nbsp;&nbsp;&nbsp;•	✅ Persistent Storage - Stats and settings saved across restarts<br>
<br><hr><br>
<pre>
📁 Project Structure<br>
discord_bot/<br>
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
├── 📁 services/              # Business logic
│   ├── lmstudio.py           # LMStudio API integration
│   ├── tts.py                # Text-to-speech
│   ├── search.py             # Web search
│   ├── content_fetch.py      # URL content fetching
│   ├── file_processor.py     # File processing
│   └── __init__.py
│
├── 📁 commands/              # Slash commands
│   ├── conversation.py       # /reset, /history
│   ├── stats.py              # /stats commands
│   ├── voice.py              # /join, /leave, /voice
│   ├── model.py              # /model selection
│   ├── config_cmd.py         # /config command
│   ├── help.py               # /help command
│   └── __init__.py
│
└── 📁 core/                  # Bot core
    ├── bot_instance.py       # Bot setup
    ├── events.py             # Event handlers
    └── __init__.py
</pre>
<hr>
<pre>
<h4>🚀 Quick Start</h4>
<b>Prerequisites</b>
    
<b>Requirement        Version            Link</b>
Python             3.9+               <a href="https://www.python.org/downloads/">Download</a>
Discord Bot        Token Required     <a href="https://discord.com/developers/applications">Create Bot</a>
LMStudio           Latest             <a href="https://lmstudio.ai/">Download</a>
AllTalk TTS        Optional           <a href="https://github.com/erew123/alltalk_tts/tree/alltalkbeta">Download</a>
</pre>
    
<b>Installation</b><br>
<details> <summary><b>📥 Step 1: Clone Repository</b></summary> <br>
# Clone or download the repository<br>
<pre>
    git clone https://github.com/Garry-Marshall/Jarvis
    cd Jarvis
</pre>
<br>
# Create virtual environment (recommended)<br>
<pre>
    python -m venv venv
</pre>
<br>
# Activate virtual environment<br>
# On Linux/Mac:<br>
<pre>
    source venv/bin/activate
</pre>
<br>
# On Windows:<br>
<pre>
    venv\Scripts\activate
</pre>
</details>

<details> <summary><b>📦 Step 2: Install Dependencies</b></summary> <br>
<pre>
    pip install -r requirements.txt
</pre>
</details>

<details> <summary><b>⚙️ Step 3: Configure Bot</b></summary> <br>
Create a .env file in the project root:<br>
(This file will be created automatically on first run.)
<br>
<pre>
Edit the .env file:
Replace 'your-bot-token-here' with your Discord Bot Token.
Replace example CHANNEL_IDS with comma-separated channel IDs where bot should respond
</pre>
</details>

<details> <summary><b>🔑 Step 4: Get Channel IDs</b></summary> <br>
1.	Enable Developer Mode in Discord <br>
o	Settings → Advanced → Developer Mode ✅<br>
2.	Right-click a channel → Copy ID<br>
3.	Add to DISCORD_CHANNEL_IDS in .env <br>
o	Multiple channels: comma-separated<br>
</details>

<details> <summary><b>▶️ Step 5: Run the Bot</b></summary> <br>
<pre>
    start_bot.bat
</pre>
Expected output:<br>

`2026-01-13 10:00:00 [INFO] Bot has connected to Discord!`<br>
`2026-01-13 10:00:00 [INFO] Loaded LM Studio model(s): ['llama-2-7b']`<br>
`2026-01-13 10:00:00 [INFO] Synced 10 slash command(s)`<br>
`✅ Success! Your bot is now online.`<br>
</details> <br>
<hr>
<h4>📖 Usage</h4>
<b>💬 Basic Conversation</b><br>
<table> <tr> <td width="30%"><b>Action</b></td> <td width="70%"><b>Example</b></td> </tr> <tr> <td>Simple message</td> <td> 
User: What is the weather like today?<br>
Bot: 🤔 Thinking...<br>
Bot: [Searches web and responds with weather info]<br>
</td> </tr> <tr> <td>With image</td> <td> 
User: [uploads sunset.jpg] What's in this image?<br>
Bot: I can see a beautiful sunset over the ocean with <br>
     vibrant orange and pink colors reflecting on the water...<br>
</td> </tr> <tr> <td>With PDF/Files</td> <td> 
User: [uploads report.pdf] Summarize this document<br>
Bot: This document discusses quarterly sales performance,<br>
     highlighting a 23% increase in revenue...<br>
</td> </tr> </table> 

<h4>🎮 Slash Commands</h4>
<b>🗨️ Conversation Management</b><br>
<br>
<pre>
<b>Command           Description</b>

<b>/history</b>          Show conversation length in memory
<b>/stats</b>            Display detailed statistics
</pre>

<h4>⚙️ Configuration</h4>
Note: Commands that change settings require Administrator permissions 🔒 <br>
<br>
<pre>
The /config command will open up a dialog box where per guild settings can be adjusted.

    Edit System Prompt            Set a custom system prompt that gets injected in every interaction with the LLM
                                  This will greatly affect how to bot behaves.
                                     Example: You are a python coding assistant.
                                     Example: You always talk like a pirate.

    Adjust Temperature            Value between 0.0 and 2.0. Affects how strict the LLM will follow the prompt.
                                  See below for more details.

    Set Max Tokens                Set a limit on the maximum tokens that can be sent back and forth.

    Debug: ON|OFF                 Toggle between Debug On or Off. Debug info appears on the console and in the log files.

    Set Debug Level               Choose between INFO and DEBUG. Sets the verbosity of the logs.

    Web Search ON|OFF             Toggles the ability to search the web On or Off.

    TTS ON|OFF                    Toggles the Text-to-Speech for Voice channels On or Off.

    Clear Last Message            Removes the last interaction from the history.

    Clear All History             Removes all history.

    Reset to Defaults             Resets all Config settings to their default values.
</pre>
<br>
<h4>🧠 Model & Voice</h4>
<b>Command	Description</b><br>
<pre>
/model        Select AI model from dropdown menu
/voice        Choose TTS voice (alloy, echo, fable, nova, onyx, shimmer)
/join         Join your current voice channel
/leave        Leave voice channel
</pre>
<br>
<h4>❓ Help</h4>
<b>Command	Description</b>b><br>
<pre>
/help         Show all commands and usage instructions
</pre>
<hr>
<h4>🔧 Advanced Configuration</h4>
  
<summary><b>🌡️ Temperature Settings</b></summary> <br>
<pre>
Control response creativity and randomness:
    
<b>Temperature        Behavior                        Best For</b>
0.0 - 0.3          Focused, deterministic          Code, facts, technical content
0.4 - 0.7          Balanced (default: 0.7)         General conversation
0.8 - 1.2          Creative, varied                Brainstorming, creative writing
1.3 - 2.0          Highly creative, unpredictable  Experimental, artistic content

</pre>
<hr>

<h4>🐛 Troubleshooting</h4>
<details> <summary><b>Bot doesn't respond to messages</b></summary> 
<pre>
<b>Possible causes:</b>
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
</pre>
</details>

<details> <summary><b>"No models found in LMStudio"</b></summary>
<pre>
<b>Solution:</b>
1.	Open LMStudio application
2.	Navigate to "Models" tab
3.	Click "Load Model" for your desired model
4.	Wait for model to fully load (status bar shows 100%)
5.  Start the server under Developer
6.	Restart the Discord bot
Verify:
-> You should see in logs:
[INFO] Loaded LM Studio model(s): ['your-model-name']
</pre>
</details>

<details> <summary><b>Import errors / Module not found</b></summary>
<pre>
<b>Cause: Running from wrong directory or missing __init__.py files</b>
<b>Solution:</b>
-> Always run from project root
        cd Jarvis
        python bot.py

-> Ensure all __init__.py files exist:
touch config/__init__.py
touch utils/__init__.py
touch services/__init__.py
touch commands/__init__.py
touch core/__init__.py
</pre>
</details>

<details> <summary><b>Slash commands not appearing</b></summary>
<pre>
<b>Solution:</b>
1.	Refresh Discord – Press CTRL-R in Discord.
2.	Wait 1 hour - Discord caches slash commands globally
3.	Check logs for sync errors: 
4.	[INFO] Synced 10 slash command(s)
5.	Test in DM - Slash commands appear faster in DMs
</pre>
</details>

<details> <summary><b>Permission errors</b></summary> 
<pre>
<b>Required bot permissions:</b>

<b>Permission        	     Why Needed</b>
View Channels            See messages
Send Messages            Respond to users
Embed Links              Rich formatting
Attach Files             Send images/files
Read Message History	 Load context
Use Slash Commands	     Execute commands
Connect	                 Join voice
Speak	                 TTS playback

<b>Bot invite URL template:</b>
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2150747136&scope=bot%20applications.commands
</pre>
</details>

<details> <summary><b>Voice/TTS not working</b></summary>
<pre>
Checklist:
    •	[ ] ENABLE_TTS=true in .env
    •	[ ] AllTalk TTS running at ALLTALK_URL
    •	[ ] Enable TTS in Guild via /config
    •	[ ] Bot is in voice channel (/join)
    •	[ ] Bot has Connect and Speak permissions
    •	[ ] FFmpeg installed (required for audio playback)

Install FFmpeg:

<b>-> Ubuntu/Debian</b>
    sudo apt-get install ffmpeg

<b>-> macOS</b>
    brew install ffmpeg

<b>-> Windows</b>
    Download from: https://ffmpeg.org/download.html
</pre>
</details>

<hr>
<h4>📊 Statistics Files</h4>
<pre>
The bot automatically creates and maintains these files:

<b>File                        Purpose                                                Can Delete?</b>
channel_stats.json          Conversation statistics (tokens, times, messages)      ✅ Yes - Will recreate with defaults
guild_settings.json         Server configurations (prompts, temperature, etc.)     ⚠️ Caution - Settings will be lost
Logs/bot_*.log              Daily log files                                        ✅ Yes - Old logs can be deleted

Example stats structure:
  "123456789": {
    "total_messages": 42,
    "prompt_tokens_estimate": 15230,
    "response_tokens_cleaned": 8450,
    "average_response_time": 2.3
  }
</pre>
<hr>
<h4>🔒 Security Best Practices</h4>
<pre>
⚠️ IMPORTANT: Follow these security guidelines
    
<b>Environment Variables</b>
    •	✅ DO: Keep .env file in .gitignore
    •	✅ DO: Use separate tokens for dev/production
    •	❌ DON'T: Commit .env to version control
    •	❌ DON'T: Share your bot token publicly

<b>Token Exposed?</b>
If your bot token is accidentally exposed:
    1.	Immediately regenerate in Discord Developer Portal
    2.	Update .env with new token
    3.	Restart bot
    4.	Review bot's recent activity
    
<b>Permissions</b>
    •	Principle of least privilege: Only grant permissions the bot actually needs
    •	Review regularly: Audit bot permissions in all servers
    •	Test in dev server first: Before adding new features

<b>Rate Limiting</b>
The bot includes built-in rate limiting for:
    •	Web searches (10s cooldown per server)
    •	API requests (handled by discord.py)
</pre>
<hr>
<h4>🤝 Contributing</h4>
We welcome contributions! Here's how to help:<br>
<br>    
Reporting Issues<br>
<details> <summary><b>🐛 Bug Reports</b></summary>
<pre>
Please include:
    •	Bot version or commit hash
    •	Python version: python --version
    •	OS: Windows/Mac/Linux
    •	Error logs from Logs/ directory
    •	Steps to reproduce
</pre>pre>
</details>
<details> <summary><b>💡 Feature Requests</b></summary>
<pre>
Describe:
    •	Use case: What problem does this solve?
    •	Proposed solution: How should it work?
    •	Alternatives considered: Other approaches?
</pre>
</details> <br>
<pre>
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
</pre>
<hr>
<h4>📝 License</h4>
This project is licensed under the MIT License - see the LICENSE file for details.<br>
TL;DR: You can use, modify, and distribute this code freely, just keep the copyright notice.<br>
<hr>
<h4>🙏 Acknowledgments</h4>
This project is built on these amazing open-source projects:<br>
<table> <tr> <td align="center" width="20%"> <a href="https://github.com/Rapptz/discord.py"><img src="https://github.com/github/explore/blob/main/topics/discord/discord.png?raw=true" width="60px" alt="discord.py"/><br/> <b>discord.py</b> </a><br/> Discord API wrapper </td> <td align="center" width="20%"> <a href="https://lmstudio.ai/"><img src="https://lmstudio.ai/_next/static/media/Building_Standing_BlueHammer.2da8c7d6.png" width="60px" alt="lmstudio"/><br/><b>🖥️ LMStudio</b> </a><br/> Local LLM runtime </td> <td align="center" width="20%"> <a href="https://github.com/deedy5/ddgs"> <b>🦆 Dux Distributed Global Search</b> </a><br/> Privacy-first search </td> <td align="center" width="20%"> <a href="https://github.com/adbar/trafilatura"><img src="https://raw.githubusercontent.com/adbar/trafilatura/master/docs/trafilatura-logo.png" width="100px" alt="trafilatura"/><br> <b>📄 Trafilatura</b> </a><br/> Web scraping </td><td align="center" width="20%"> <a href="https://pypdf.readthedocs.io/en/stable/"><img src="https://pypdf.readthedocs.io/en/stable/_static/logo.png" width="100px" alt="pypdf"/><br> <b>PyPDF</b> </a><br/> Back to the Roots </td> </tr> </table> 
Special thanks to:<br>
•	AllTalk TTS for OpenAI-compatible text-to-speech<br>
•	The Discord.py community for excellent documentation<br>
•	All contributors and users of this project<br>
<hr>
<h4>📧 Support & Community</h4>
<div align="center"> 
   
</div> 
•	🐛 Bug Reports: <a href="https://github.com/Garry-Marshall/Jarvis/issues">Github Issues</a><br>
•	💬 Questions: <a href="https://github.com/Garry-Marshall/Jarvis/discussions">Github Discussions</a><br>
•	📖 Wiki: Documentation (WIP)<br>
<hr>
<div align="center"> 
⭐ Star this repo if you find it useful! ⭐<br>
Made with ❤️ by the community<br>
⬆ <a href="https://github.com/Garry-Marshall/Jarvis?tab=readme-ov-file#-discord-ai-bot-with-lmstudio-integration">Back to Top</a><br>
</div>
