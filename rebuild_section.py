#!/usr/bin/env python3

import re

# The problematic part of the file
with open('user_bot.py', 'r') as f:
    content = f.read()

# Find the section with the SessionPasswordNeededError exception handling
section_start = content.find("except SessionPasswordNeededError:")
if section_start == -1:
    print("Could not find the section")
    exit(1)

# Find the beginning and end of the problematic section
start_line = content.rfind('\n', 0, section_start) + 1
end_line = content.find('await telethon_client.disconnect()', section_start)
if end_line == -1:
    print("Could not find the end of the section")
    exit(1)

# Find the line after the disconnect
end_line = content.find('\n', end_line)
if end_line == -1:
    print("Could not find the newline after disconnect")
    exit(1)

# Extract the part before and after the problematic section
before = content[:start_line]
after = content[end_line:]

# Create a new, properly indented section
new_section = """            except SessionPasswordNeededError:
                # Need 2FA password
                users.update_one(
                    {"user_id": user_id},
                    {"$set": {"phone_auth.step": "waiting_for_2fa"}},
                    upsert=True
                )
                
                # Also update user_states
                if user_id in user_states:
                    # Update user state with new step
                    tmp_state = user_states[user_id].copy()
                    tmp_state["step"] = "waiting_for_2fa"
                    print(f"STATE UPDATE: Updated state for user {user_id} to waiting_for_2fa")
                    if 'set_user_state' in globals():
                        set_user_state(user_id, tmp_state)
                    else:
                        user_states[user_id] = tmp_state
                else:
                    # Create new state
                    user_states[user_id] = {
                        "action": "phone_auth",
                        "phone_number": phone_number,
                        "step": "waiting_for_2fa"
                    }
                    print(f"STATE UPDATE: Set new state for user {user_id} to waiting_for_2fa")
                
                await telethon_client.disconnect()
"""

# Combine everything back together
new_content = before + new_section + after

# Write the file back
with open('user_bot.py', 'w') as f:
    f.write(new_content)

print("Successfully rebuilt the problematic section") 