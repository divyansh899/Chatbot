#!/usr/bin/env python3

"""
This script adds minimal changes to fix the OTP handler and enable multiple session generations.
"""

import os
import re
import shutil

# Restore from the clean backup
shutil.copy2("user_bot.py.clean", "user_bot.py")
print("Restored from clean backup")

# Read the file
with open("user_bot.py", "r") as f:
    content = f.read()

# Fix 1: Make the OTP handler also check the DB for states
otp_handler_pattern = "@user_bot.on_message(filters.regex(r'^\\d{5,6}$') & filters.private)"
if otp_handler_pattern not in content:
    print("OTP handler not found!")
    exit(1)

otp_not_waiting_pattern = "if not is_waiting_for_code:"
otp_section_start = content.find(otp_handler_pattern)
otp_check_pos = content.find(otp_not_waiting_pattern, otp_section_start)

if otp_check_pos > 0:
    # Add code to check DB as an additional recovery mechanism
    recovery_code = """
    # Also check database as a fallback
    if not is_waiting_for_code and user_data and "phone_auth" in user_data:
        auth_data = user_data["phone_auth"]
        if auth_data.get("step") == "waiting_for_code":
            is_waiting_for_code = True
            phone_number = auth_data.get("phone_number")
            phone_code_hash = auth_data.get("phone_code_hash")
            print(f"Recovery: Restored state from database for user {user_id}")
            
            # Also restore in-memory state
            user_states[user_id] = {
                "action": "phone_auth",
                "phone_number": phone_number,
                "phone_code_hash": phone_code_hash,
                "step": "waiting_for_code"
            }
    
    """
    
    new_content = content[:otp_check_pos] + recovery_code + content[otp_check_pos:]
    content = new_content
    print("Added state recovery to OTP handler")

# Fix 2: Clear any existing states when starting a new session generation
generate_session_pattern = "async def generate_session(client, message, phone_number, regenerate=False):"
if generate_session_pattern not in content:
    print("generate_session function not found!")
    exit(1)

user_id_pattern = "    user_id = message.from_user.id"
gen_section_start = content.find(generate_session_pattern)
user_id_pos = content.find(user_id_pattern, gen_section_start)

if user_id_pos > 0:
    # Add code to clear existing states
    cleanup_code = """
    # Clear any existing states for this user
    if user_id in user_states:
        print(f"Clearing previous state for user {user_id} before starting new session")
        del user_states[user_id]
        
    """
    
    new_content = content[:user_id_pos + len(user_id_pattern) + 1] + cleanup_code + content[user_id_pos + len(user_id_pattern) + 1:]
    content = new_content
    print("Added state cleanup to generate_session function")

# Fix 3: Clear all states at bot startup
run_bot_pattern = "async def run_bot():"
if run_bot_pattern not in content:
    print("run_bot function not found!")
    exit(1)

run_bot_try_pattern = "    try:"
run_bot_pos = content.find(run_bot_pattern)
try_pos = content.find(run_bot_try_pattern, run_bot_pos)

if try_pos > 0:
    # Add code to clear all states at startup
    startup_code = """
        # Clear all user states at startup
        global user_states
        user_states.clear()
        print("Cleared all user states at startup")
        
    """
    
    new_content = content[:try_pos + len(run_bot_try_pattern) + 1] + startup_code + content[try_pos + len(run_bot_try_pattern) + 1:]
    content = new_content
    print("Added state cleanup at bot startup")

# Write the updated content
with open("user_bot.py", "w") as f:
    f.write(content)

print("All fixes applied successfully!") 