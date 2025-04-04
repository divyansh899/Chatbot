#!/usr/bin/env python3

"""
This script fixes the indentation error in user_bot.py
"""

import re
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("IndentationFixer")
USER_BOT_FILE = "user_bot.py"

def fix_indentation():
    """Fix the indentation error in the user_bot.py file"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
        
        # Find the problematic line
        problem_line = "tmp_state = user_states[user_id].copy()"
        line_pos = content.find(problem_line)
        
        if line_pos == -1:
            logger.error("Could not find the problematic line")
            return False
        
        # Find the beginning of the line
        line_start = content.rfind("\n", 0, line_pos) + 1
        
        # Check the indentation
        indentation = content[line_start:line_pos]
        if not indentation:
            logger.error("Could not determine indentation")
            return False
        
        # Find the if statement before it
        if_statement = "if user_id in user_states:"
        if_pos = content.rfind(if_statement, 0, line_pos)
        
        if if_pos == -1:
            logger.error("Could not find the if statement")
            return False
        
        # Get section from if statement to the problematic line
        section = content[if_pos:line_pos]
        
        # Fix the indentation
        fixed_section = section.replace(
            "if user_id in user_states:",
            "if user_id in user_states:\n                "
        )
        
        # Replace the content
        modified_content = content[:if_pos] + fixed_section + content[line_pos:]
        
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Fixed indentation error")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing indentation: {e}")
        return False

if __name__ == "__main__":
    if fix_indentation():
        logger.info("Successfully fixed indentation error")
    else:
        logger.error("Failed to fix indentation error") 