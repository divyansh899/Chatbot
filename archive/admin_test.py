import asyncio
import logging
import os
import pymongo
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.getenv("API_ID", "28128290")
API_HASH = os.getenv("API_HASH", "d0a9bd403194e06a8740c7ee0219a01e")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6839389825:AAEZECaArzOEAF3vVXh_Z3NWJF0VYm3NxNk")
ADMIN_ID = os.getenv("ADMIN_ID", "7536665814")
ADMIN_USER_IDS = [ADMIN_ID]  # List of admin IDs

# Initialize Pyrogram Client
user_bot = Client("admin_test_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Connect to MongoDB
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["telegram_bot_db"]
users = db["users"]
numbers_inventory = db["numbers_inventory"]
orders = db["orders"]
payment_screenshots = db["payment_screenshots"]

# Helper functions
def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

# Command handlers
@user_bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        f"👋 Hello, {message.from_user.first_name}!\n\n"
        f"This is a test bot for the admin panel functionality.\n"
        f"Send /admin to access the admin panel."
    )

@user_bot.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    """Admin panel with management options"""
    print(f"ADMIN PANEL CALLED by user ID: {message.from_user.id}")
    print(f"ADMIN_ID: {ADMIN_ID}")
    print(f"ADMIN_USER_IDS: {ADMIN_USER_IDS}")
    
    if str(message.from_user.id) not in ADMIN_USER_IDS and str(message.from_user.id) != ADMIN_ID:
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

@user_bot.on_callback_query(filters.regex("^admin_manage_numbers$"))
async def admin_manage_numbers(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    number_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Single Number", callback_data="admin_add_number"),
            InlineKeyboardButton("📋 Bulk Add Numbers", callback_data="admin_bulk_add")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await callback_query.message.edit_text(
        "📱 **Number Management**\n\n"
        "Manage your virtual number inventory:",
        reply_markup=number_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await admin_panel(client, callback_query.message)

# Main function
async def main():
    await user_bot.start()
    print("Bot started successfully!")
    
    # Keep the bot running until it's stopped manually
    await idle()
    
    await user_bot.stop()

if __name__ == "__main__":
    # Run the bot
    print("Starting the bot...")
    asyncio.run(main()) 