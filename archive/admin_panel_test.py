import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables if available
try:
    load_dotenv()
except ImportError:
    pass

# Configuration - hardcoded for testing
API_ID = 28128290
API_HASH = "d0a9bd403194e06a8740c7ee0219a01e"
BOT_TOKEN = "6839389825:AAEZECaArzOEAF3vVXh_Z3NWJF0VYm3NxNk"
ADMIN_ID = "7536665814"  # Your Telegram user ID
ADMIN_USER_IDS = [ADMIN_ID]  # List of admin IDs

# Initialize Pyrogram Client
app = Client("admin_panel_test", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Helper functions
def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

# Command handlers
@app.on_message(filters.command("start"))
async def start(client, message):
    print(f"Received start command from {message.from_user.id}")
    await message.reply_text(
        f"👋 Hello, {message.from_user.first_name}!\n\n"
        f"This is a test bot for the admin panel functionality.\n"
        f"Send /admin to access the admin panel."
    )

@app.on_message(filters.command("admin"))
async def admin_panel(client, message):
    """Admin panel with management options"""
    print(f"ADMIN PANEL CALLED by user ID: {message.from_user.id}")
    print(f"ADMIN_ID: {ADMIN_ID}")
    print(f"ADMIN_USER_IDS: {ADMIN_USER_IDS}")
    
    if str(message.from_user.id) != ADMIN_ID and str(message.from_user.id) not in ADMIN_USER_IDS:
        print(f"User {message.from_user.id} is not authorized as admin.")
        await message.reply_text("⛔️ You are not authorized to use this command.")
        return

    print(f"User {message.from_user.id} authenticated as admin, showing admin panel.")
    buttons = [
        [InlineKeyboardButton("📱 Manage Numbers", callback_data="admin_manage_numbers")],
        [InlineKeyboardButton("📦 Manage Orders", callback_data="admin_manage_orders")],
        [InlineKeyboardButton("💰 Revenue", callback_data="admin_revenue")],
        [InlineKeyboardButton("🔑 Session Management", callback_data="admin_session_management")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply_text(
        "👋 Welcome to the Admin Panel!\n\n"
        "Please select an option:",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex("^admin_"))
async def handle_admin_buttons(client, callback_query):
    """Handle all admin panel button callbacks"""
    print(f"CALLBACK RECEIVED: {callback_query.data} from user {callback_query.from_user.id}")
    
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return
    
    await callback_query.answer("Button clicked!")
    
    if callback_query.data == "admin_manage_numbers":
        await callback_query.message.edit_text(
            "📱 Number Management\n\nThis is a test of the admin panel functionality.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )
    elif callback_query.data == "admin_back":
        # Go back to main admin panel
        buttons = [
            [InlineKeyboardButton("📱 Manage Numbers", callback_data="admin_manage_numbers")],
            [InlineKeyboardButton("📦 Manage Orders", callback_data="admin_manage_orders")],
            [InlineKeyboardButton("💰 Revenue", callback_data="admin_revenue")],
            [InlineKeyboardButton("🔑 Session Management", callback_data="admin_session_management")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await callback_query.message.edit_text(
            "👋 Welcome to the Admin Panel!\n\n"
            "Please select an option:",
            reply_markup=keyboard
        )
    else:
        # Generic response for other buttons
        await callback_query.message.edit_text(
            f"You clicked: {callback_query.data}\n\nThis is a test of the admin panel functionality.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

# Start the bot
if __name__ == "__main__":
    print("Starting admin panel test bot...")
    app.run() 