#!/bin/bash

# Stop any existing MongoDB and Python processes
echo "Stopping any existing processes..."
pkill -f mongod
pkill -f "python user_bot"
sleep 2

# Clean session files if needed
echo "Ensuring clean environment..."
mkdir -p sessions

# Start MongoDB
echo "Starting MongoDB..."
mongod --dbpath ./fresh_db --port 27017 &
sleep 3

# Start the bot
echo "Starting Telegram bot..."
source venv/bin/activate
python user_bot.py 