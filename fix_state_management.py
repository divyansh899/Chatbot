#!/usr/bin/env python3

"""
This script patches the user_bot.py file to improve state management for session generation.
It fixes the issue where the bot fails to handle multiple session generations properly.
"""

import os
import re
import sys
import logging
import shutil
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/state_fix.log", 'w'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("StateFixerTool")

# Constants
USER_BOT_FILE = "user_bot.py"
BACKUP_FILE = f"{USER_BOT_FILE}.before_state_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def create_backup():
    """Create a backup of the user_bot.py file"""
    try:
        logger.info(f"Creating backup of {USER_BOT_FILE} to {BACKUP_FILE}")
        shutil.copy2(USER_BOT_FILE, BACKUP_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def add_state_debug_logging():
    """Add debugging code to log state changes"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Add function to log state changes
        state_debug_functions = """
# State debugging functions
def log_state_change(user_id, action, old_state=None, new_state=None, operation="update"):
    '''Log state changes for debugging'''
    if old_state is None:
        old_state = user_states.get(user_id, {})
    
    print(f"STATE CHANGE: User {user_id} - {operation} - {action}")
    print(f"  Old state: {old_state}")
    print(f"  New state: {new_state}")

def set_user_state(user_id, state_dict):
    '''Set user state with logging'''
    old_state = user_states.get(user_id, {})
    user_states[user_id] = state_dict
    log_state_change(user_id, "set_state", old_state, state_dict, "set")

def clear_user_state(user_id, reason="completed"):
    '''Clear user state with logging'''
    if user_id in user_states:
        old_state = user_states[user_id]
        del user_states[user_id]
        log_state_change(user_id, reason, old_state, None, "clear")
"""
        
        # Find a good insertion point - right after the global variables
        # Look for the first function or decorator after user_states
        match = re.search(r'user_states\s*=\s*\{\}.*?(?=\n@|\ndef\s+|\nclass\s+)', content, re.DOTALL)
        if match:
            insertion_point = match.end()
            new_content = content[:insertion_point] + state_debug_functions + content[insertion_point:]
            
            with open(USER_BOT_FILE, 'w') as f:
                f.write(new_content)
            
            logger.info(f"Added state debugging functions to {USER_BOT_FILE}")
            return True
        else:
            logger.error("Could not find insertion point for state debugging functions")
            return False
    
    except Exception as e:
        logger.error(f"Error adding state debugging functions: {e}")
        return False

def update_generate_session_function():
    """Update the generate_session function to use the new state management"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Replace the user state assignment
        # Original: user_states[user_id] = { ... }
        if "user_states[user_id] = {" in content:
            modified_content = content.replace(
                "user_states[user_id] = {\n            \"action\": \"phone_auth\",\n            \"phone_number\": phone_number,\n            \"phone_code_hash\": phone_code_hash.phone_code_hash,\n            \"step\": \"waiting_for_code\"\n        }",
                "set_user_state(user_id, {\n            \"action\": \"phone_auth\",\n            \"phone_number\": phone_number,\n            \"phone_code_hash\": phone_code_hash.phone_code_hash,\n            \"step\": \"waiting_for_code\"\n        })"
            )
            
            logger.info("Updated user state assignment in generate_session function")
        else:
            logger.warning("Could not find user state assignment in generate_session function")
            modified_content = content
        
        # Find and replace state deletions - convert to clear_user_state()
        final_content = re.sub(
            r'del user_states\[user_id\]',
            r'clear_user_state(user_id)',
            modified_content
        )
        
        with open(USER_BOT_FILE, 'w') as f:
            f.write(final_content)
        
        logger.info("Updated state deletion throughout the file")
        return True
    
    except Exception as e:
        logger.error(f"Error updating generate_session function: {e}")
        return False

def update_otp_handler():
    """Update the OTP handler to use the new state management functions"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Find the OTP handler - look for the specific section where we update user_states
        if "user_states[user_id][\"step\"] = \"waiting_for_2fa\"" in content:
            modified_content = content.replace(
                "user_states[user_id][\"step\"] = \"waiting_for_2fa\"",
                "# Update user state with new step\n                tmp_state = user_states[user_id].copy()\n                tmp_state[\"step\"] = \"waiting_for_2fa\"\n                set_user_state(user_id, tmp_state)"
            )
            
            # Also update the else section
            modified_content = modified_content.replace(
                "user_states[user_id] = {\n                    \"action\": \"phone_auth\",\n                    \"phone_number\": phone_number,\n                    \"step\": \"waiting_for_2fa\"\n                }",
                "set_user_state(user_id, {\n                    \"action\": \"phone_auth\",\n                    \"phone_number\": phone_number,\n                    \"step\": \"waiting_for_2fa\"\n                })"
            )
            
            # Update the del statement
            modified_content = modified_content.replace(
                "del user_states[user_id]",
                "clear_user_state(user_id, \"otp_completed\")"
            )
            
            with open(USER_BOT_FILE, 'w') as f:
                f.write(modified_content)
            
            logger.info("Updated OTP handler to use new state management")
            return True
        else:
            logger.warning("Could not find OTP handler in file")
            return False
    
    except Exception as e:
        logger.error(f"Error updating OTP handler: {e}")
        return False

def update_handle_text_input():
    """Update the handle_text_input function to better handle state management"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Find the handle_text_input function
        if "async def handle_text_input(client, message):" in content:
            # Update to use clear_user_state instead of del
            modified_content = content.replace(
                "del user_states[user_id]",
                "clear_user_state(user_id, \"text_handler_completed\")"
            )
            
            with open(USER_BOT_FILE, 'w') as f:
                f.write(modified_content)
            
            logger.info("Updated handle_text_input to use clear_user_state")
            return True
        else:
            logger.warning("Could not find handle_text_input function")
            return False
    
    except Exception as e:
        logger.error(f"Error updating handle_text_input function: {e}")
        return False

def cleanup_state_on_startup():
    """Add code to clean up stale user states on bot startup"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Find the startup section
        if "async def run_bot():" in content:
            # Add state cleanup code after database connection
            startup_code = """
    # Clear any stale user_states
    user_states.clear()
    print(f"Cleared user_states at startup: {datetime.now()}")
    
"""
            # Find position after where database connection is made
            match = re.search(r'async def run_bot\(\):[^}]+?initialize_database\(\)', content, re.DOTALL)
            if match:
                pos = match.end()
                new_content = content[:pos] + startup_code + content[pos:]
                
                with open(USER_BOT_FILE, 'w') as f:
                    f.write(new_content)
                
                logger.info("Added state cleanup on startup")
                return True
            else:
                logger.warning("Could not find database initialization in run_bot function")
                return False
        else:
            logger.warning("Could not find run_bot function")
            return False
    
    except Exception as e:
        logger.error(f"Error adding state cleanup on startup: {e}")
        return False

def add_scheduled_state_cleanup():
    """Add scheduled task to cleanup stale states"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Define the cleanup task
        cleanup_task = """
async def cleanup_stale_states():
    '''Periodically clean up stale user states'''
    while True:
        try:
            # Wait for 5 minutes
            await asyncio.sleep(5 * 60)
            
            # Check all states
            current_time = time.time()
            stale_users = []
            
            for user_id, state in user_states.items():
                # If the state has a timestamp and it's older than 30 minutes, consider it stale
                if "timestamp" in state and current_time - state["timestamp"] > 30 * 60:
                    stale_users.append(user_id)
                # Or if it's just been there too long (1 hour) without a timestamp
                elif current_time - user_states.get("_created_at", current_time) > 60 * 60:
                    stale_users.append(user_id)
            
            # Clear stale states
            for user_id in stale_users:
                clear_user_state(user_id, "cleanup_stale")
                print(f"Cleared stale state for user {user_id}")
            
            if stale_users:
                print(f"Cleaned up {len(stale_users)} stale user states")
            
        except Exception as e:
            print(f"Error in state cleanup task: {e}")
"""
        
        # Find a good insertion point - right before the run_bot function
        match = re.search(r'async def run_bot\(\):', content)
        if match:
            pos = match.start()
            new_content = content[:pos] + cleanup_task + "\n\n" + content[pos:]
            
            # Add the task to the task list in run_bot
            task_added_content = new_content.replace(
                "    # Start background tasks",
                "    # Start background tasks\n    asyncio.create_task(cleanup_stale_states())"
            )
            
            with open(USER_BOT_FILE, 'w') as f:
                f.write(task_added_content)
            
            logger.info("Added scheduled state cleanup task")
            return True
        else:
            logger.warning("Could not find run_bot function for adding cleanup task")
            return False
    
    except Exception as e:
        logger.error(f"Error adding scheduled state cleanup: {e}")
        return False

def improve_otp_handler():
    """Improve the OTP handler to be more resilient"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Add direct DB check at the beginning of the function
        otp_handler_improvements = """
    # First check for case where user_states might be lost but DB record exists
    if not is_waiting_for_code and user_data and "phone_auth" in user_data:
        # This is a recovery path - user_states may have been lost but DB has the state
        print(f"Potential state recovery for user {user_id} - found in DB but not in memory")
        auth_data = user_data["phone_auth"]
        if auth_data.get("step") == "waiting_for_code":
            is_waiting_for_code = True
            phone_number = auth_data.get("phone_number")
            phone_code_hash = auth_data.get("phone_code_hash")
            
            # Restore the in-memory state
            set_user_state(user_id, {
                "action": "phone_auth",
                "phone_number": phone_number,
                "phone_code_hash": phone_code_hash,
                "step": "waiting_for_code",
                "timestamp": time.time()
            })
            print(f"Recovered state for user {user_id}, phone {phone_number}")
"""
        
        # Find the OTP handler check section
        match = re.search(r'if not is_waiting_for_code:', content)
        if match:
            pos = match.start()
            # Find the right position by going backwards to find the previous statement
            prev_statement = content.rfind("print(f\"Found waiting state in database", 0, pos)
            if prev_statement > 0:
                end_prev = content.find("\n", prev_statement) + 1
                new_content = content[:end_prev] + otp_handler_improvements + content[end_prev:]
                
                with open(USER_BOT_FILE, 'w') as f:
                    f.write(new_content)
                
                logger.info("Improved OTP handler with state recovery logic")
                return True
            else:
                logger.warning("Could not find previous statement before 'if not is_waiting_for_code'")
                return False
        else:
            logger.warning("Could not find 'if not is_waiting_for_code' section")
            return False
    
    except Exception as e:
        logger.error(f"Error improving OTP handler: {e}")
        return False

def add_timestamp_to_states():
    """Add timestamp to user states to track how old they are"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Replace set_user_state function to add timestamp
        if "def set_user_state(user_id, state_dict):" in content:
            old_func = """def set_user_state(user_id, state_dict):
    '''Set user state with logging'''
    old_state = user_states.get(user_id, {})
    user_states[user_id] = state_dict
    log_state_change(user_id, "set_state", old_state, state_dict, "set")"""
            
            new_func = """def set_user_state(user_id, state_dict):
    '''Set user state with logging'''
    old_state = user_states.get(user_id, {})
    # Add timestamp if not present
    if "timestamp" not in state_dict:
        state_dict["timestamp"] = time.time()
    user_states[user_id] = state_dict
    log_state_change(user_id, "set_state", old_state, state_dict, "set")"""
            
            modified_content = content.replace(old_func, new_func)
            
            with open(USER_BOT_FILE, 'w') as f:
                f.write(modified_content)
            
            logger.info("Added timestamp to user states")
            return True
        else:
            logger.warning("Could not find set_user_state function")
            return False
    
    except Exception as e:
        logger.error(f"Error adding timestamp to states: {e}")
        return False

def fix_state_management():
    """Apply all fixes to the user_bot.py file"""
    if not create_backup():
        logger.error("Backup failed, aborting")
        return False
    
    success = True
    success = success and add_state_debug_logging()
    success = success and update_generate_session_function()
    success = success and update_otp_handler()
    success = success and update_handle_text_input()
    success = success and cleanup_state_on_startup()
    success = success and add_scheduled_state_cleanup()
    success = success and improve_otp_handler()
    success = success and add_timestamp_to_states()
    
    if success:
        logger.info("Successfully applied all state management fixes")
    else:
        logger.error("Some fixes failed to apply")
    
    return success

if __name__ == "__main__":
    fix_state_management() 