#!/usr/bin/env python3

"""
This script adds a dedicated OTP code handler to the user_bot.py file.
This fixes the issue where OTP codes entered as direct messages are not processed.
"""

import os
import logging
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to the user_bot.py file
USER_BOT_FILE = "user_bot.py"
BACKUP_FILE = f"{USER_BOT_FILE}.backup_otp_fix"

# The OTP handler code to be added
OTP_HANDLER = """
# Direct OTP Code Handler
@user_bot.on_message(filters.regex(r'^\\d{5,6}$') & filters.private)
async def handle_otp_code(client, message):
    \"\"\"Handle direct OTP code messages\"\"\"
    user_id = message.from_user.id
    print(f"Received potential OTP code from user {user_id}: {message.text}")
    
    # Load user data
    user_data = users.find_one({"user_id": user_id})
    
    # Get OTP code from message
    code = message.text.strip()
    
    # Check if the user is waiting for an OTP code
    is_waiting_for_code = False
    phone_number = None
    phone_code_hash = None
    
    # Check in-memory state first
    if user_id in user_states and user_states[user_id].get("action") == "phone_auth":
        if user_states[user_id].get("step") == "waiting_for_code":
            is_waiting_for_code = True
            phone_number = user_states[user_id].get("phone_number")
            phone_code_hash = user_states[user_id].get("phone_code_hash")
            print(f"Found waiting state in memory for user {user_id}, phone {phone_number}")
    
    # Then check database
    elif user_data and "phone_auth" in user_data and user_data["phone_auth"].get("step") == "waiting_for_code":
        is_waiting_for_code = True
        phone_number = user_data["phone_auth"]["phone_number"]
        phone_code_hash = user_data["phone_auth"]["phone_code_hash"]
        print(f"Found waiting state in database for user {user_id}, phone {phone_number}")
    
    if not is_waiting_for_code:
        # Not waiting for code, ignore
        print(f"User {user_id} sent code but not waiting for OTP")
        return
    
    print(f"Processing OTP code {code} for phone {phone_number}")
    
    # Send status message
    status_message = await message.reply_text(
        f"🔄 Signing in with code {code} for {phone_number}...\n"
        f"Please wait."
    )
    
    try:
        # Create client with same session
        session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
        telethon_client = TelegramClient(session_file, API_ID, API_HASH)
        await telethon_client.connect()
        
        # Sign in with the code
        try:
            await telethon_client.sign_in(
                phone=phone_number,
                code=code,
                phone_code_hash=phone_code_hash
            )
        except SessionPasswordNeededError:
            # Need 2FA password
            users.update_one(
                {"user_id": user_id},
                {"$set": {"phone_auth.step": "waiting_for_2fa"}},
                upsert=True
            )
            
            # Also update user_states
            if user_id in user_states:
                user_states[user_id]["step"] = "waiting_for_2fa"
            else:
                user_states[user_id] = {
                    "action": "phone_auth",
                    "phone_number": phone_number,
                    "step": "waiting_for_2fa"
                }
            
            await telethon_client.disconnect()
            
            await status_message.edit_text(
                f"🔐 Two-factor authentication required for {phone_number}\\n\\n"
                f"Please reply with your 2FA password.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
                ])
            )
            return
        
        # Successfully signed in, save the session string
        session_string = StringSession.save(telethon_client.session)
        print(f"Generated session string for {phone_number}: {session_string[:15]}...")
        
        # Update the database with the session string
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {
                "session_string": session_string,
                "session_added_at": datetime.now(),
                "is_authorized": True,
                "needs_session": False
            }}
        )
        
        # Clear the phone_auth data
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"phone_auth": ""}}
        )
        
        # Also clear from user_states
        if user_id in user_states:
            del user_states[user_id]
        
        await telethon_client.disconnect()
        
        # Send success message
        await status_message.edit_text(
            f"✅ **Session generated successfully**\\n\\n"
            f"Number: {phone_number}\\n"
            f"Session string (first 15 chars): ```{session_string[:15]}...```\\n\\n"
            f"This session has been saved to the database and is ready to use.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        
        # Start monitoring if the number is sold
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
            sold_to_user = number_data.get("sold_to")
            success = await start_monitoring_for_otp(phone_number, sold_to_user)
            
            if success:
                # Notify the user
                try:
                    await client.send_message(
                        chat_id=sold_to_user,
                        text=f"🔔 Your virtual number {phone_number} is now active!\\n\\n"
                            f"You can use this number to sign in to Telegram.\\n"
                            f"When you request an OTP code, it will be automatically sent to you here."
                    )
                except Exception as e:
                    print(f"Error notifying user {sold_to_user}: {e}")
                
    except Exception as e:
        print(f"Error in session generation: {e}")
        await status_message.edit_text(
            f"❌ **Error generating session**\\n\\n"
            f"Error: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data=f"generate_session_{phone_number}")],
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
"""

# Updated session instruction message
UPDATED_INSTRUCTION = """
        # Ask the user to enter the code
        await status_message.edit_text(
            f"📱 Authentication code sent to {phone_number}\\n\\n"
            f"Please enter the authentication code you received.\\n\\n"
            f"You can simply type the 5-6 digit code as a message.\\n"
            f"For example: 12345",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
            ])
        )
"""

def fix_otp_handler():
    """Add the OTP handler to the user_bot.py file"""
    logger.info(f"Creating backup of {USER_BOT_FILE} to {BACKUP_FILE}")
    shutil.copy2(USER_BOT_FILE, BACKUP_FILE)
    
    # Read the file
    with open(USER_BOT_FILE, 'r') as f:
        content = f.read()
    
    # Find a good insertion point - right before the @user_bot.on_callback_query(filters.regex("^admin_generate_session$"))
    insertion_point = "@user_bot.on_callback_query(filters.regex(\"^admin_generate_session$\"))"
    if insertion_point in content:
        parts = content.split(insertion_point)
        if len(parts) == 2:
            new_content = parts[0] + OTP_HANDLER + "\n\n" + insertion_point + parts[1]
            
            # Write the modified content
            with open(USER_BOT_FILE, 'w') as f:
                f.write(new_content)
                
            logger.info(f"Added OTP handler to {USER_BOT_FILE}")
            
            # Also update the instruction message
            instruction_pattern = "f\"📱 Authentication code sent to {phone_number}\\n\\n\"\n            f\"Please reply to this message with the code you received."
            if instruction_pattern in new_content:
                updated_content = new_content.replace(
                    instruction_pattern,
                    f"f\"📱 Authentication code sent to {{phone_number}}\\n\\n\"\n            f\"Please enter the authentication code you received.\\n\\n\"\n            f\"You can simply type the 5-6 digit code as a message.\\n\"\n            f\"For example: 12345"
                )
                
                # Write the updated content
                with open(USER_BOT_FILE, 'w') as f:
                    f.write(updated_content)
                    
                logger.info("Updated instruction message")
            else:
                logger.warning("Could not find instruction message to update")
                
            return True
        else:
            logger.error("Could not split file content correctly")
            return False
    else:
        logger.error(f"Could not find insertion point: {insertion_point}")
        return False

if __name__ == "__main__":
    if fix_otp_handler():
        logger.info("OTP handler fix applied successfully!")
    else:
        logger.error("Failed to apply OTP handler fix.") 