#!/bin/bash

# This script creates and installs a LaunchAgent to keep the bots running persistently

# Define the user and paths
USER_DIR=$(cd ~ && pwd)
BOT_DIR="/Users/divyanshchugh/Desktop/chat bot"
LAUNCH_AGENTS_DIR="$USER_DIR/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/com.telegrambot.daemon.plist"

# Create the LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Create the plist file
cat > "$PLIST_FILE" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.telegrambot.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${BOT_DIR}/scripts/launch_bots.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${BOT_DIR}/logs/launch_service.log</string>
    <key>StandardErrorPath</key>
    <string>${BOT_DIR}/logs/launch_service_error.log</string>
    <key>WorkingDirectory</key>
    <string>${BOT_DIR}</string>
</dict>
</plist>
EOL

# Set proper permissions
chmod 644 "$PLIST_FILE"

# Load the LaunchAgent
launchctl unload "$PLIST_FILE" 2>/dev/null
launchctl load -w "$PLIST_FILE"

echo "LaunchAgent installed and loaded successfully."
echo "Your Telegram bots will now start automatically when you log in"
echo "and will restart if they crash or if your Mac restarts."
echo ""
echo "Plist file created at: $PLIST_FILE"
echo ""
echo "To uninstall this service, run: launchctl unload $PLIST_FILE" 