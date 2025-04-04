#!/bin/bash

# Set the working directory to the bot directory
cd /Users/divyanshchugh/Desktop/chat\ bot/

echo "Checking status of Telegram bots..."
echo "-----------------------------------"

# Check user bot status
if [ -f logs/user_bot.pid ]; then
    pid=$(cat logs/user_bot.pid)
    if ps -p $pid > /dev/null; then
        uptime=$(ps -p $pid -o etime= | tr -d ' ')
        echo "✅ User bot is running (PID: $pid, Uptime: $uptime)"
    else
        echo "❌ User bot is NOT running (Stale PID file: $pid)"
    fi
else
    # Try to find the process
    pid=$(ps aux | grep "python3 user_bot.py" | grep -v grep | awk '{print $2}')
    if [ -n "$pid" ]; then
        uptime=$(ps -p $pid -o etime= | tr -d ' ')
        echo "✅ User bot is running (PID: $pid, Uptime: $uptime) but PID file is missing"
    else
        echo "❌ User bot is NOT running"
    fi
fi

# Check backup bot status
if [ -f logs/backup_bot.pid ]; then
    pid=$(cat logs/backup_bot.pid)
    if ps -p $pid > /dev/null; then
        uptime=$(ps -p $pid -o etime= | tr -d ' ')
        echo "✅ Backup bot is running (PID: $pid, Uptime: $uptime)"
    else
        echo "❌ Backup bot is NOT running (Stale PID file: $pid)"
    fi
else
    # Try to find the process
    pid=$(ps aux | grep "python3 backup_bot.py" | grep -v grep | awk '{print $2}')
    if [ -n "$pid" ]; then
        uptime=$(ps -p $pid -o etime= | tr -d ' ')
        echo "✅ Backup bot is running (PID: $pid, Uptime: $uptime) but PID file is missing"
    else
        echo "❌ Backup bot is NOT running"
    fi
fi

echo "-----------------------------------"
echo "Last 5 lines of user_bot.log:"
tail -5 logs/user_bot.log 2>/dev/null || echo "No log file found"

echo "-----------------------------------"
echo "Last 5 lines of backup_bot.log:"
tail -5 logs/backup_bot.log 2>/dev/null || echo "No log file found" 