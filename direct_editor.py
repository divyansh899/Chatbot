#!/usr/bin/env python3
"""
This script directly edits specific lines in user_bot.py to fix the indentation issue.
"""

def fix_indentation():
    print("Reading user_bot.py...")
    with open("user_bot.py", "r") as f:
        lines = f.readlines()
    
    # Let's find the specific lines with the if statement and indentation issue
    found = False
    for i in range(len(lines)):
        if i+3 < len(lines) and "if user_id in user_states:" in lines[i] and "# Update user state with new step" in lines[i+1]:
            print(f"Found problematic area at line {i+1}")
            # Fix the indentation for the next lines
            base_indent = lines[i].rstrip().find("if")
            lines[i+2] = ' ' * (base_indent + 4) + "tmp_state = user_states[user_id].copy()\n"
            
            if i+3 < len(lines) and "tmp_state[\"step\"]" in lines[i+3]:
                lines[i+3] = ' ' * (base_indent + 4) + "tmp_state[\"step\"] = \"waiting_for_2fa\"\n"
            
            if i+4 < len(lines) and "set_user_state" in lines[i+4]:
                lines[i+4] = ' ' * (base_indent + 4) + "set_user_state(user_id, tmp_state)\n"
            
            found = True
            print(f"Fixed indentation at lines {i+1}-{i+5}")
            break
    
    if not found:
        print("Could not find the problematic code section")
        return
    
    # Write back to the file
    print("Writing back to user_bot.py...")
    with open("user_bot.py", "w") as f:
        f.writelines(lines)
    
    print("Done fixing indentation")

if __name__ == "__main__":
    fix_indentation() 