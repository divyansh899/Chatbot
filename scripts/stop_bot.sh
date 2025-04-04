#!/bin/bash

# Stop the bot
if pgrep -f "user_bot_main.py" > /dev/null
then
    echo "Stopping the bot..."
    pkill -f "user_bot_main.py"
    echo "Bot stopped"
else
    echo "Bot is not running"
fi

# Stop MongoDB (optional, comment out if you want to keep MongoDB running)
if pgrep -x "mongod" > /dev/null
then
    echo "Stopping MongoDB..."
    pkill -f mongod
    echo "MongoDB stopped"
else
    echo "MongoDB is not running"
fi

echo "System has been shut down."
echo "To start again, use './scripts/start_bot.sh'" 