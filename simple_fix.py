#!/usr/bin/env python3

"""
This script restores the bot from backup and adds a single simple state fix
to help with multiple session generation.
"""

import os
import shutil
import time

# Restore from backup
original_backup = "user_bot.py.backup_20250404_174739"
if os.path.exists(original_backup):
    print(f"Restoring from {original_backup}")
    shutil.copy2(original_backup, "user_bot.py")
else:
    print("Backup file not found!")
    exit(1)

# Add a simple state fix to clear all states at each OTP code entry
fix = """

    # Clear any existing states at the beginning of each session generation
    if message.from_user and message.from_user.id:
        user_id = message.from_user.id
        # Check all user states and remove any lingering ones for this user
        for state_user_id in list(user_states.keys()):
            if state_user_id == user_id:
                print(f"Clearing previous state for user {user_id} at session start")
                del user_states[user_id]
                break
"""

with open("user_bot.py", "r") as f:
    content = f.read()

# Find the generate_session function
target = "async def generate_session(client, message, phone_number, regenerate=False):"
if target in content:
    # Find the beginning of the function body
    pos = content.find(target) + len(target)
    # Find first non-comment line
    first_line = content.find("    user_id = message.from_user.id", pos)
    if first_line > 0:
        # Insert our fix right before it
        new_content = content[:first_line] + fix + content[first_line:]
        
        # Write the updated content
        with open("user_bot.py", "w") as f:
            f.write(new_content)
        
        print("Successfully added state clearing to generate_session function")
    else:
        print("Could not find insertion point in generate_session function")
else:
    print("Could not find generate_session function")

print("Done!") 