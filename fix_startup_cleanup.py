#!/usr/bin/env python3

"""
This script adds state cleanup code to the bot startup process.
It fixes the issue where stale states can prevent new session generations.
"""

import os
import re
import sys
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/startup_fix.log", 'w'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("StartupFixTool")

# Constants
USER_BOT_FILE = "user_bot.py"

def cleanup_state_on_startup():
    """Add code to clean up stale user states on bot startup"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Find the run_bot function
        match = re.search(r'async def run_bot\(\):', content)
        if not match:
            logger.error("Could not find run_bot function")
            return False
        
        # Find a good insertion point after connecting to database
        # First locate the run_bot function
        run_bot_start = match.start()
        run_bot_end = content.find("if __name__ == \"__main__\":", run_bot_start)
        if run_bot_end == -1:
            run_bot_end = len(content)
        
        run_bot_code = content[run_bot_start:run_bot_end]
        
        # Find a suitable point after database connection
        insertion_points = [
            "# Initialize the database",
            "initialize_database()",
            "mongodb_client =",
            "# Connect to MongoDB"
        ]
        
        insertion_pos = -1
        for point in insertion_points:
            pos = run_bot_code.find(point)
            if pos != -1:
                # Find the end of this line
                line_end = run_bot_code.find("\n", pos)
                if line_end != -1:
                    insertion_pos = run_bot_start + line_end + 1
                    break
        
        if insertion_pos == -1:
            logger.error("Could not find suitable insertion point in run_bot function")
            return False
        
        # Add state cleanup code
        cleanup_code = """
    # Clear any stale user_states at startup
    user_states.clear()
    print(f"Cleared user_states at startup: {datetime.now()}")
    
"""
        
        new_content = content[:insertion_pos] + cleanup_code + content[insertion_pos:]
        
        with open(USER_BOT_FILE, 'w') as f:
            f.write(new_content)
        
        logger.info("Added state cleanup on startup")
        return True
    
    except Exception as e:
        logger.error(f"Error adding state cleanup on startup: {e}")
        return False

def add_scheduled_cleanup_task():
    """Add scheduled task to cleanup stale states"""
    try:
        with open(USER_BOT_FILE, 'r') as f:
            content = f.read()
        
        # Check if cleanup function already exists
        if "async def cleanup_stale_states():" in content:
            logger.info("Cleanup task already exists")
            return True
        
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
            
            for user_id, state in list(user_states.items()):
                # If the state has a timestamp and it's older than 30 minutes, consider it stale
                if "timestamp" in state and current_time - state["timestamp"] > 30 * 60:
                    stale_users.append(user_id)
                # Or if it's just been there too long (1 hour) without a timestamp
                elif current_time - state.get("_created_at", current_time) > 60 * 60:
                    stale_users.append(user_id)
            
            # Clear stale states
            for user_id in stale_users:
                if user_id in user_states:
                    old_state = user_states[user_id]
                    del user_states[user_id]
                    print(f"Cleared stale state for user {user_id}: {old_state}")
            
            if stale_users:
                print(f"Cleaned up {len(stale_users)} stale user states")
            
        except Exception as e:
            print(f"Error in state cleanup task: {e}")
"""
        
        # Find a good insertion point - right before the run_bot function
        match = re.search(r'async def run_bot\(\):', content)
        if not match:
            logger.error("Could not find run_bot function")
            return False
            
        pos = match.start()
        new_content = content[:pos] + cleanup_task + "\n\n" + content[pos:]
        
        # Add the task to the background tasks in run_bot
        # Find background tasks section
        background_tasks_patterns = [
            "    # Start background tasks",
            "    # Start the background tasks",
            "    asyncio.create_task"
        ]
        
        task_added = False
        for pattern in background_tasks_patterns:
            if pattern in new_content:
                task_added_content = new_content.replace(
                    pattern,
                    f"{pattern}\n    asyncio.create_task(cleanup_stale_states())"
                )
                task_added = True
                break
        
        if not task_added:
            # If we can't find a good insertion point, add it near the end of run_bot
            match = re.search(r'async def run_bot\(\):', new_content)
            run_bot_start = match.start()
            
            # Find the last line in run_bot function
            run_bot_end = new_content.find("if __name__ == \"__main__\":", run_bot_start)
            if run_bot_end == -1:
                run_bot_end = len(new_content)
            
            # Find a point before the end of the function
            last_line = new_content.rfind("\n", run_bot_start, run_bot_end)
            if last_line != -1:
                task_added_content = (
                    new_content[:last_line] + 
                    "\n    # Start state cleanup task\n    asyncio.create_task(cleanup_stale_states())" +
                    new_content[last_line:]
                )
                task_added = True
            else:
                logger.error("Could not find suitable location to add cleanup task")
                return False
        
        if task_added:
            with open(USER_BOT_FILE, 'w') as f:
                f.write(task_added_content)
            
            logger.info("Added scheduled state cleanup task")
            return True
        else:
            logger.error("Failed to add cleanup task")
            return False
    
    except Exception as e:
        logger.error(f"Error adding scheduled state cleanup: {e}")
        return False

if __name__ == "__main__":
    success = cleanup_state_on_startup()
    if success:
        success = add_scheduled_cleanup_task()
    
    if success:
        logger.info("Successfully applied all startup cleanup fixes")
    else:
        logger.error("Some fixes failed to apply") 