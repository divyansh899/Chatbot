#!/bin/bash

# Make sure the watchdog is executable
chmod +x /Users/divyanshchugh/Desktop/chat\ bot/scripts/watchdog.sh

# Export the current crontab
crontab -l > /tmp/current_crontab 2>/dev/null || echo "" > /tmp/current_crontab

# Check if our entry is already in the crontab
if grep -q "watchdog.sh" /tmp/current_crontab; then
    echo "Watchdog cron job already exists. No changes made."
else
    # Add our watchdog job to run every 5 minutes
    echo "*/5 * * * * /Users/divyanshchugh/Desktop/chat\ bot/scripts/watchdog.sh >/dev/null 2>&1" >> /tmp/current_crontab
    
    # Import the updated crontab
    crontab /tmp/current_crontab
    
    echo "Watchdog cron job set up successfully. It will run every 5 minutes."
    echo "The watchdog will check if bots are running and restart them if needed."
fi

# Clean up
rm /tmp/current_crontab

echo "To see your current cron jobs, run: crontab -l" 