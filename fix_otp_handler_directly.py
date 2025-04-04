#!/usr/bin/env python3

"""
This script fixes only the OTP handler in user_bot.py to improve state management.
"""

import re
import sys
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/fix_otp_directly.log", 'w'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("OTPFixTool")

# Path to the file
USER_BOT_FILE = "user_bot.py"

def fix_otp_handler():
    """Fix state management in the OTP handler"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
            
        # Using a simpler search pattern
        otp_handler_start = "async def handle_otp_code(client, message):"
        if otp_handler_start not in content:
            logger.error("Could not find OTP handler function")
            return False
            
        # Find the OTP handler function
        handler_start_pos = content.find(otp_handler_start)
        if handler_start_pos == -1:
            logger.error("Could not find OTP handler function")
            return False
            
        # Find the section with the state check
        not_waiting_for_code = "if not is_waiting_for_code:"
        not_waiting_pos = content.find(not_waiting_for_code, handler_start_pos)
        if not_waiting_pos == -1:
            logger.error("Could not find 'if not is_waiting_for_code' section")
            return False
            
        # Find the line before it
        prev_line_end = content.rfind("\n", handler_start_pos, not_waiting_pos)
        if prev_line_end == -1:
            logger.error("Could not find previous line end")
            return False
            
        # 1. Add additional state recovery code
        otp_handler_recovery = """
    # First check for case where user_states might be lost but DB record exists
    if not is_waiting_for_code and user_data and "phone_auth" in user_data:
        auth_data = user_data["phone_auth"]
        if auth_data.get("step") == "waiting_for_code":
            is_waiting_for_code = True
            phone_number = auth_data.get("phone_number")
            phone_code_hash = auth_data.get("phone_code_hash")
            print(f"STATE RECOVERY: Restored state for user {user_id} from database")
            
            # Restore user_states from database
            user_states[user_id] = {
                "action": "phone_auth",
                "phone_number": phone_number,
                "phone_code_hash": phone_code_hash,
                "step": "waiting_for_code",
                "restored_at": datetime.now().isoformat()
            }
"""
        
        # Insert the recovery code
        modified_content = content[:prev_line_end + 1] + otp_handler_recovery + content[prev_line_end + 1:]
        
        # Add debug print near the beginning of the function
        user_id_line = "user_id = message.from_user.id"
        user_id_pos = modified_content.find(user_id_line, handler_start_pos)
        if user_id_pos != -1:
            # Find the end of this line
            user_id_line_end = modified_content.find("\n", user_id_pos)
            if user_id_line_end != -1:
                debug_print = "\n    print(f\"OTP State Debug: user={user_id}, states={list(user_states.keys()) if user_states else 'empty'}, message={message.text}\")"
                modified_content = modified_content[:user_id_line_end + 1] + debug_print + modified_content[user_id_line_end + 1:]
                logger.info("Added debug print to OTP handler")
        
        # Clean up state on success
        cleanup_section = "# Clear the phone_auth data"
        cleanup_pos = modified_content.find(cleanup_section, handler_start_pos)
        if cleanup_pos != -1:
            # Find the state cleanup part
            del_state = "del user_states[user_id]"
            del_pos = modified_content.find(del_state, cleanup_pos)
            if del_pos != -1:
                # Insert debug print before state deletion
                debug_print = 'print(f"STATE CLEANUP: Clearing OTP state for user {user_id}")\n            '
                modified_content = modified_content[:del_pos] + debug_print + modified_content[del_pos:]
                logger.info("Added debug print before state cleanup")
        
        # Write the modified content back to the file
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Fixed OTP handler")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing OTP handler: {e}")
        return False

if __name__ == "__main__":
    if fix_otp_handler():
        logger.info("Successfully fixed OTP handler")
    else:
        logger.error("Failed to fix OTP handler")