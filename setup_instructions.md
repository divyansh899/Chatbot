# Telegram OTP Bot Setup Instructions

This document explains how to set up and run the Telegram OTP Bot on your system.

## Prerequisites

- Python 3.8 or higher
- MongoDB (local installation or remote connection)
- Telegram API credentials (API ID and API Hash)
- A Telegram Bot Token (obtained from BotFather)

## Installation Steps

1. **Create a Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure MongoDB**

   Ensure MongoDB is running on your system. The default connection is `mongodb://localhost:27017/`.

4. **Environment Variables**

   Create a `.env` file with your credentials (if not already present):

   ```
   API_ID=your_telegram_api_id
   API_HASH=your_telegram_api_hash
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_ID=your_telegram_user_id
   ADMIN_USERNAME=@your_telegram_username
   ```

   Update the values in the file with your own credentials.

5. **Create Sessions Directory**

   ```bash
   mkdir -p sessions
   ```

## Running the Bot

1. **Start the Bot**

   ```bash
   python user_bot.py
   ```

2. **Keep Bot Running in Background (Mac/Linux)**

   Use `tmux` to keep the bot running even when you close your terminal:

   ```bash
   # Install tmux if not already installed
   # On macOS: brew install tmux
   # On Ubuntu: apt-get install tmux

   # Start a new tmux session
   tmux new -s telegram_bot

   # Inside the tmux session, run:
   source venv/bin/activate && python user_bot.py

   # Detach from the session (press Ctrl+B, then D)
   ```

   To reattach to the session later:
   ```bash
   tmux attach -t telegram_bot
   ```

## Bot Commands and Features

### Admin Commands

- `/admin` - Access admin panel
- `/listnumbers` - List all numbers in inventory
- `/clearinventory` - Clear all inventory data
- `/generateSession +PHONE` - Generate a session for a number
- `/addsession +PHONE SESSION` - Add a session string manually
- `/startmonitor +PHONE` - Start OTP monitoring for a number
- `/stopmonitor +PHONE` - Stop OTP monitoring for a number
- `/exportstring +PHONE` - Export a session string
- `/deletesession +PHONE` - Delete a session

### User Commands

- `/start` - Start the bot and see main menu
- `/mynumbers` - Show numbers purchased by the user
- `/help` - Show help message
- `/id` - Get user's Telegram ID

## Folder Structure

- `user_bot.py` - Main bot file with all functionality
- `sessions/` - Directory for Telethon session files
- `TELEGRAM_BOT_SETUP.md` - General setup documentation
- `TELEGRAM_OTP_SYSTEM.md` - Documentation about the OTP system
- `requirements.txt` - Python dependencies

## Troubleshooting

1. **MongoDB Connection Issues**
   
   Ensure MongoDB is running:
   ```bash
   # Check if MongoDB service is running
   ps aux | grep mongod
   ```

2. **Telegram Authorization Issues**
   
   If your bot can't connect to Telegram, verify your API credentials in the `.env` file.

3. **Session Issues**
   
   If a number's session becomes invalid, use `/generateSession +PHONENUMBER` to regenerate it.

4. **OTP Monitoring Not Working**
   
   Use `/startmonitor +PHONENUMBER` to manually start monitoring for a specific number.

## Security Considerations

- Keep your `.env` file secure and never share your API credentials
- Regularly backup your session files
- Monitor the bot logs for suspicious activities
- Use secure passwords for your MongoDB instance

## Backup and Restore

To backup your bot data:

1. Backup MongoDB data
2. Backup the `sessions/` directory
3. Backup the `.env` file and `user_bot.py`

To restore:

1. Restore MongoDB data
2. Place session files in the `sessions/` directory
3. Configure the `.env` file with your credentials
4. Run the bot as usual
