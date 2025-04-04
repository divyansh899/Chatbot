#!/usr/bin/env python3

import re
import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/session_fix.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("SessionFixer")

def fix_user_bot_file():
    """Fix the session generation flow in user_bot.py"""
    user_bot_path = "user_bot.py"
    backup_path = "user_bot.py.before_fix"
    
    # Create backup
    logger.info(f"Creating backup of {user_bot_path} to {backup_path}")
    with open(user_bot_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_path, 'w') as f:
        f.write(original_content)
    
    # Fix 1: Add improved OTP code handler that works with direct messages
    improved_text_handler = """
    # Added enhanced OTP handling
    @user_bot.on_message(filters.regex(r'^\\d{5,6}$') & filters.private)
    async def handle_otp_code(client, message):
        \"\"\"Handle direct OTP code messages\"\"\"
        user_id = message.from_user.id
        
        # Load user data
        user_data = users.find_one({"user_id": user_id})
        
        # Get OTP code from message
        code = message.text.strip()
        
        # Log for debugging
        print(f"Received potential OTP code: {code} from user {user_id}")
        
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
                    f"🔐 Two-factor authentication required for {phone_number}\n\n"
                    f"Please reply with your 2FA password.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
                    ])
                )
                return
            
            # Successfully signed in, save the session string
            session_string = StringSession.save(telethon_client.session)
            print(f"Successfully generated session string for {phone_number}: {session_string[:15]}...")
            
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
                f"✅ **Session generated successfully**\n\n"
                f"Number: {phone_number}\n"
                f"Session string (first 15 chars): ```{session_string[:15]}...```\n\n"
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
                f"❌ **Error generating session**\n\n"
                f"Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"generate_session_{phone_number}")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ])
            )
    """
    
    # Fix 2: Improve the generate_session function to provide clearer instructions
    new_instructions = """
            f"📱 Authentication code sent to {phone_number}\\n\\n"
            f"Please enter the authentication code you received.\\n\\n"
            f"You can just type the 5-6 digit code directly as a message.\\n"
            f"For example: 12345"
    """
    
    # Apply fixes by replacing content
    modified_content = original_content
    
    # Add the new handler before the handle_text_input function
    text_handler_pattern = r'@user_bot\.on_message\(filters\.text & filters\.private\)\nasync def handle_text_input\(client, message\):'
    if re.search(text_handler_pattern, modified_content):
        modified_content = re.sub(text_handler_pattern, improved_text_handler + "\n\n" + text_handler_pattern, modified_content)
        logger.info("Added enhanced OTP code handler")
    else:
        logger.error("Could not find text handler to modify")
    
    # Update the authentication message in generate_session
    auth_message_pattern = r'f"📱 Authentication code sent to \{phone_number\}\\n\\n"[^}]+?][ \n]+'
    if re.search(auth_message_pattern, modified_content):
        modified_content = re.sub(auth_message_pattern, 
                                 f"""            f"📱 Authentication code sent to {{phone_number}}\\n\\n"
            f"Please enter the authentication code you received.\\n\\n"
            f"You can just type the 5-6 digit code directly as a message.\\n"
            f"For example: 12345",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
            ])
        )
        
        """, modified_content)
        logger.info("Updated authentication instruction message")
    else:
        logger.error("Could not find authentication message to modify")
    
    # Save the modified file
    with open(user_bot_path, 'w') as f:
        f.write(modified_content)
    
    logger.info(f"Applied fixes to {user_bot_path}")

if __name__ == "__main__":
    fix_user_bot_file() 