#!/usr/bin/env python3

"""
This script adds state cleanup at bot startup
"""

import os

# Add state cleanup code for bot startup
startup_fix = """
    # Clear any stale user states at startup
    global user_states
    user_states.clear()
    print(f"Cleared all user states at startup")
    
"""

with open("user_bot.py", "r") as f:
    content = f.read()

# Find the run_bot function
target = "async def run_bot():"
if target not in content:
    print("run_bot function not found!")
    exit(1)

# Find the beginning of the function
pos_start = content.find(target) + len(target)

# Find a good insertion point - after first few lines
pos_insert = content.find("    try:", pos_start)
if pos_insert == -1:
    print("Could not find 'try:' in run_bot function!")
    exit(1)

# Insert our cleanup code right after the try
pos_insert = content.find("\n", pos_insert) + 1
new_content = content[:pos_insert] + startup_fix + content[pos_insert:]

# Write the updated content
with open("user_bot.py", "w") as f:
    f.write(new_content)

print("Successfully added state cleanup at bot startup")
print("Done!") 