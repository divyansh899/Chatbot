#!/usr/bin/env python3

"""
This script directly modifies specific parts of the user_bot.py file
to fix issues with state management that cause problems when generating
multiple sessions in sequence.
"""

import os
import re
import sys
import logging
import shutil
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/direct_fix.log", 'w'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("DirectFixTool")

# Path to the file
USER_BOT_FILE = "user_bot.py"
BACKUP_FILE = f"{USER_BOT_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def backup_file():
    """Create a backup of the file"""
    try:
        shutil.copy2(USER_BOT_FILE, BACKUP_FILE)
        logger.info(f"Created backup of {USER_BOT_FILE} at {BACKUP_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def fix_otp_handler():
    """Fix state management in the OTP handler"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
        
        # Find the OTP handler function
        otp_handler_regex = r'@user_bot\.on_message\(filters\.regex\(r\'\^\\\d\{5,6\}\$\'\) & filters\.private\)\nasync def handle_otp_code\(client, message\):'
        if not re.search(otp_handler_regex, content):
            logger.error("Could not find OTP handler function")
            return False
        
        # 1. Fix: Add additional state recovery in OTP handler
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
        
        # Find position to insert recovery code
        not_waiting_regex = r'if not is_waiting_for_code:'
        match = re.search(not_waiting_regex, content)
        if not match:
            logger.error("Could not find insertion point for state recovery")
            return False
        
        # Get position just before "if not is_waiting_for_code:"
        pos = match.start()
        
        # Find the line before it
        prev_line_end = content.rfind("\n", 0, pos)
        if prev_line_end == -1:
            prev_line_end = 0
        
        # Insert recovery code
        modified_content = content[:prev_line_end + 1] + otp_handler_recovery + content[prev_line_end + 1:]
        
        # 2. Fix: Ensure we clear states properly on success
        success_pattern = r'# Clear the phone_auth data\s+users\.update_one\(\s+\{"user_id": user_id\},\s+\{\"\$unset\": \{"phone_auth": ""\}\}\s+\)\s+\s+# Also clear from user_states\s+if user_id in user_states:\s+del user_states\[user_id\]'
        
        success_replacement = """# Clear the phone_auth data
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"phone_auth": ""}}
        )
        
        # Also clear from user_states
        if user_id in user_states:
            print(f"STATE CLEANUP: Clearing state for user {user_id} after successful OTP processing")
            del user_states[user_id]"""
        
        modified_content = re.sub(success_pattern, success_replacement, modified_content)
        
        # 3. Fix: Add debugging prints to trace state problems
        debug_print = "print(f\"OTP State Debug: user={user_id}, states={list(user_states.keys()) if user_states else 'empty'}\")"
        
        # Add debug print at beginning of function
        otp_func_pattern = r'async def handle_otp_code\(client, message\):[^\n]+\n\s+user_id = message\.from_user\.id'
        modified_content = re.sub(
            otp_func_pattern,
            f'async def handle_otp_code(client, message):\\n    """Handle direct OTP code messages"""\\n    user_id = message.from_user.id\\n    {debug_print}',
            modified_content
        )
        
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Fixed OTP handler state management")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing OTP handler: {e}")
        return False

def fix_generate_session():
    """Fix state management in the generate_session function"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
        
        # Find the generate_session function
        gen_session_regex = r'async def generate_session\(client, message, phone_number, regenerate=False\):'
        if not re.search(gen_session_regex, content):
            logger.error("Could not find generate_session function")
            return False
        
        # Add state logging to the user_states assignment
        # Original pattern
        state_assignment_pattern = r'user_states\[user_id\] = \{\s+"action": "phone_auth",\s+"phone_number": phone_number,\s+"phone_code_hash": phone_code_hash\.phone_code_hash,\s+"step": "waiting_for_code"\s+\}'
        
        # New code with debugging
        state_assignment_replacement = """user_states[user_id] = {
            "action": "phone_auth",
            "phone_number": phone_number,
            "phone_code_hash": phone_code_hash.phone_code_hash,
            "step": "waiting_for_code",
            "started_at": datetime.now().isoformat()
        }
        print(f"STATE UPDATE: Set state for user {user_id}, phone {phone_number}")"""
        
        modified_content = re.sub(state_assignment_pattern, state_assignment_replacement, content)
        
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Fixed generate_session state management")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing generate_session: {e}")
        return False

def fix_text_handler():
    """Fix state management in text input handler"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
        
        # Find the handle_text_input function
        text_handler_regex = r'@user_bot\.on_message\(filters\.text & filters\.private\)\nasync def handle_text_input\(client, message\):'
        if not re.search(text_handler_regex, content):
            logger.error("Could not find handle_text_input function")
            return False
        
        # 1. Add state debugging at start of function
        debug_print = "print(f\"TEXT HANDLER: user={user_id}, text={text[:10]}..., states={list(user_states.keys()) if user_states else 'empty'}\")"
        
        # Pattern to find start of function
        text_func_pattern = r'async def handle_text_input\(client, message\):[^\n]+\n\s+user_id = message\.from_user\.id\s+text = message\.text\.strip\(\)'
        modified_content = re.sub(
            text_func_pattern,
            f'async def handle_text_input(client, message):\\n    """Handle text input from users"""\\n    user_id = message.from_user.id\\n    text = message.text.strip()\\n    {debug_print}',
            content
        )
        
        # 2. Fix state cleanup
        # For each "del user_states[user_id]", add a debug print
        state_cleanup_pattern = r'del user_states\[user_id\]'
        state_cleanup_replacement = 'print(f"STATE CLEANUP: Clearing state for user {user_id} in text handler")\\n                del user_states[user_id]'
        
        modified_content = re.sub(state_cleanup_pattern, state_cleanup_replacement, modified_content)
        
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Fixed text handler state management")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing text handler: {e}")
        return False

def add_startup_cleanup():
    """Add state cleanup on bot startup"""
    try:
        with open(USER_BOT_FILE, "r") as f:
            content = f.read()
        
        # Find the run_bot function
        run_bot_regex = r'async def run_bot\(\):'
        match = re.search(run_bot_regex, content)
        if not match:
            logger.error("Could not find run_bot function")
            return False
        
        # Add cleanup code at beginning of function
        startup_cleanup = """
    # Clear any stale user states at startup
    user_states.clear()
    print(f"STATE CLEANUP: Cleared all user states at startup ({datetime.now().isoformat()})")
    """
        
        # Insert after function declaration and any comment/docstring
        pos = match.end()
        # Find opening brace of function body (usually the first line after declaration)
        next_line = content.find("\n", pos)
        if next_line == -1:
            logger.error("Could not find insertion point in run_bot function")
            return False
        
        modified_content = content[:next_line + 1] + startup_cleanup + content[next_line + 1:]
        
        with open(USER_BOT_FILE, "w") as f:
            f.write(modified_content)
        
        logger.info("Added startup cleanup code")
        return True
    
    except Exception as e:
        logger.error(f"Error adding startup cleanup: {e}")
        return False

def apply_fixes():
    """Apply all fixes to the file"""
    if not backup_file():
        logger.error("Backup failed, aborting")
        return False
    
    success = fix_otp_handler()
    success = fix_generate_session() and success
    success = fix_text_handler() and success
    success = add_startup_cleanup() and success
    
    if success:
        logger.info("All fixes applied successfully")
    else:
        logger.warning("Some fixes failed to apply")
    
    return success

if __name__ == "__main__":
    apply_fixes() 