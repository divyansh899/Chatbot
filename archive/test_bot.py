import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get these from environment or config
API_ID = 28128290
API_HASH = "d0a9bd403194e06a8740c7ee0219a01e"
BOT_TOKEN = "6839389825:AAEZECaArzOEAF3vVXh_Z3NWJF0VYm3NxNk"
ADMIN_ID = "7536665814"

# Create the client
app = Client("test_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    logger.info(f"Received start command from {message.from_user.id}")
    await message.reply_text("Bot is running. Use /admin to test the admin panel.")

@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    logger.info(f"Received admin command from {message.from_user.id}")
    
    if str(message.from_user.id) != ADMIN_ID:
        await message.reply_text("⛔️ You are not authorized to use this command.")
        return

    buttons = [
        [InlineKeyboardButton("📱 Test Button", callback_data="test_button")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply_text(
        "👋 Welcome to the Admin Panel Test!\n\n"
        "This is a test to verify that admin commands are working.",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex("^test_button$"))
async def test_button_callback(client, callback_query):
    logger.info(f"Received test button callback from {callback_query.from_user.id}")
    await callback_query.answer("This is a test button!")
    await callback_query.message.edit_text(
        "Button callback received successfully!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Test Again", callback_data="test_button")]
        ])
    )

# Start the bot
if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run() 