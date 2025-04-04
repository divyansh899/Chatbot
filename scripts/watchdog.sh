#!/bin/bash

# Set the working directory to the bot directory
cd /Users/divyanshchugh/Desktop/chat\ bot/

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to check if a bot is running
is_bot_running() {
    bot_name=$1
    ps aux | grep "python3 $bot_name.py" | grep -v grep | wc -l | tr -d ' '
}

# Date for logging
log_date=$(date "+%Y-%m-%d %H:%M:%S")

# Check user bot
if [ $(is_bot_running "user_bot") -eq 0 ]; then
    echo "$log_date - USER BOT not running. Restarting..." >> logs/watchdog.log
    nohup caffeinate -i python3 user_bot.py > logs/user_bot.log 2>&1 &
    echo "$!" > logs/user_bot.pid
    echo "$log_date - USER BOT restarted with PID: $!" >> logs/watchdog.log
else
    echo "$log_date - USER BOT running OK" >> logs/watchdog.log
fi

# Check backup bot
if [ $(is_bot_running "backup_bot") -eq 0 ]; then
    echo "$log_date - BACKUP BOT not running. Restarting..." >> logs/watchdog.log
    nohup caffeinate -i python3 backup_bot.py > logs/backup_bot.log 2>&1 &
    echo "$!" > logs/backup_bot.pid
    echo "$log_date - BACKUP BOT restarted with PID: $!" >> logs/watchdog.log
else
    echo "$log_date - BACKUP BOT running OK" >> logs/watchdog.log
fi 