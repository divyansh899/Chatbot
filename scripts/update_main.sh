#!/bin/bash

# First check if there are any uncommitted changes
if [ -d ".git" ] && command -v git &> /dev/null; then
    if ! git diff --quiet; then
        echo "WARNING: You have uncommitted changes in git. Consider committing first."
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Update aborted."
            exit 1
        fi
    fi
fi

# Create a backup of the current main version
DATE=$(date "+%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="backups/user_bot_backup_$DATE.py"

echo "Creating backup of current main version..."
mkdir -p backups
cp user_bot_main.py "$BACKUP_FILE"
echo "Backup created at $BACKUP_FILE"

# Check if dev version exists
if [ ! -f "development/user_bot_dev.py" ]; then
    echo "ERROR: Development version not found at development/user_bot_dev.py"
    exit 1
fi

# Stop the bot if it's running
if pgrep -f "user_bot_main.py" > /dev/null; then
    echo "Stopping the running bot..."
    pkill -f "user_bot_main.py"
    echo "Bot stopped"
    RESTART_BOT=true
else
    RESTART_BOT=false
fi

# Update the main version
echo "Updating main version from development version..."
cp development/user_bot_dev.py user_bot_main.py

# Add the header back to the main file
echo "Adding main version header comment..."
sed -i.bak '1i\
#!/usr/bin/env python\
# -*- coding: utf-8 -*-\
\
#############################################################\
# TELEGRAM BOT MAIN CODE - DO NOT MODIFY DIRECTLY           #\
# -------------------------------------------------------   #\
# This is the main, stable version of the Telegram bot.     #\
# Any changes should be tested in a development branch      #\
# before being incorporated into this main version.         #\
#                                                           #\
# Last updated: '"$(date "+%B %d, %Y")"'                               #\
# Features:                                                 #\
# - Telegram and WhatsApp number management                 #\
# - OTP forwarding and monitoring                           #\
# - Session management with import/export                   #\
# - Admin panel with user management                        #\
# - Payment processing                                      #\
#############################################################\
' user_bot_main.py

# Make executable
chmod +x user_bot_main.py

# Restart the bot if it was running
if [ "$RESTART_BOT" = true ]; then
    echo "Restarting the bot..."
    source venv/bin/activate
    python user_bot_main.py &
    echo "Bot restarted"
fi

echo "Update complete! Main version is now updated from development version."
echo "A backup was created at: $BACKUP_FILE" 