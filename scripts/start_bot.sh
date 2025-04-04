#!/bin/bash

# Check if MongoDB is running
if pgrep -x "mongod" > /dev/null
then
    echo "MongoDB is already running"
else
    echo "Starting MongoDB..."
    mkdir -p ./fresh_db
    mongod --dbpath ./fresh_db --port 27018 &
    echo "MongoDB started on port 27018"
    sleep 2  # Give MongoDB time to start
fi

# Check if bot is running
if pgrep -f "user_bot_main.py" > /dev/null
then
    echo "Bot is already running"
else
    echo "Starting the main bot..."
    source venv/bin/activate
    python user_bot_main.py &
    echo "Bot started in background"
fi

echo "System is up and running!"
echo "To stop, use './scripts/stop_bot.sh'" 