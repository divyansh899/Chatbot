#!/usr/bin/env python3

import logging
import os
import sys

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/session_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("OTPDebugger")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import necessary modules and add patches
from pymongo import MongoClient
import re

# Connect to MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')

logger.info(f"Connecting to MongoDB at {MONGO_URI}")
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Get collections
users = db.users
numbers_inventory = db.numbers_inventory
user_states = {}  # In-memory state storage

# Add debug function to monkey patch into the relevant parts of the bot
def patch_text_handler():
    """Patch the text handler in the user_bot.py file to add debug logging"""
    from pyrogram import Client
    
    original_process_message = Client.process_messages
    
    def debug_process_messages(self, messages, *args, **kwargs):
        logger.debug(f"Processing messages: {messages}")
        return original_process_message(self, messages, *args, **kwargs)
    
    Client.process_messages = debug_process_messages
    logger.info("Patched Client.process_messages for debugging")

def check_user_states():
    """Check all user states related to session generation"""
    logger.info("Checking user states in memory...")
    for user_id, state in user_states.items():
        logger.info(f"User {user_id} state: {state}")
    
    logger.info("Checking user states in database...")
    for user in users.find({"phone_auth": {"$exists": True}}):
        logger.info(f"User {user['user_id']} DB state: {user.get('phone_auth')}")

def main():
    """Main debugging function"""
    logger.info("Starting OTP debug script")
    
    # Check existing user states
    check_user_states()
    
    # Check session files
    sessions_dir = "sessions"
    if os.path.exists(sessions_dir):
        logger.info(f"Checking session files in {sessions_dir}")
        for filename in os.listdir(sessions_dir):
            if filename.endswith(".session"):
                logger.info(f"Found session file: {filename}")
                # Check if this session has a corresponding entry in the database
                phone = filename.replace(".session", "")
                number = numbers_inventory.find_one({"phone_number": phone})
                if number:
                    logger.info(f"Number found in database: {phone}, authorized: {number.get('is_authorized', False)}")
                else:
                    logger.warning(f"No database entry for session file: {phone}")
    
    # Enable the debug patch
    logger.info("To enable debug patches, run this after importing user_bot:")
    logger.info("from debug_session_issue import patch_text_handler; patch_text_handler()")
    
    logger.info("Debug script completed")

if __name__ == "__main__":
    main() 