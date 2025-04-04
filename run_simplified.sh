#!/bin/bash

# Kill any existing bot processes
pkill -f user_bot.py || true
sleep 2

# Clear logs
> bot.log
> bot_error.log

# Run the bot with python3 (full path)
echo "Starting the bot..."
nohup /opt/homebrew/bin/python3 user_bot.py > bot.log 2> bot_error.log &

echo "Bot started with PID: $!"
echo "Check logs with: tail -f bot.log" 