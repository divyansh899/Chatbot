#!/usr/bin/env python3

"""
This script adds state recovery to the OTP handler
"""

import os

# Add state recovery code to check the database if in-memory state is lost
otp_fix = """
    # Check if there's state data in the database even if memory state is missing
    if not is_waiting_for_code and user_data and "phone_auth" in user_data:
        auth_data = user_data["phone_auth"]
        if auth_data.get("step") == "waiting_for_code":
            is_waiting_for_code = True
            phone_number = auth_data.get("phone_number")
            phone_code_hash = auth_data.get("phone_code_hash")
            print(f"STATE RECOVERY: Restored state from database for user {user_id}")
            
            # Restore the memory state too
            user_states[user_id] = {
                "action": "phone_auth",
                "phone_number": phone_number,
                "phone_code_hash": phone_code_hash,
                "step": "waiting_for_code"
            }
"""

with open("user_bot.py", "r") as f:
    content = f.read()

# Find the OTP handler function that processes direct OTP messages
target_fn_start = "@user_bot.on_message(filters.regex(r'^\\d{5,6}$') & filters.private)"
if target_fn_start not in content:
    print("OTP handler function not found!")
    exit(1)

# Find the "if not is_waiting_for_code:" line
target_check = "if not is_waiting_for_code:"
pos_start = content.find(target_fn_start)
pos_check = content.find(target_check, pos_start)

if pos_check == -1:
    print("Could not find 'if not is_waiting_for_code:' in OTP handler!")
    exit(1)

# Insert our recovery code just before this check
new_content = content[:pos_check] + otp_fix + content[pos_check:]

# Write the updated content
with open("user_bot.py", "w") as f:
    f.write(new_content)

print("Successfully added state recovery to OTP handler")

# Add another improvement to clear states after successful processing
success_clear = """
        # Make sure state is fully cleared for this user
        if user_id in user_states:
            print(f"SUCCESS CLEANUP: Clearing state for user {user_id} after successful session")
            del user_states[user_id]
        # Also clear any lingering DB state
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"phone_auth": ""}}
        )
"""

with open("user_bot.py", "r") as f:
    content = f.read()

# Find where we update the database with the session string
target_success = "numbers_inventory.update_one("
pos_start = content.find(target_fn_start)
pos_success = content.find(target_success, pos_start)

if pos_success == -1:
    print("Could not find 'numbers_inventory.update_one(' in OTP handler!")
    exit(1)

# Find the end of this update block
pos_end = content.find(")", pos_success)
if pos_end == -1:
    print("Could not find the end of the update block!")
    exit(1)
pos_end = content.find("\n", pos_end)

# Insert our success cleanup right after this
new_content = content[:pos_end+1] + success_clear + content[pos_end+1:]

# Write the updated content
with open("user_bot.py", "w") as f:
    f.write(new_content)

print("Successfully added state cleanup after successful session generation")
print("Done!") 