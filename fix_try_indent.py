#!/usr/bin/env python3
"""
This script fixes the indentation error after the try statement at line 7708
"""

def fix_indentation():
    print("Reading user_bot.py...")
    with open("user_bot.py", "r") as f:
        lines = f.readlines()
    
    # Fix indentation for lines 7709-7713 (0-indexed would be 7708-7712)
    if len(lines) >= 7713:
        # Find the indentation level of the try statement
        try_line = lines[7707].rstrip('\n')
        try_indent = try_line.index("try")
        
        # Add 4 spaces to that for the indented block
        block_indent = try_indent + 4
        
        # The added lines after try need to be indented
        lines[7708] = ' ' * block_indent + lines[7708].lstrip()
        lines[7709] = ' ' * block_indent + lines[7709].lstrip()
        lines[7710] = ' ' * block_indent + lines[7710].lstrip()
        lines[7711] = ' ' * block_indent + lines[7711].lstrip()
        
        print("Fixed indentation after try statement at line 7708")
    else:
        print("Error: File doesn't have enough lines")
        return
    
    # Write the fixed content back
    with open("user_bot.py", "w") as f:
        f.writelines(lines)
    
    print("Done fixing indentation")

if __name__ == "__main__":
    fix_indentation() 