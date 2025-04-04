#!/usr/bin/env python3
"""
This script manually fixes the try block indentation.
"""

def fix_try_block():
    # Read the content
    with open("user_bot.py", "r") as f:
        lines = f.readlines()
    
    # Find the run_bot function and fix the try block manually
    for i in range(len(lines)):
        if "async def run_bot():" in lines[i]:
            run_bot_line = i
            break
    
    # Locate the try statement
    for i in range(run_bot_line, len(lines)):
        if "try:" in lines[i] and lines[i].strip() == "try:":
            try_line = i
            break
    
    # Calculate proper indentation based on the line before try
    base_indent = lines[try_line].index("try")
    
    # Examine what comes after try
    print(f"Found try statement at line {try_line+1}, examining next lines...")
    
    # Manually replace the problematic section
    correct_lines = []
    
    # Add the lines up to and including try:
    correct_lines.extend(lines[:try_line+1])
    
    # Add properly indented cleanup code
    correct_lines.append(' ' * (base_indent + 4) + "# Clear all user states at startup\n")
    correct_lines.append(' ' * (base_indent + 4) + "global user_states\n")
    correct_lines.append(' ' * (base_indent + 4) + "user_states.clear()\n")
    correct_lines.append(' ' * (base_indent + 4) + "print(\"Cleared all user states at startup\")\n")
    correct_lines.append("\n")
    
    # Find the next proper line
    next_line = None
    for i in range(try_line + 1, try_line + 15):
        if "print(\"Checking for active virtual numbers" in lines[i]:
            next_line = i
            break
    
    if next_line:
        # Add properly indented next line
        correct_lines.append(' ' * (base_indent + 4) + lines[next_line].lstrip())
        
        # Add the rest of the file
        correct_lines.extend(lines[next_line+1:])
        
        # Write the corrected content
        with open("user_bot.py", "w") as f:
            f.writelines(correct_lines)
        
        print(f"Fixed try block starting at line {try_line+1}")
    else:
        print("Could not find the expected next line after try statement")

if __name__ == "__main__":
    fix_try_block() 