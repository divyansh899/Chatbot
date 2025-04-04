import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Configuration
API_ID = 28128290
API_HASH = "d0a9bd403194e06a8740c7ee0219a01e"
BOT_TOKEN = "6839389825:AAEZECaArzOEAF3vVXh_Z3NWJF0VYm3NxNk"
ADMIN_ID = "7536665814"  # Your Telegram user ID as string
ADMIN_USER_IDS = [ADMIN_ID]  # List of admin IDs

# Initialize Pyrogram Client
user_bot = Client("admin_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Helper functions
def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

async def safe_edit_message(message, text, reply_markup=None):
    """Safely edit a message, handling errors"""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        print(f"Error editing message: {e}")

# Command handlers
@user_bot.on_message(filters.command("start"))
async def start(client, message):
    """Start command handler"""
    user_id = message.from_user.id
    
    welcome_text = (
        f"👋 Welcome to Admin Bot Test!\n\n"
        f"Use /admin to access the admin panel if you're authorized."
    )
    
    await message.reply_text(welcome_text)

# Debug command
@user_bot.on_message(filters.command(["*"]))
async def log_all_commands(client, message):
    """Log all commands for debugging"""
    print(f"COMMAND RECEIVED: {message.text} from user ID: {message.from_user.id}")

# Admin panel
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
        [
            InlineKeyboardButton("📱 View Inventory", callback_data="admin_view_numbers"),
            InlineKeyboardButton("🔍 Search Numbers", callback_data="admin_search_numbers")
        ],
        [
            InlineKeyboardButton("❌ Clear Inventory", callback_data="admin_clear_inventory"),
            InlineKeyboardButton("📊 Inventory Stats", callback_data="admin_inventory_stats")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📱 **Number Management**\n\n"
        "Manage your virtual number inventory:",
        reply_markup=number_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_session_management$"))
async def admin_session_management(client, callback_query):
    """Show session management menu"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton("📥 Import Session", callback_data="admin_import_session")],
        [InlineKeyboardButton("📤 Export Session", callback_data="admin_export_session")],
        [InlineKeyboardButton("🔑 Generate Session", callback_data="admin_generate_session")],
        [InlineKeyboardButton("❌ Delete Session", callback_data="admin_delete_session")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "🔑 Session Management\n\n"
        "Please select an option:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
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

# Run the bot
if __name__ == "__main__":
    print(f"Starting bot with admin ID: {ADMIN_ID}")
    user_bot.run() 