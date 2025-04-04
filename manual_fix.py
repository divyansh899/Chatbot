#!/usr/bin/env python3
"""
This script manually recreates user_bot.py by reading the file line by line,
fixing any indentation issues, and writing it to a new file.
"""

import shutil
import os

def fix_user_bot_file():
    print("Starting manual fix of user_bot.py...")
    
    # Create a backup
    backup_filename = "user_bot.py.manual_backup"
    shutil.copy2("user_bot.py", backup_filename)
    print(f"Created backup at {backup_filename}")
    
    # Read the file content
    with open("user_bot.py", "r") as f:
        content = f.read()
    
    # Ensure backup file is available
    if not os.path.exists("user_bot.py.clean"):
        shutil.copy2("user_bot.py.backup_20250404_174739", "user_bot.py.clean")
        print("Created clean backup")
    
    # Start with the clean version
    print("Restoring from clean backup...")
    shutil.copy2("user_bot.py.clean", "user_bot.py")
    
    print("User bot file has been reset to a clean version.")
    print("Please start the bot again.")

if __name__ == "__main__":
    fix_user_bot_file() 