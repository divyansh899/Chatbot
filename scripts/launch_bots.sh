#!/bin/bash

# Set the working directory to the bot directory
cd /Users/divyanshchugh/Desktop/chat\ bot/

# Kill any existing bot processes
pkill -f user_bot.py
pkill -f backup_bot.py

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the bots with nohup to keep them running after terminal closes
# Using caffeinate to prevent sleep from stopping the process
nohup caffeinate -i python3 user_bot.py > logs/user_bot.log 2>&1 &
echo "User bot started with PID: $!"

# Wait a bit before starting the backup bot
sleep 5

nohup caffeinate -i python3 backup_bot.py > logs/backup_bot.log 2>&1 &
echo "Backup bot started with PID: $!"

# Save PIDs to a file for easy management
echo "$!" > logs/backup_bot.pid
ps aux | grep "python3 user_bot.py" | grep -v grep | awk '{print $2}' > logs/user_bot.pid

echo "Bots are now running in the background"
echo "To check status: ps aux | grep 'bot.py'"
echo "Log files are stored in the logs directory" 