from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Create a new client
app = Client(
    "simple_bot",
    api_id=28128290,
    api_hash="d0a9bd403194e06a8740c7ee0219a01e",
    bot_token="6839389825:AAEZECaArzOEAF3vVXh_Z3NWJF0VYm3NxNk"
)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    print(f"Received /start command from {message.from_user.id}")
    await message.reply("Hello! Send /admin to test the admin panel.")

@app.on_message(filters.command("admin"))
async def admin_command(client, message):
    print(f"Received /admin command from {message.from_user.id}")
    await message.reply("This is a test of the admin panel.")

@app.on_message(filters.command("debugadmin"))
async def debug_admin_command(client, message):
    print(f"Received /debugadmin command from {message.from_user.id}")
    
    # Create a simple admin panel with buttons
    buttons = [
        [InlineKeyboardButton("📱 Test Button 1", callback_data="test_button_1")],
        [InlineKeyboardButton("📦 Test Button 2", callback_data="test_button_2")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    
    await message.reply(
        "👋 Welcome to the Debug Admin Panel!\n\n"
        "This is a test to verify that admin buttons work.",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def handle_all_callbacks(client, callback_query):
    print(f"Received callback: {callback_query.data} from user {callback_query.from_user.id}")
    await callback_query.answer(f"Button {callback_query.data} clicked!")
    await callback_query.message.reply(f"You clicked: {callback_query.data}")

# Start the bot
print("Starting simple test bot...")
app.run() 