#!/usr/bin/env python3
"""
This script fixes the specific indentation issue at lines 6186-6190 of user_bot.py
"""

def fix_specific_indentation():
    print("Reading user_bot.py...")
    with open("user_bot.py", "r") as f:
        lines = f.readlines()
    
    # The lines we need to fix are 6186-6190 (0-indexed would be 6185-6189)
    # Line 6186: if user_id in user_states:
    # Line 6187: # Update user state with new step
    # Line 6188: tmp_state = user_states[user_id].copy()   <-- needs indentation
    # Line 6189: tmp_state["step"] = "waiting_for_2fa"     <-- needs indentation
    # Line 6190: set_user_state(user_id, tmp_state)        <-- needs indentation
    
    if len(lines) >= 6190:
        # Find the indentation level of the if statement
        if_line = lines[6185].rstrip('\n')
        if_indent = if_line.index("if")
        
        # Add 4 spaces to that for the indented block
        block_indent = if_indent + 4
        
        # Fix lines 6188-6190
        lines[6187] = ' ' * block_indent + "tmp_state = user_states[user_id].copy()\n"
        lines[6188] = ' ' * block_indent + "tmp_state[\"step\"] = \"waiting_for_2fa\"\n"
        lines[6189] = ' ' * block_indent + "set_user_state(user_id, tmp_state)\n"
        
        print("Fixed indentation at lines 6188-6190")
    else:
        print("Error: File doesn't have enough lines")
        return
    
    # Write the fixed content back
    with open("user_bot.py", "w") as f:
        f.writelines(lines)
    
    print("Done fixing indentation")

if __name__ == "__main__":
    fix_specific_indentation() 