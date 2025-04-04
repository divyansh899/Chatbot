#!/usr/bin/env python3
"""
This script directly fixes the indentation error in user_bot.py.
"""

import os
import shutil

def fix_indentation_issue():
    print("Fixing indentation error in user_bot.py...")
    
    # Create a backup
    backup_filename = "user_bot.py.direct_backup"
    shutil.copy2("user_bot.py", backup_filename)
    print(f"Created backup at {backup_filename}")
    
    # Read the file content
    with open("user_bot.py", "r") as f:
        lines = f.readlines()
    
    # Look for the specific problematic lines
    for i in range(len(lines)):
        if "# Also update user_states" in lines[i] and i+2 < len(lines):
            # Check the next lines
            if "if user_id in user_states:" in lines[i+1] and "# Update user state with new step" in lines[i+2]:
                # Fix the indentation of the next three lines
                if i+3 < len(lines) and "tmp_state = user_states[user_id].copy()" in lines[i+3]:
                    indent_level = lines[i+1].index("if")
                    lines[i+3] = ' ' * (indent_level + 4) + "tmp_state = user_states[user_id].copy()\n"
                    
                if i+4 < len(lines) and "tmp_state[\"step\"] = \"waiting_for_2fa\"" in lines[i+4]:
                    indent_level = lines[i+1].index("if")
                    lines[i+4] = ' ' * (indent_level + 4) + "tmp_state[\"step\"] = \"waiting_for_2fa\"\n"
                    
                if i+5 < len(lines) and "set_user_state(user_id, tmp_state)" in lines[i+5]:
                    indent_level = lines[i+1].index("if")
                    lines[i+5] = ' ' * (indent_level + 4) + "set_user_state(user_id, tmp_state)\n"
                    
                print(f"Fixed indentation at lines {i+3}, {i+4}, and {i+5}")
                break
    
    # Write the corrected content back
    with open("user_bot.py", "w") as f:
        f.writelines(lines)
    
    print("Finished fixing indentation in user_bot.py")

if __name__ == "__main__":
    fix_indentation_issue() 