#!/bin/bash

# Stop any existing processes
echo "Stopping any existing bot processes..."
pkill -f user_bot.py || true

# Wait a moment to make sure previous processes are terminated
sleep 2

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Make sure the virtual environment is activated
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Clear previous logs
> bot.log
> bot_error.log

# Start the bot with caffeinate to prevent sleep
echo "Starting Telegram OTP bot..."
nohup caffeinate -s python user_bot.py > bot.log 2> bot_error.log &

# Get the process ID
BOT_PID=$!

# Display a message
echo "Telegram OTP bot started with PID: $BOT_PID"
echo "The bot will continue running even when your Mac sleeps or is closed"
echo "You can check if it's running with: ps aux | grep user_bot.py"
echo "Logs are saved to: bot.log and bot_error.log" 