#!/bin/bash

# Set the working directory to the bot directory
cd /Users/divyanshchugh/Desktop/chat\ bot/

echo "Stopping telegram bots..."

# Kill processes by PID files if they exist
if [ -f logs/user_bot.pid ]; then
    pid=$(cat logs/user_bot.pid)
    if ps -p $pid > /dev/null; then
        echo "Stopping user bot (PID: $pid)"
        kill $pid
    else
        echo "User bot process not found with PID: $pid"
    fi
fi

if [ -f logs/backup_bot.pid ]; then
    pid=$(cat logs/backup_bot.pid)
    if ps -p $pid > /dev/null; then
        echo "Stopping backup bot (PID: $pid)"
        kill $pid
    else
        echo "Backup bot process not found with PID: $pid"
    fi
fi

# Additionally, try to find and kill any remaining bot processes
pkill -f user_bot.py
pkill -f backup_bot.py

echo "All bots have been stopped" 