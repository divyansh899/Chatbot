# Bot Management Scripts

This directory contains scripts to manage the Telegram bots running on your system.

## Available Scripts

### `launch_bots.sh`
Launches both the user bot and backup bot with caffeinate to prevent them from stopping during sleep mode.

**Usage:**
```bash
./launch_bots.sh
```

### `stop_bots.sh`
Safely stops all running bot processes.

**Usage:**
```bash
./stop_bots.sh
```

### `check_status.sh`
Shows the current status of all bots, including PID, uptime, and recent log entries.

**Usage:**
```bash
./check_status.sh
```

### `watchdog.sh`
Checks if the bots are running and restarts them if they're not. This is meant to be run via cron.

**Usage:**
```bash
./watchdog.sh
```

### `setup_cron.sh`
Sets up a cron job to run the watchdog script every 5 minutes to ensure bots stay running.

**Usage:**
```bash
./setup_cron.sh
```

### `install_service.sh`
Creates a LaunchAgent to automatically start the bots when you log in to your Mac and keep them running persistently, even after system restarts.

**Usage:**
```bash
./install_service.sh
```

## Recommended Setup for Persistent Bots

For the most reliable bot operation that persists through sleep and system restarts:

1. Install the launch service:
   ```bash
   ./install_service.sh
   ```

2. Set up the watchdog cron job:
   ```bash
   ./setup_cron.sh
   ```

3. Verify everything is running:
   ```bash
   ./check_status.sh
   ```

## Logs

All logs are stored in the `logs` directory:
- `user_bot.log` - Main user bot logs
- `backup_bot.log` - Backup bot logs
- `watchdog.log` - Shows when the watchdog checked and restarted bots
- `launch_service.log` - LaunchAgent service logs 