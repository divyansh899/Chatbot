#!/usr/bin/env python3
"""
This script fixes the indentation error in user_bot.py.
"""

import os
import re
import shutil

def fix_indentation_issue():
    print("Fixing indentation error in user_bot.py...")
    
    # First, create a backup
    backup_filename = "user_bot.py.indentation_backup"
    shutil.copy2("user_bot.py", backup_filename)
    print(f"Created backup at {backup_filename}")
    
    # Read the file
    with open("user_bot.py", "r") as f:
        content = f.read()
    
    # Find the problematic section and fix it
    pattern = r"(# Also update user_states\n\s+if user_id in user_states:\n\s+# Update user state with new step\n)(\s*)tmp_state"
    replacement = r"\1\2            tmp_state"
    
    new_content = re.sub(pattern, replacement, content)
    
    # Write the fixed content back
    with open("user_bot.py", "w") as f:
        f.write(new_content)
    
    print("Fixed indentation error in user_bot.py")
    
if __name__ == "__main__":
    fix_indentation_issue() 