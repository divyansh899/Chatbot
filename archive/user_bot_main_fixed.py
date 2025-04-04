#!/usr/bin/env python
# -*- coding: utf-8 -*-

#############################################################
# TELEGRAM BOT MAIN CODE - DO NOT MODIFY DIRECTLY           #
# -------------------------------------------------------   #
# This is the main, stable version of the Telegram bot.     #
# Any changes should be tested in a development branch      #
# before being incorporated into this main version.         #
#                                                           #
# Last updated: April 2, 2025                               #
# Features:                                                 #
# - Telegram and WhatsApp number management                 #
# - OTP forwarding and monitoring                           #
# - Session management with import/export                   #
# - Admin panel with user management                        #
# - Payment processing                                      #
#############################################################

import asyncio
import json
import logging
import os
import random
import re
import requests
import shutil
import string
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import uuid
import glob
import time
import pymongo
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import MessageNotModified
from telethon.sync import TelegramClient
from telethon import events
from telethon.sessions.string import StringSession
from bson.objectid import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot Credentials ---
API_ID = 25733253
API_HASH = "eabb8d10c13a3a7f63b2b832be8336d6"
BOT_TOKEN = "7011527407:AAEPw2k9NYJbQNL6qpGJWrcmokLp7nq3D2w"
ADMIN_ID = "7536665814"  # Your Telegram user ID as string
ADMIN_USERNAME = "@Mr_Griffiin"  # Your Telegram username

UPI_ID = "sunnysing2632-3@okaxis"
BINANCE_ID = "1018484211"

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client["telegram_bot_new_fresh"]  # Using a new database name to avoid lock conflicts
users = db["users"]
orders = db["orders"]
pending_approvals = db["pending_approvals"]
numbers_inventory = db["numbers_inventory"]

# Initialize Pyrogram Client
user_bot = Client(
    "number_selling_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Session management ---
# Dictionary to store active telethon clients
active_telethon_clients = {}
# Directory for storing session files
SESSIONS_DIR = "new_fresh_sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# --- Global Variables ---
telethon_user_data = {}  # Store temporary data for Telethon session generation
recent_otps = {}  # Store recent OTPs to prevent duplicates

# --- Helper Functions for OTP Management ---
async def get_telethon_client_for_number(phone_number, session_string=None):
    """
    Get or create a Telethon client for the given phone number.
    Using in-memory sessions to avoid database locks.
    
    Args:
        phone_number: The phone number to get a client for
        session_string: Optional session string to use
        
    Returns:
        TelegramClient: The client
    """
    try:
        # Check if we already have an active client for this number
        if phone_number in active_telethon_clients:
            print(f"Returning existing client for {phone_number}")
            return active_telethon_clients[phone_number]
            
        print(f"Creating new Telethon client for {phone_number}")
        
        # Create a new client using the session string or in-memory session
        if session_string:
            # Use the provided session string
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        else:
            # Always use in-memory session to avoid database locks
            memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        
        # Connect the client but don't start it yet
        await client.connect()
        
        # Check if the client is authorized
        is_authorized = await client.is_user_authorized()
        print(f"Client for {phone_number} authorized: {is_authorized}")
        
        return client
        
    except Exception as e:
        print(f"Error getting Telethon client for {phone_number}: {e}")
        logger.error(f"Error getting Telethon client for {phone_number}: {e}")
        raise

async def start_monitoring_for_otp(phone_number, user_id):
    """
    Start monitoring a phone number for Telegram OTP codes.
    
    Args:
        phone_number: The phone number to monitor
        user_id: The user to send OTP codes to
    
    Returns:
        bool: True if monitoring started successfully, False otherwise
    """
    try:
        print(f"Starting monitoring for OTP codes for {phone_number}, forwarding to user {user_id}")
        
        # Initialize recent OTPs tracker for this number
        recent_otps[phone_number] = set()
        
        # Get session string from database
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        if not number_data:
            print(f"No number found in database for {phone_number}")
            return False
            
        session_string = number_data.get("session_string")
        if not session_string:
            print(f"No session string found for {phone_number}")
            return False
            
        # Store the owner ID for later use in message forwarding
        sold_to_user = number_data.get("sold_to")
        print(f"Number {phone_number} is sold to user: {sold_to_user}")
        
        # Create and start client
        client = await get_telethon_client_for_number(phone_number, session_string)
        
        # Ensure client is logged in
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            print(f"Client for {phone_number} is not authorized")
            await client.disconnect()
            return False
        
        # Store the client in the active clients dictionary
        active_telethon_clients[phone_number] = client
        
        # Update database to indicate monitoring is active
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {"otp_monitoring_active": True}}
        )
        
        # Set up event handler for new messages
        @client.on(events.NewMessage())
        async def handle_new_message(event):
            try:
                message_text = event.message.message
                print(f"New message received on {phone_number}: {message_text}")
                
                # Check if the message is from Telegram or contains OTP code
                is_otp = False
                otp_code = None
                
                # Check if message is from Telegram
                if event.message.from_id and hasattr(event.message.from_id, 'user_id'):
                    sender_id = event.message.from_id.user_id
                    if sender_id == 777000:  # Telegram's official user ID
                        is_otp = True
                
                # Look for OTP patterns in the message
                otp_patterns = [
                    r'Telegram code (?:is|:) (\d{5})',
                    r'Your login code:? (\d{5})',
                    r'Your code:? (\d{5})',
                    r'verification code:? (\d{5})',
                    r'(\d{5}) is your Telegram code',
                    r'Login code:? (\d{5})',
                    r'[^\d](\d{5})[^\d]',
                ]
                
                for pattern in otp_patterns:
                    match = re.search(pattern, message_text)
                    if match:
                        otp_code = match.group(1)
                        is_otp = True
                        break
                
                if is_otp:
                    print(f"OTP detected: {otp_code if otp_code else 'Pattern matched but no code extracted'}")
                    
                    # Check if this is a duplicate OTP
                    if otp_code:
                        otp_key = f"{otp_code}_{int(datetime.now().timestamp()) // 300}"  # Group by 5-min window
                        
                        # Skip if we've already sent this OTP recently
                        if otp_key in recent_otps.get(phone_number, set()):
                            print(f"Skipping duplicate OTP {otp_code} for {phone_number}")
                            return
                        
                        # Add to recent OTPs
                        if phone_number not in recent_otps:
                            recent_otps[phone_number] = set()
                        recent_otps[phone_number].add(otp_key)
                        
                        # Cleanup old OTPs (keep only last 10)
                        if len(recent_otps[phone_number]) > 10:
                            recent_otps[phone_number] = set(list(recent_otps[phone_number])[-10:])
                    
                    # Format the message to send to the user
                    formatted_message = f"📲 **OTP Code Received**\n\n"
                    
                    if otp_code:
                        formatted_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        formatted_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    formatted_message += f"📱 Phone Number: `{phone_number}`\n"
                    formatted_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    formatted_message += "Enter this code in the Telegram app to complete the login."
                    
                    # Add verification completion button
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Verification Complete", callback_data=f"verify_success_{phone_number}")],
                        [InlineKeyboardButton("🔄 Get New OTP", callback_data=f"new_otp_{phone_number}")],
                        [InlineKeyboardButton("ℹ️ Help", callback_data="otp_help")]
                    ])
                    
                    # Get latest owner information from database
                    current_data = numbers_inventory.find_one({"phone_number": phone_number})
                    current_owner = current_data.get("sold_to") if current_data else None
                    
                    # 1. Send the OTP to the user who purchased the number (if sold)
                    if current_owner:
                        try:
                            await user_bot.send_message(
                                chat_id=current_owner,
                                text=formatted_message,
                                reply_markup=reply_markup
                            )
                            print(f"OTP forwarded to owner {current_owner} for number {phone_number}")
                        except Exception as e:
                            print(f"Failed to send OTP to owner {current_owner}: {e}")
                    
                    # 2. Always send the OTP to the admin
                    admin_message = f"📲 **OTP Forwarded**\n\n"
                    if otp_code:
                        admin_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        admin_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    admin_message += f"📱 Number: `{phone_number}`\n"
                    if current_owner:
                        admin_message += f"👤 Sold to User ID: `{current_owner}`\n"
                    else:
                        admin_message += f"👤 Not sold yet\n"
                    admin_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                    
                    try:
                        await user_bot.send_message(
                            chat_id=ADMIN_ID,
                            text=admin_message
                        )
                        print(f"OTP also forwarded to admin for monitoring")
                    except Exception as e:
                        print(f"Failed to send OTP to admin: {e}")
            except Exception as e:
                print(f"Error handling message in OTP monitor: {e}")
                logger.error(f"Error handling message in OTP monitor: {e}")
        
        # Start the client properly
        print(f"Starting OTP monitoring for {phone_number}...")
        await client.start()
        print(f"✅ Successfully started OTP monitoring for {phone_number}")
        
        return True
        
    except Exception as e:
        print(f"Error starting OTP monitoring: {e}")
        logger.error(f"Error starting OTP monitoring: {e}")
        return False

# --- Helper Functions ---
def initialize_database():
    """Initialize database indexes"""
    try:
        db.pending_approvals.create_index([("user_id", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("admin_action", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("timestamp", pymongo.DESCENDING)])
        print("Database indexes created")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def safe_edit_message(message, text, reply_markup=None):
    """Safely edit message with error handling."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"Error editing message: {e}")

def button_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
        [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
        [InlineKeyboardButton("💳 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="support")]
    ])

def get_otp_from_session(phone_number):
    """Monitor session files for new OTPs and extract phone number"""
    session_path = f"sessions/{phone_number}.session"
    
    if not os.path.exists(session_path):
        return None, None
    
    try:
        with open(session_path, 'r') as f:
            content = f.read()
        
        # Extract phone number
        phone_match = re.search(r'phone_number\s*=\s*([\+\d]+)', content)
        phone_number = phone_match.group(1) if phone_match else None
        
        # Extract OTP
        otp_match = re.search(r'(\b\d{5}\b|\b\d{6}\b)', content)
        otp = otp_match.group(1) if otp_match else None
        
        return phone_number, otp
        
    except Exception as e:
        print(f"Error reading session file: {e}")
        return None, None

# --- Command Handlers ---
@user_bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    
    # Check if user exists, if not create a new entry
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        users.insert_one({"user_id": user_id, "wallet": 0})
        print(f"Created new user: {user_id}")
    
    # Clear any temporary user state that could cause issues
    users.update_one(
        {"user_id": user_id},
        {"$unset": {
            "temp_manual_monitor": "",
            "temp_manual_generate": "",
            "temp_add_number": "",
            "phone_auth": ""
        }}
    )
    
    # Check if message has been processed recently to prevent duplicates
    processed_key = f"start_{user_id}_{int(datetime.now().timestamp()) // 10}"  # Group by 10-second window
    if processed_key in recent_otps:
        print(f"Preventing duplicate start command processing for user {user_id}")
        return
    
    # Mark as processed
    recent_otps[processed_key] = True
    
    # Send a single welcome message
    try:
        await message.reply_text(
            "**Welcome to the Number Selling Bot!**\nChoose an option below:",
            reply_markup=button_menu()
        )
    except Exception as e:
        print(f"Error sending start message: {e}")
        
    # Clean up old processed keys (keep for 30 seconds)
    current_time = int(datetime.now().timestamp())
    old_keys = [k for k in recent_otps.keys() if k.startswith("start_") and int(k.split("_")[-1]) < (current_time // 10 - 3)]
    for k in old_keys:
        if k in recent_otps:
            del recent_otps[k]

@user_bot.on_message(filters.command("help"))
async def help_command(client, message):
    """Send help text when command /help is issued."""
    user_id = message.from_user.id
    
    # Basic help for all users
    help_text = (
        "📝 **Available Commands**\n\n"
        "/start - Start the bot and see main menu\n"
        "/mynumbers - Show numbers you have purchased\n"
        "/help - Show this help message\n"
        "/id - Get your Telegram user ID"
    )
    
    # Additional admin commands
    if is_admin(user_id):
        admin_help = (
            "\n\n👑 **Admin Commands**\n\n"
            "/admin - Access admin panel\n"
            "/listnumbers - List all numbers in inventory\n"
            "/clearinventory - Clear all inventory data\n"
            "/generateSession +PHONE - Generate a session for a number\n"
            "/addsession +PHONE SESSION - Add a session string manually\n"
            "/startmonitor +PHONE - Start OTP monitoring for a number\n"
            "/stopmonitor +PHONE - Stop OTP monitoring for a number\n"
            "/exportstring +PHONE - Export a session string\n"
            "/deletesession +PHONE - Delete a session"
        )
        help_text += admin_help
    
    await message.reply_text(help_text)

@user_bot.on_message(filters.command("mynumbers") & filters.private)
async def my_numbers_command(client, message):
    """Show user's purchased numbers"""
    user_id = message.from_user.id
    
    # Get user's purchased numbers
    user_numbers = list(numbers_inventory.find({"sold_to": user_id, "status": "sold"}))
    
    if not user_numbers:
        await message.reply_text(
            "You don't have any purchased numbers yet. Use the menu below to buy one:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
        )
        return
    
    # Display user's numbers
    response = "Your purchased numbers:\n\n"
    
    for i, number in enumerate(user_numbers, 1):
        phone = number.get("phone_number")
        country = number.get("country", "Unknown").upper()
        plan = number.get("plan", "Regular").capitalize()
        
        # Check if number has active session
        has_session = "✅" if number.get("session_string") else "❌"
        is_monitoring = "✅" if number.get("otp_monitoring_active") else "❌"
        
        response += f"{i}. 📱 **{phone}**\n"
        response += f"   Country: {country} | Plan: {plan}\n"
        response += f"   Session: {has_session} | Monitoring: {is_monitoring}\n\n"
    
    await message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔢 Buy Another Number", callback_data="buy_number")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_message(filters.command("id") & filters.private)
async def my_id(client, message):
    """Show the user their Telegram ID"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    print(f"ID command received from {first_name} (@{username}), ID: {user_id}")
    
    await message.reply_text(
        f"Your Telegram Information:\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Name: {first_name}\n"
        f"🔤 Username: @{username}\n\n"
        f"To set yourself as admin, update the ADMIN_ID value in the bot code."
    )

# --- Callback Query Handlers ---
@user_bot.on_callback_query(filters.regex("^main_menu$"))
async def main_menu(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Welcome back! Choose an option below:**",
        reply_markup=button_menu()
    )

@user_bot.on_callback_query(filters.regex("^buy_number$"))
async def select_service(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Service:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Telegram", callback_data="buy_telegram")],
            [InlineKeyboardButton("WhatsApp", callback_data="buy_whatsapp")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_telegram$"))
async def select_country(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Country & Plan Type:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇮🇳 India (₹50)", callback_data="ind_regular"),
             InlineKeyboardButton("VIP (₹100)", callback_data="ind_vip")],
            [InlineKeyboardButton("🇧🇩 Bangladesh (₹35)", callback_data="bd_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="bd_vip")],
            [InlineKeyboardButton("🇺🇸 USA (₹50)", callback_data="usa_regular")],
            [InlineKeyboardButton("🇳🇬 Nigeria (₹35)", callback_data="ng_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="ng_vip")],
            [InlineKeyboardButton("🌍 Other (₹35)", callback_data="other_regular")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^(ind|bd|usa|ng|other)_(regular|vip)$"))
async def handle_country_selection(client, callback_query):
    country_code = callback_query.data.split('_')[0]
    plan_type = callback_query.data.split('_')[1]
    
    prices = {
        "ind": {"regular": 50, "vip": 100},
        "bd": {"regular": 35, "vip": 80},
        "usa": {"regular": 50, "vip": 80},
        "ng": {"regular": 35, "vip": 80},
        "other": {"regular": 35, "vip": 80}
    }
    
    price = prices[country_code][plan_type]
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Payment Instructions\n\n"
        f"Country: {country_code.upper()}\n"
        f"Plan: {plan_type.capitalize()}\n"
        f"Amount: ₹{price}\n\n"
        f"Please send ₹{price} to:\n"
        f"UPI: `{UPI_ID}`\n\n"
        "After payment, click 'I Have Paid' below.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("✅ I Have Paid", callback_data=f"confirm_{country_code}_{plan_type}")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^confirm_[a-z]+_(regular|vip)$"))
async def handle_payment_confirmation(client, callback_query):
    country_code = callback_query.data.split('_')[1]
    plan_type = callback_query.data.split('_')[2]
    
    # Check if there's an available number for this country and plan
    available_number = numbers_inventory.find_one({
        "country": country_code,
        "plan": plan_type,
        "status": "available"
    })
    
    if not available_number:
        await callback_query.answer("No numbers available for this selection!", show_alert=True)
        await safe_edit_message(
            callback_query.message,
            f"⚠️ Sorry, we're out of stock for {country_code.upper()} {plan_type} numbers.\n\n"
            f"Please try a different country or plan, or contact {ADMIN_USERNAME} for assistance.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
            ])
        )
        return
    
    await callback_query.answer()
    
    payment_data = {
        "user_id": callback_query.from_user.id,
        "username": callback_query.from_user.username,
        "country": country_code,
        "plan": plan_type,
        "status": "pending",
        "admin_action": "pending",
        "reserved_number": available_number["phone_number"],
        "timestamp": datetime.now()
    }
    result = pending_approvals.insert_one(payment_data)
    
    # Mark the number as reserved
    numbers_inventory.update_one(
        {"_id": available_number["_id"]},
        {"$set": {"status": "reserved", "reserved_for": callback_query.from_user.id}}
    )
    
    await safe_edit_message(
        callback_query.message,
        "📸 Payment Verification\n\n"
        "Please send a clear screenshot of your payment receipt.\n\n"
        "Our admin will verify it within 15-30 minutes.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"{country_code}_{plan_type}")]
        ])
    )

@user_bot.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    
    pending_payment = pending_approvals.find_one(
        {"user_id": user_id, "admin_action": "pending"},
        sort=[("timestamp", pymongo.DESCENDING)]
    )
    
    if not pending_payment:
        await message.reply_text("⚠️ Please click 'I Have Paid' before sending screenshots!")
        return

    try:
        # Store the screenshot in database
        pending_approvals.update_one(
            {"_id": pending_payment["_id"]},
            {"$set": {"screenshot_id": message.photo.file_id}}
        )
        
        # Format the payment ID as a string
        payment_id_str = str(pending_payment["_id"])
        
        # Log important information
        logger.info(f"Processing payment screenshot from user {user_id}, payment ID: {payment_id_str}")
        print(f"Payment screenshot received: user={user_id}, payment_id={payment_id_str}")
        
        # Handle admin notification with admin_notification helper
        admin_notified = await admin_notification(
            client,
            f"🔄 Payment Verification Request\n\n"
                f"User: {message.from_user.mention} (ID: {user_id})\n"
                f"Country: {pending_payment['country'].upper()}\n"
                f"Plan: {pending_payment['plan'].capitalize()}\n"
                f"Number: {pending_payment.get('reserved_number', 'Not assigned')}\n"
                f"Payment ID: {payment_id_str}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Approve", 
                        callback_data=f"approve_{user_id}_{payment_id_str}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", 
                        callback_data=f"reject_{user_id}_{payment_id_str}"
                    )
                ]
            ])
        )
        
        if not admin_notified:
            # Log the failure
            logger.error(f"Failed to notify admin about payment {payment_id_str}")
            print(f"Admin notification failed for payment {payment_id_str}")
            
            # Update status to indicate admin notification failure
            pending_approvals.update_one(
                {"_id": pending_payment["_id"]},
                {"$set": {
                    "admin_action": "notification_failed",
                    "admin_error": "Failed to notify admin"
                }}
            )
            
            await message.reply_text(
                "⚠️ We're having trouble processing your payment.\n"
                "Please contact admin for assistance."
            )
            return
        
        # Also send the screenshot to admin
        try:
            await client.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo.file_id,
                caption=f"📷 Payment screenshot from user {user_id}\nPayment ID: {payment_id_str}"
            )
            logger.info(f"Payment screenshot forwarded to admin")
            
            # Send success message only after everything is successful
            await message.reply_text(
                "✅ Screenshot received!\n"
                "Admin will verify your payment shortly."
            )
            
        except Exception as e:
            logger.error(f"Failed to forward screenshot to admin: {e}")
            print(f"Failed to forward screenshot to admin: {e}")
            # Send error message only if admin notification fails
            await message.reply_text(
                "❌ Failed to process screenshot. Please try again or contact admin."
            )
        
    except Exception as e:
        logger.error(f"Screenshot handling error: {e}")
        print(f"Screenshot handling error: {e}")
        # Send error message only for general errors
        await message.reply_text(
            "❌ Failed to process screenshot. Please try again or contact admin."
        )

@user_bot.on_callback_query(filters.regex("^(approve|reject)_"))
async def handle_admin_approval(client, callback_query):
    try:
        # Log the callback data
        print(f"Admin approval callback received: {callback_query.data}")
        logger.info(f"Admin approval callback received: {callback_query.data}")
        
        # Split the callback data
        parts = callback_query.data.split('_')
        if len(parts) < 3:
            await callback_query.answer("Invalid callback data format!", show_alert=True)
            return
            
        action = parts[0]
        user_id = int(parts[1])
        payment_id = '_'.join(parts[2:])  # Combine all remaining parts in case ObjectId contains underscores
        
        print(f"Parsed callback data: action={action}, user_id={user_id}, payment_id={payment_id}")
        
        # Try to convert to ObjectId
        try:
            payment_oid = ObjectId(payment_id)
        except Exception as e:
            print(f"Error converting payment_id to ObjectId: {e}")
            await callback_query.answer(f"Invalid payment ID format: {payment_id}", show_alert=True)
            return
            
        # Find the payment
        payment = pending_approvals.find_one({
            "_id": payment_oid,
            "user_id": user_id
        })
        
        if not payment:
            # Try logging the payment we're looking for
            print(f"Payment not found: _id={payment_oid}, user_id={user_id}")
            try:
                # Check if payment exists at all
                payment_exists = pending_approvals.find_one({"_id": payment_oid})
                if payment_exists:
                    print(f"Payment exists but with different user_id: {payment_exists.get('user_id')}")
                else:
                    print(f"No payment with _id={payment_oid} exists")
                    
                # Check if user has any pending payments
                user_payments = list(pending_approvals.find({"user_id": user_id}))
                print(f"User {user_id} has {len(user_payments)} payments in database")
            except Exception as e:
                print(f"Error when searching for payment: {e}")
                
            await callback_query.answer("Payment not found or already processed!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment not found or already processed\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        # Check if payment has already been processed
        if payment.get("admin_action") != "pending":
            await callback_query.answer(f"Payment already {payment.get('admin_action')}!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment already processed ({payment.get('admin_action')})\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        if action == "approve":
            print(f"Approving payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "approved",
                    "admin_action": "approved",
                    "approved_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment in database")
                await callback_query.answer("Failed to update payment!", show_alert=True)
                return
                
            # Assign the number to the user
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                # Check if this number has a session string in the database
                number_data = numbers_inventory.find_one({"phone_number": reserved_number})
                
                if number_data and number_data.get("session_string"):
                    # Number already has a session string, mark as sold
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now()
                        }}
                    )
                    
                    # Start monitoring for OTP immediately
                    success = await start_monitoring_for_otp(reserved_number, user_id)
                    
                    # Send success message to user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"OTP monitoring is {('active' if success else 'not active')}.\n"
                                 f"Use this number to sign in to Telegram, and we'll send you the OTP.",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔢 New Number", callback_data="buy_number")],
                                [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                            ])
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
                else:
                    # No session string found - admin needs to add it
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now(),
                            "needs_session": True
                        }}
                    )
                    
                    # Notify admin that session is needed
                    await admin_notification(
                        client,
                        f"⚠️ Session string needed!\n\n"
                        f"Number: {reserved_number}\n"
                        f"Sold to: {user_id}\n\n"
                        f"Please add a session string for this number using the command:\n"
                        f"/addsession {reserved_number} SESSION_STRING"
                    )
                    
                    # Notify user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"Our admin is preparing this number for you. You'll be notified when it's ready to use."
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
            
            await callback_query.answer("Payment approved!")
            await callback_query.message.edit_text(
                f"✅ Approved payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}\n\n"
                f"Status: Sold"
            )
            
        else:  # Rejection
            print(f"Rejecting payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "rejected",
                    "admin_action": "rejected",
                    "rejected_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment rejection in database")
                await callback_query.answer("Failed to reject payment!", show_alert=True)
                return
            
            # Return the number to available status
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                numbers_inventory.update_one(
                    {"phone_number": reserved_number},
                    {"$set": {"status": "available", "reserved_for": None}}
                )
                
            try:
                await client.send_message(
                    chat_id=user_id,
                    text="❌ Payment Rejected\n\n"
                         "Your payment could not be verified.\n"
                         f"Contact {ADMIN_USERNAME} if this is a mistake.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                    ])
                )
                print(f"Sent rejection notification to user {user_id}")
            except Exception as e:
                print(f"Failed to notify user about rejected payment: {e}")
                logger.error(f"Failed to notify user about rejected payment: {e}")
                
            await callback_query.answer("Payment rejected!")
            await callback_query.message.edit_text(
                f"❌ Rejected payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}"
            )
            
    except Exception as e:
        print(f"Error in admin approval callback: {e}")
        logger.error(f"Error in admin approval: {e}")
        await callback_query.answer(f"Error processing approval: {str(e)}", show_alert=True)

async def monitor_session_files():
    while True:
        try:
            pending_orders = pending_approvals.find({
                "status": "awaiting_session"
            }).sort("timestamp", pymongo.ASCENDING)
            
            for order in pending_orders:
                for filename in os.listdir("sessions"):
                    if filename.endswith(".session"):
                        phone_number, _ = get_otp_from_session(filename[:-8])
                        
                        if phone_number:
                            pending_approvals.update_one(
                                {"_id": order["_id"]},
                                {"$set": {
                                    "status": "awaiting_otp",
                                    "number": phone_number,
                                    "session_file": filename
                                }}
                            )
                            
                            try:
                                await user_bot.send_message(
                                    chat_id=order["user_id"],
                                    text=f"🔢 Number Ready: {phone_number}\n\n"
                                         f"Please:\n"
                                         f"1. Login to Telegram using this number\n"
                                         f"2. Send the OTP you receive\n\n"
                                         f"Your OTP will automatically appear here once sent.",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("✅ I've Sent OTP", callback_data=f"check_otp_{phone_number}")]
                                    ])
                                )
                                os.remove(f"sessions/{filename}")
                                break
                            except Exception as e:
                                print(f"Error notifying user: {e}")
            
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Session monitor error: {e}")
            await asyncio.sleep(30)

@user_bot.on_callback_query(filters.regex("^check_otp_"))
async def check_otp_handler(client, callback_query):
    try:
        phone_number = callback_query.data.split('_')[2]
        _, otp = get_otp_from_session(phone_number)
        
        if not otp:
            await callback_query.answer("OTP not found yet! Try again.", show_alert=True)
            return
            
        await asyncio.sleep(2)
        
        await client.send_message(
            chat_id=callback_query.from_user.id,
            text=f"✅ OTP Received: {otp}\n\n"
                 "Complete login within 2 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👍 Login Successful", callback_data="login_success")],
                [InlineKeyboardButton("🆘 Help", callback_data="support")]
            ])
        )
        
        pending_approvals.update_one(
            {"user_id": callback_query.from_user.id, "status": "awaiting_otp"},
            {"$set": {"status": "otp_delivered", "otp": otp}}
        )
        
        await callback_query.answer("OTP sent!")
        
    except Exception as e:
        print(f"OTP check error: {e}")
        await callback_query.answer("Error fetching OTP", show_alert=True)

@user_bot.on_callback_query(filters.regex("^login_success$"))
async def handle_login_success(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🎉 Thank you for your order!\n\n"
        "Your number is now ready for use.\n\n"
        "Start a new conversation with /start when you need another number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔄 New Order", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^support$"))
async def handle_support(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🆘 Support\n\n"
        f"Contact admin directly: {ADMIN_USERNAME}\n"
        "Include your order details for faster response.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^recharge$"))
async def handle_recharge(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "💰 Recharge Your Wallet\n\n"
        f"Send money to:\n"
        f"UPI: `{UPI_ID}`\n"
        f"Binance ID: {BINANCE_ID}\n\n"
        "After payment, send a screenshot with caption: #recharge",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^check_balance$"))
async def handle_check_balance(client, callback_query):
    user_id = callback_query.from_user.id
    user_data = users.find_one({"user_id": user_id})
    balance = user_data.get("wallet", 0) if user_data else 0
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Your Wallet Balance\n\n"
        f"Current Balance: ₹{balance}\n\n"
        f"Use the recharge option to add funds.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_whatsapp$"))
async def whatsapp_service(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 WhatsApp Service\n\n"
        "WhatsApp virtual numbers will be available soon!\n\n"
        "Please check back later or contact support for updates.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

# --- Admin Command Handlers ---
@user_bot.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    """Admin panel with management options"""
    if str(message.from_user.id) not in ADMIN_USER_IDS and str(message.from_user.id) != ADMIN_ID:
        await message.reply_text("⛔️ You are not authorized to use this command.")
        return

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

@user_bot.on_callback_query(filters.regex("^admin_manage_orders$"))
async def admin_manage_orders(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    orders_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Pending Orders", callback_data="admin_pending_orders"),
            InlineKeyboardButton("✅ Completed Orders", callback_data="admin_completed_orders")
        ],
        [
            InlineKeyboardButton("💰 Sales Report", callback_data="admin_sales_report"),
            InlineKeyboardButton("📈 Revenue Stats", callback_data="admin_revenue_stats")
        ],
        [
            InlineKeyboardButton("👥 Customer List", callback_data="admin_customer_list"),
            InlineKeyboardButton("📋 Order History", callback_data="admin_order_history")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📊 **Orders & Sales**\n\n"
        "Manage orders and view sales information:",
        reply_markup=orders_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_settings$"))
async def admin_settings(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    settings_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Payment Settings", callback_data="admin_payment_settings"),
            InlineKeyboardButton("🔔 Notification Settings", callback_data="admin_notification_settings")
        ],
        [
            InlineKeyboardButton("⚡ Performance Settings", callback_data="admin_performance_settings"),
            InlineKeyboardButton("🔒 Security Settings", callback_data="admin_security_settings")
        ],
        [
            InlineKeyboardButton("📱 Bot Settings", callback_data="admin_bot_settings"),
            InlineKeyboardButton("🔄 Backup & Restore", callback_data="admin_backup_restore")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "⚙️ **Settings**\n\n"
        "Configure bot settings and preferences:",
        reply_markup=settings_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_reports$"))
async def admin_reports(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    reports_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Daily Report", callback_data="admin_daily_report"),
            InlineKeyboardButton("📈 Weekly Report", callback_data="admin_weekly_report")
        ],
        [
            InlineKeyboardButton("📉 Monthly Report", callback_data="admin_monthly_report"),
            InlineKeyboardButton("📋 Custom Report", callback_data="admin_custom_report")
        ],
        [
            InlineKeyboardButton("📱 System Status", callback_data="admin_system_status"),
            InlineKeyboardButton("⚠️ Error Logs", callback_data="admin_error_logs")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📋 **Reports**\n\n"
        "View various reports and system information:",
        reply_markup=reports_markup
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
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "🔑 Session Management\n\n"
        "Please select an option:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^admin_import_session$"))
async def admin_import_session_menu(client, callback_query):
    """Show menu for importing session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"import_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📥 Import Session\n\n"
        "Select a number to import session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^import_session_"))
async def handle_import_session_button(client, callback_query):
    """Handle import session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("import_session_", "")
    
    # Store the phone number in user state
    user_states[callback_query.from_user.id] = {
        "action": "import_session",
        "phone": phone
    }
    
    await callback_query.message.edit_text(
        f"📥 Import Session\n\n"
        f"Please enter the session string for {phone}:\n\n"
        f"Example: 1BQANOTEzrHE...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_export_session$"))
async def admin_export_session_menu(client, callback_query):
    """Show menu for exporting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"export_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📤 Export Session\n\n"
        "Select a number to export session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^export_session_"))
async def handle_export_session_button(client, callback_query):
    """Handle export session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("export_session_", "")
    
    # Get the session string from the database
    number = numbers_inventory.find_one({"phone": phone})
    if not number:
        await callback_query.answer("❌ Number not found in inventory.", show_alert=True)
        return
    
    session_string = number.get("session_string")
    if not session_string:
        await callback_query.answer("❌ No session string found for this number.", show_alert=True)
        return
    
    # Send the session string
    await callback_query.message.reply_text(
        f"📤 Session String for {phone}:\n\n"
        f"`{session_string}`\n\n"
        f"⚠️ Keep this session string secure and don't share it with anyone!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_export_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_delete_session$"))
async def admin_delete_session_menu(client, callback_query):
    """Show menu for deleting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"delete_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "❌ Delete Session\n\n"
        "Select a number to delete session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^delete_session_"))
async def handle_delete_session_button(client, callback_query):
    """Handle delete session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("delete_session_", "")
    
    # Update the database to remove the session string
    result = numbers_inventory.update_one(
        {"phone": phone},
        {"$unset": {"session_string": ""}}
    )
    
    if result.modified_count > 0:
        await callback_query.answer("✅ Session deleted successfully!", show_alert=True)
    else:
        await callback_query.answer("❌ No session found for this number.", show_alert=True)
    
    # Go back to session management menu
    await admin_session_management(client, callback_query)

def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

@user_bot.on_callback_query(filters.regex("^session_login_number$"))
async def session_login_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "📱 **Login New Number**\n\n"
        "To login a Telegram number, use the command:\n"
        "/loginnumber phone_number\n\n"
        "Example: /loginnumber +917012345678\n\n"
        "You'll receive a verification code on that number which you'll need to enter.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_import$"))
async def session_import(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 **Import Session**\n\n"
        "To import a session string for a number, use the command:\n"
        "/addsession phone_number session_string\n\n"
        "Example: /addsession +917012345678 1BQANOTEzrHE...\n\n"
        "The system will validate the session and start OTP monitoring if the number is sold.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_export$"))
async def session_export(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔑 **Export Session**\n\n"
        "To export a session string for a number, use the command:\n"
        "/exportstring phone_number\n\n"
        "Example: /exportstring +917012345678\n\n"
        "This will generate a session string that can be used with Telethon.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_delete$"))
async def session_delete(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "❌ **Delete Session**\n\n"
        "To delete a session for a number, use the command:\n"
        "/deletesession phone_number\n\n"
        "Example: /deletesession +917012345678\n\n"
        "This will remove the session from the database and delete any session files.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_status$"))
async def session_status(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get numbers with sessions
    numbers_with_sessions = list(numbers_inventory.find({
        "session_string": {"$exists": True}
    }))
    
    if not numbers_with_sessions:
        await safe_edit_message(
            callback_query.message,
            "📋 **Session Status**\n\n"
            "No numbers with active sessions found.\n\n"
            "Use the Login Number or Import Session options to add sessions.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
            ])
        )
        return
    
    # Create status message
    status_text = "📋 **Session Status**\n\n"
    
    for number in numbers_with_sessions:
        phone = number.get("phone_number", "Unknown")
        is_authorized = "✅ Authorized" if number.get("is_authorized") else "❌ Not authorized"
        is_monitoring = "✅ Active" if number.get("otp_monitoring_active") else "❌ Inactive"
        status = number.get("status", "unknown")
        sold_to = number.get("sold_to", "N/A")
        
        status_text += f"📱 **{phone}**\n"
        status_text += f"Status: {status.capitalize()}\n"
        status_text += f"Authorization: {is_authorized}\n"
        status_text += f"Monitoring: {is_monitoring}\n"
        if status == "sold":
            status_text += f"Sold to: {sold_to}\n"
        status_text += "\n"
    
    await safe_edit_message(
        callback_query.message,
        status_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_message(filters.private & filters.reply & filters.incoming)
async def handle_admin_input(client, message):
    user_id = message.from_user.id
    message_text = message.text if message.text else "No text"
    print(f"Admin input received: {message_text} from user: {user_id}")
    
    # Check if user is admin
    if not is_admin(user_id):
        print(f"User {user_id} is not admin, ignoring message")
        return
    
    # Get user data from database
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        print(f"No user data found for user {user_id}")
        users.insert_one({"user_id": user_id, "wallet": 0})
        user_data = users.find_one({"user_id": user_id})
        if not user_data:
            print("Failed to create user data")
            return
        print(f"Created new user data for {user_id}")
    
    print(f"User data: {user_data}")
    
    # Check if admin is in the process of logging in a number
    if "temp_login" in user_data and user_data["temp_login"].get("step") == "awaiting_code":
        print(f"Processing OTP code input: {message_text}")
        # Handle OTP code input for phone login
        try:
            phone_number = user_data["temp_login"]["phone_number"]
            code = message.text.strip()
            
            # Validate code format (basic check)
            if not re.match(r'^\d{5}$', code):
                print(f"Invalid OTP format: {code}")
                await message.reply_text(
                    "⚠️ Invalid code format. Please enter a 5-digit code.\n"
                    "Example: 12345"
                )
                return
            
            print(f"Valid OTP format, attempting to sign in with {phone_number} and code {code}")
            
            # Get client for this phone
            session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
            memory_session = StringSession()
            client = TelegramClient(memory_session, API_ID, API_HASH)
            await client.connect()
            
            # Sign in with the provided code
            await client.sign_in(phone_number, code)
            print(f"Successfully signed in with {phone_number}")
            
            # Export the session as a string
            string_session = StringSession.save(client.session)
            print(f"Exported session string for {phone_number}")
            
            # Update the database
            update_result = numbers_inventory.update_one(
                {"phone_number": phone_number},
                {"$set": {
                    "session_string": string_session,
                    "session_added_at": datetime.now(),
                    "is_authorized": True
                }}
            )
            print(f"Database update result: {update_result.modified_count} document(s) modified")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            print(f"Cleared temp_login data for user {user_id}")
            
            # Disconnect this temporary client
            await client.disconnect()
            
            # If the number is sold, start monitoring
            number_data = numbers_inventory.find_one({"phone_number": phone_number})
            if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
                user_to_monitor = number_data.get("sold_to")
                print(f"Starting OTP monitoring for number {phone_number} for user {user_to_monitor}")
                success = await start_monitoring_for_otp(phone_number, user_to_monitor)
                monitoring_status = f"OTP monitoring: {'✅ Started' if success else '❌ Failed to start'}"
                
                # Notify the user if monitoring started successfully
                if success:
                    try:
                        await user_bot.send_message(
                            chat_id=user_to_monitor,
                            text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                 f"You can now use this number to sign in to Telegram.\n"
                                 f"When you request an OTP code, it will be automatically sent to you here."
                        )
                        print(f"User {user_to_monitor} notified about active number {phone_number}")
                    except Exception as e:
                        logger.error(f"Failed to notify user about active number: {e}")
                        print(f"Failed to notify user {user_to_monitor}: {e}")
            else:
                monitoring_status = "Number not sold yet, no monitoring started"
                print(f"No monitoring needed for {phone_number} as it's not sold yet")
            
            await message.reply_text(
                f"✅ Successfully logged in to {phone_number}!\n\n"
                f"Session string has been saved to the database.\n"
                f"{monitoring_status}\n\n"
                f"You can now use this number with the OTP service."
            )
            
        except Exception as e:
            logger.error(f"Error in login verification: {str(e)}")
            print(f"Error in login verification: {str(e)}")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            
            await message.reply_text(f"❌ Login error: {str(e)}")
        
        # We've handled the admin input, so return
        return
    
    # Check if admin is in the process of adding a number
    if "temp_add_number" in user_data and user_data["temp_add_number"].get("step") == "enter_phone":
        print(f"Processing phone number input: {message_text}")
        
        # Get the phone number from the message
        phone_number = message.text.strip()
        
        # Validate phone number format (basic validation)
        if not re.match(r'^\+\d{10,15}$', phone_number):
            print(f"Invalid phone number format: {phone_number}")
            await message.reply_text(
                "⚠️ Invalid phone number format. Please use international format:\n"
                "+COUNTRYCODE NUMBER (e.g. +917012345678)"
            )
            return
        
        # Get country and plan from stored data
        country_code = user_data["temp_add_number"]["country"]
        plan_type = user_data["temp_add_number"]["plan"]
        
        # Check if number already exists
        existing_number = numbers_inventory.find_one({"phone_number": phone_number})
        if existing_number:
            print(f"Number {phone_number} already exists in inventory")
            await message.reply_text(
                f"⚠️ Number {phone_number} is already in the inventory."
            )
            return
        
        # Add to inventory
        number_data = {
            "phone_number": phone_number,
            "country": country_code,
            "plan": plan_type,
            "status": "available",
            "added_at": datetime.now(),
            "added_by": user_id
        }
        
        try:
            insert_result = numbers_inventory.insert_one(number_data)
            print(f"Number added to inventory with ID: {insert_result.inserted_id}")
            
            # Clear the temp data
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_add_number": ""}}
            )
            print(f"Cleared temp_add_number data for user {user_id}")
            
            # Show confirmation with options to add more or go back
            await message.reply_text(
                f"✅ Number added to inventory:\n"
                f"📱 {phone_number}\n"
                f"🌍 {country_code.upper()}\n"
                f"📋 {plan_type.capitalize()}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Another Number", callback_data="admin_add_number")],
                    [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ])
            )
            print(f"Confirmation message sent for {phone_number}")
        except Exception as e:
            print(f"Error adding number to inventory: {e}")
            await message.reply_text(f"❌ Error adding number: {str(e)}")
        return
    
    # Handle bulk add
    if "temp_bulk_add" in user_data and user_data["temp_bulk_add"].get("step") == "enter_numbers":
        print(f"Processing bulk add input with {len(message.text.strip().split('\\n'))} lines")
        # Process bulk numbers
        lines = message.text.strip().split('\n')
        added = 0
        errors = []
        
        for i, line in enumerate(lines, 1):
            parts = line.strip().split()
            if len(parts) < 3:
                error_msg = f"Line {i}: Not enough information"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            phone_number = parts[0].strip()
            country_code = parts[1].lower().strip()
            plan_type = parts[2].lower().strip()
            
            # Validate phone format
            if not re.match(r'^\+\d{10,15}$', phone_number):
                error_msg = f"Line {i}: Invalid phone format '{phone_number}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate country code
            valid_countries = ["ind", "bd", "usa", "ng", "other"]
            if country_code not in valid_countries:
                error_msg = f"Line {i}: Invalid country code '{country_code}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate plan type
            valid_plans = ["regular", "vip"]
            if plan_type not in valid_plans:
                error_msg = f"Line {i}: Invalid plan type '{plan_type}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Check if number already exists
            if numbers_inventory.find_one({"phone_number": phone_number}):
                error_msg = f"Line {i}: Number '{phone_number}' already exists"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Add to inventory
            number_data = {
                "phone_number": phone_number,
                "country": country_code,
                "plan": plan_type,
                "status": "available",
                "added_at": datetime.now(),
                "added_by": user_id
            }
            
            try:
                insert_result = numbers_inventory.insert_one(number_data)
                print(f"Added number {phone_number} with ID: {insert_result.inserted_id}")
                added += 1
            except Exception as e:
                error_msg = f"Line {i}: Database error - {str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        # Clear the temp data
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"temp_bulk_add": ""}}
        )
        print(f"Cleared temp_bulk_add data for user {user_id}")
        
        # Prepare result message
        result_message = f"✅ Added {added} numbers to inventory\n\n"
        
        if errors:
            result_message += "⚠️ Errors encountered:\n"
            for error in errors[:10]:  # Show first 10 errors
                result_message += f"- {error}\n"
            
            if len(errors) > 10:
                result_message += f"...and {len(errors) - 10} more errors\n"
        
        # Show confirmation
        await message.reply_text(
            result_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                [InlineKeyboardButton("➕ Add More Numbers", callback_data="admin_bulk_add")],
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        print(f"Bulk add completed: {added} added, {len(errors)} errors")
        return

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Number Management", callback_data="admin_number_management"),
            InlineKeyboardButton("🔐 Session Control", callback_data="admin_session_management")
        ],
        [
            InlineKeyboardButton("📶 OTP Monitoring", callback_data="admin_monitor_otp"),
            InlineKeyboardButton("📊 Orders & Sales", callback_data="admin_orders_sales")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
            InlineKeyboardButton("📋 Reports", callback_data="admin_reports")
        ]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "👨‍💼 **Admin Panel**\n\n"
        "Welcome to the admin control center. Select a category to manage:",
        reply_markup=admin_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_add_number$"))
async def admin_add_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Create markup for number type selection
    type_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Telegram Number", callback_data="add_number_type_telegram")],
        [InlineKeyboardButton("📲 WhatsApp Number", callback_data="add_number_type_whatsapp")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📱 **Select Number Type**\n\n"
        "Choose the type of number you want to add:",
        reply_markup=type_markup
    )

@user_bot.on_callback_query(filters.regex("^add_number_type_(telegram|whatsapp)$"))
async def handle_add_number_type(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    number_type = callback_query.data.split('_')[-1]
    
    # Store the number type in user data
    user_id = callback_query.from_user.id
#!/usr/bin/env python
# -*- coding: utf-8 -*-

#############################################################
# TELEGRAM BOT MAIN CODE - DO NOT MODIFY DIRECTLY           #
# -------------------------------------------------------   #
# This is the main, stable version of the Telegram bot.     #
# Any changes should be tested in a development branch      #
# before being incorporated into this main version.         #
#                                                           #
# Last updated: April 2, 2025                               #
# Features:                                                 #
# - Telegram and WhatsApp number management                 #
# - OTP forwarding and monitoring                           #
# - Session management with import/export                   #
# - Admin panel with user management                        #
# - Payment processing                                      #
#############################################################

import asyncio
import json
import logging
import os
import random
import re
import requests
import shutil
import string
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import uuid
import glob
import time
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot Credentials ---
API_ID = 25733253
API_HASH = "eabb8d10c13a3a7f63b2b832be8336d6"
BOT_TOKEN = "7011527407:AAEPw2k9NYJbQNL6qpGJWrcmokLp7nq3D2w"
ADMIN_ID = "7536665814"  # Your Telegram user ID as string
ADMIN_USERNAME = "@Mr_Griffiin"  # Your Telegram username

UPI_ID = "sunnysing2632-3@okaxis"
BINANCE_ID = "1018484211"

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client["telegram_bot_new_fresh"]  # Using a new database name to avoid lock conflicts
users = db["users"]
orders = db["orders"]
pending_approvals = db["pending_approvals"]
numbers_inventory = db["numbers_inventory"]

# Initialize Pyrogram Client
# user_bot = Client(
    "number_selling_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Session management ---
# Dictionary to store active telethon clients
active_telethon_clients = {}
# Directory for storing session files
SESSIONS_DIR = "new_fresh_sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# --- Global Variables ---
telethon_user_data = {}  # Store temporary data for Telethon session generation
recent_otps = {}  # Store recent OTPs to prevent duplicates

# --- Helper Functions for OTP Management ---
async def get_telethon_client_for_number(phone_number, session_string=None):
    """
    Get or create a Telethon client for the given phone number.
    Using in-memory sessions to avoid database locks.
    
    Args:
        phone_number: The phone number to get a client for
        session_string: Optional session string to use
        
    Returns:
        TelegramClient: The client
    """
    try:
        # Check if we already have an active client for this number
        if phone_number in active_telethon_clients:
            print(f"Returning existing client for {phone_number}")
            return active_telethon_clients[phone_number]
            
        print(f"Creating new Telethon client for {phone_number}")
        
        # Create a new client using the session string or in-memory session
        if session_string:
            # Use the provided session string
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        else:
            # Always use in-memory session to avoid database locks
            memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        
        # Connect the client but don't start it yet
        await client.connect()
        
        # Check if the client is authorized
        is_authorized = await client.is_user_authorized()
        print(f"Client for {phone_number} authorized: {is_authorized}")
        
        return client
        
    except Exception as e:
        print(f"Error getting Telethon client for {phone_number}: {e}")
        logger.error(f"Error getting Telethon client for {phone_number}: {e}")
        raise

async def start_monitoring_for_otp(phone_number, user_id):
    """
    Start monitoring a phone number for Telegram OTP codes.
    
    Args:
        phone_number: The phone number to monitor
        user_id: The user to send OTP codes to
    
    Returns:
        bool: True if monitoring started successfully, False otherwise
    """
    try:
        print(f"Starting monitoring for OTP codes for {phone_number}, forwarding to user {user_id}")
        
        # Initialize recent OTPs tracker for this number
        recent_otps[phone_number] = set()
        
        # Get session string from database
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        if not number_data:
            print(f"No number found in database for {phone_number}")
            return False
            
        session_string = number_data.get("session_string")
        if not session_string:
            print(f"No session string found for {phone_number}")
            return False
            
        # Store the owner ID for later use in message forwarding
        sold_to_user = number_data.get("sold_to")
        print(f"Number {phone_number} is sold to user: {sold_to_user}")
        
        # Create and start client
        client = await get_telethon_client_for_number(phone_number, session_string)
        
        # Ensure client is logged in
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            print(f"Client for {phone_number} is not authorized")
            await client.disconnect()
            return False
        
        # Store the client in the active clients dictionary
        active_telethon_clients[phone_number] = client
        
        # Update database to indicate monitoring is active
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {"otp_monitoring_active": True}}
        )
        
        # Set up event handler for new messages
        @client.on(events.NewMessage())
        async def handle_new_message(event):
            try:
                message_text = event.message.message
                print(f"New message received on {phone_number}: {message_text}")
                
                # Check if the message is from Telegram or contains OTP code
                is_otp = False
                otp_code = None
                
                # Check if message is from Telegram
                if event.message.from_id and hasattr(event.message.from_id, 'user_id'):
                    sender_id = event.message.from_id.user_id
                    if sender_id == 777000:  # Telegram's official user ID
                        is_otp = True
                
                # Look for OTP patterns in the message
                otp_patterns = [
                    r'Telegram code (?:is|:) (\d{5})',
                    r'Your login code:? (\d{5})',
                    r'Your code:? (\d{5})',
                    r'verification code:? (\d{5})',
                    r'(\d{5}) is your Telegram code',
                    r'Login code:? (\d{5})',
                    r'[^\d](\d{5})[^\d]',
                ]
                
                for pattern in otp_patterns:
                    match = re.search(pattern, message_text)
                    if match:
                        otp_code = match.group(1)
                        is_otp = True
                        break
                
                if is_otp:
                    print(f"OTP detected: {otp_code if otp_code else 'Pattern matched but no code extracted'}")
                    
                    # Check if this is a duplicate OTP
                    if otp_code:
                        otp_key = f"{otp_code}_{int(datetime.now().timestamp()) // 300}"  # Group by 5-min window
                        
                        # Skip if we've already sent this OTP recently
                        if otp_key in recent_otps.get(phone_number, set()):
                            print(f"Skipping duplicate OTP {otp_code} for {phone_number}")
                            return
                        
                        # Add to recent OTPs
                        if phone_number not in recent_otps:
                            recent_otps[phone_number] = set()
                        recent_otps[phone_number].add(otp_key)
                        
                        # Cleanup old OTPs (keep only last 10)
                        if len(recent_otps[phone_number]) > 10:
                            recent_otps[phone_number] = set(list(recent_otps[phone_number])[-10:])
                    
                    # Format the message to send to the user
                    formatted_message = f"📲 **OTP Code Received**\n\n"
                    
                    if otp_code:
                        formatted_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        formatted_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    formatted_message += f"📱 Phone Number: `{phone_number}`\n"
                    formatted_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    formatted_message += "Enter this code in the Telegram app to complete the login."
                    
                    # Add verification completion button
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Verification Complete", callback_data=f"verify_success_{phone_number}")],
                        [InlineKeyboardButton("🔄 Get New OTP", callback_data=f"new_otp_{phone_number}")],
                        [InlineKeyboardButton("ℹ️ Help", callback_data="otp_help")]
                    ])
                    
                    # Get latest owner information from database
                    current_data = numbers_inventory.find_one({"phone_number": phone_number})
                    current_owner = current_data.get("sold_to") if current_data else None
                    
                    # 1. Send the OTP to the user who purchased the number (if sold)
                    if current_owner:
                        try:
                            await user_bot.send_message(
                                chat_id=current_owner,
                                text=formatted_message,
                                reply_markup=reply_markup
                            )
                            print(f"OTP forwarded to owner {current_owner} for number {phone_number}")
                        except Exception as e:
                            print(f"Failed to send OTP to owner {current_owner}: {e}")
                    
                    # 2. Always send the OTP to the admin
                    admin_message = f"📲 **OTP Forwarded**\n\n"
                    if otp_code:
                        admin_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        admin_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    admin_message += f"📱 Number: `{phone_number}`\n"
                    if current_owner:
                        admin_message += f"👤 Sold to User ID: `{current_owner}`\n"
                    else:
                        admin_message += f"👤 Not sold yet\n"
                    admin_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                    
                    try:
                        await user_bot.send_message(
                            chat_id=ADMIN_ID,
                            text=admin_message
                        )
                        print(f"OTP also forwarded to admin for monitoring")
                    except Exception as e:
                        print(f"Failed to send OTP to admin: {e}")
            except Exception as e:
                print(f"Error handling message in OTP monitor: {e}")
                logger.error(f"Error handling message in OTP monitor: {e}")
        
        # Start the client properly
        print(f"Starting OTP monitoring for {phone_number}...")
        await client.start()
        print(f"✅ Successfully started OTP monitoring for {phone_number}")
        
        return True
        
    except Exception as e:
        print(f"Error starting OTP monitoring: {e}")
        logger.error(f"Error starting OTP monitoring: {e}")
        return False

# --- Helper Functions ---
def initialize_database():
    """Initialize database indexes"""
    try:
        db.pending_approvals.create_index([("user_id", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("admin_action", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("timestamp", pymongo.DESCENDING)])
        print("Database indexes created")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def safe_edit_message(message, text, reply_markup=None):
    """Safely edit message with error handling."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"Error editing message: {e}")

def button_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
        [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
        [InlineKeyboardButton("💳 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="support")]
    ])

def get_otp_from_session(phone_number):
    """Monitor session files for new OTPs and extract phone number"""
    session_path = f"sessions/{phone_number}.session"
    
    if not os.path.exists(session_path):
        return None, None
    
    try:
        with open(session_path, 'r') as f:
            content = f.read()
        
        # Extract phone number
        phone_match = re.search(r'phone_number\s*=\s*([\+\d]+)', content)
        phone_number = phone_match.group(1) if phone_match else None
        
        # Extract OTP
        otp_match = re.search(r'(\b\d{5}\b|\b\d{6}\b)', content)
        otp = otp_match.group(1) if otp_match else None
        
        return phone_number, otp
        
    except Exception as e:
        print(f"Error reading session file: {e}")
        return None, None

# --- Command Handlers ---
@user_bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    
    # Check if user exists, if not create a new entry
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        users.insert_one({"user_id": user_id, "wallet": 0})
        print(f"Created new user: {user_id}")
    
    # Clear any temporary user state that could cause issues
    users.update_one(
        {"user_id": user_id},
        {"$unset": {
            "temp_manual_monitor": "",
            "temp_manual_generate": "",
            "temp_add_number": "",
            "phone_auth": ""
        }}
    )
    
    # Check if message has been processed recently to prevent duplicates
    processed_key = f"start_{user_id}_{int(datetime.now().timestamp()) // 10}"  # Group by 10-second window
    if processed_key in recent_otps:
        print(f"Preventing duplicate start command processing for user {user_id}")
        return
    
    # Mark as processed
    recent_otps[processed_key] = True
    
    # Send a single welcome message
    try:
        await message.reply_text(
            "**Welcome to the Number Selling Bot!**\nChoose an option below:",
            reply_markup=button_menu()
        )
    except Exception as e:
        print(f"Error sending start message: {e}")
        
    # Clean up old processed keys (keep for 30 seconds)
    current_time = int(datetime.now().timestamp())
    old_keys = [k for k in recent_otps.keys() if k.startswith("start_") and int(k.split("_")[-1]) < (current_time // 10 - 3)]
    for k in old_keys:
        if k in recent_otps:
            del recent_otps[k]

@user_bot.on_message(filters.command("help"))
async def help_command(client, message):
    """Send help text when command /help is issued."""
    user_id = message.from_user.id
    
    # Basic help for all users
    help_text = (
        "📝 **Available Commands**\n\n"
        "/start - Start the bot and see main menu\n"
        "/mynumbers - Show numbers you have purchased\n"
        "/help - Show this help message\n"
        "/id - Get your Telegram user ID"
    )
    
    # Additional admin commands
    if is_admin(user_id):
        admin_help = (
            "\n\n👑 **Admin Commands**\n\n"
            "/admin - Access admin panel\n"
            "/listnumbers - List all numbers in inventory\n"
            "/clearinventory - Clear all inventory data\n"
            "/generateSession +PHONE - Generate a session for a number\n"
            "/addsession +PHONE SESSION - Add a session string manually\n"
            "/startmonitor +PHONE - Start OTP monitoring for a number\n"
            "/stopmonitor +PHONE - Stop OTP monitoring for a number\n"
            "/exportstring +PHONE - Export a session string\n"
            "/deletesession +PHONE - Delete a session"
        )
        help_text += admin_help
    
    await message.reply_text(help_text)

@user_bot.on_message(filters.command("mynumbers") & filters.private)
async def my_numbers_command(client, message):
    """Show user's purchased numbers"""
    user_id = message.from_user.id
    
    # Get user's purchased numbers
    user_numbers = list(numbers_inventory.find({"sold_to": user_id, "status": "sold"}))
    
    if not user_numbers:
        await message.reply_text(
            "You don't have any purchased numbers yet. Use the menu below to buy one:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
        )
        return
    
    # Display user's numbers
    response = "Your purchased numbers:\n\n"
    
    for i, number in enumerate(user_numbers, 1):
        phone = number.get("phone_number")
        country = number.get("country", "Unknown").upper()
        plan = number.get("plan", "Regular").capitalize()
        
        # Check if number has active session
        has_session = "✅" if number.get("session_string") else "❌"
        is_monitoring = "✅" if number.get("otp_monitoring_active") else "❌"
        
        response += f"{i}. 📱 **{phone}**\n"
        response += f"   Country: {country} | Plan: {plan}\n"
        response += f"   Session: {has_session} | Monitoring: {is_monitoring}\n\n"
    
    await message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔢 Buy Another Number", callback_data="buy_number")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_message(filters.command("id") & filters.private)
async def my_id(client, message):
    """Show the user their Telegram ID"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    print(f"ID command received from {first_name} (@{username}), ID: {user_id}")
    
    await message.reply_text(
        f"Your Telegram Information:\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Name: {first_name}\n"
        f"🔤 Username: @{username}\n\n"
        f"To set yourself as admin, update the ADMIN_ID value in the bot code."
    )

# --- Callback Query Handlers ---
@user_bot.on_callback_query(filters.regex("^main_menu$"))
async def main_menu(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Welcome back! Choose an option below:**",
        reply_markup=button_menu()
    )

@user_bot.on_callback_query(filters.regex("^buy_number$"))
async def select_service(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Service:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Telegram", callback_data="buy_telegram")],
            [InlineKeyboardButton("WhatsApp", callback_data="buy_whatsapp")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_telegram$"))
async def select_country(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Country & Plan Type:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇮🇳 India (₹50)", callback_data="ind_regular"),
             InlineKeyboardButton("VIP (₹100)", callback_data="ind_vip")],
            [InlineKeyboardButton("🇧🇩 Bangladesh (₹35)", callback_data="bd_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="bd_vip")],
            [InlineKeyboardButton("🇺🇸 USA (₹50)", callback_data="usa_regular")],
            [InlineKeyboardButton("🇳🇬 Nigeria (₹35)", callback_data="ng_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="ng_vip")],
            [InlineKeyboardButton("🌍 Other (₹35)", callback_data="other_regular")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^(ind|bd|usa|ng|other)_(regular|vip)$"))
async def handle_country_selection(client, callback_query):
    country_code = callback_query.data.split('_')[0]
    plan_type = callback_query.data.split('_')[1]
    
    prices = {
        "ind": {"regular": 50, "vip": 100},
        "bd": {"regular": 35, "vip": 80},
        "usa": {"regular": 50, "vip": 80},
        "ng": {"regular": 35, "vip": 80},
        "other": {"regular": 35, "vip": 80}
    }
    
    price = prices[country_code][plan_type]
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Payment Instructions\n\n"
        f"Country: {country_code.upper()}\n"
        f"Plan: {plan_type.capitalize()}\n"
        f"Amount: ₹{price}\n\n"
        f"Please send ₹{price} to:\n"
        f"UPI: `{UPI_ID}`\n\n"
        "After payment, click 'I Have Paid' below.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("✅ I Have Paid", callback_data=f"confirm_{country_code}_{plan_type}")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^confirm_[a-z]+_(regular|vip)$"))
async def handle_payment_confirmation(client, callback_query):
    country_code = callback_query.data.split('_')[1]
    plan_type = callback_query.data.split('_')[2]
    
    # Check if there's an available number for this country and plan
    available_number = numbers_inventory.find_one({
        "country": country_code,
        "plan": plan_type,
        "status": "available"
    })
    
    if not available_number:
        await callback_query.answer("No numbers available for this selection!", show_alert=True)
        await safe_edit_message(
            callback_query.message,
            f"⚠️ Sorry, we're out of stock for {country_code.upper()} {plan_type} numbers.\n\n"
            f"Please try a different country or plan, or contact {ADMIN_USERNAME} for assistance.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
            ])
        )
        return
    
    await callback_query.answer()
    
    payment_data = {
        "user_id": callback_query.from_user.id,
        "username": callback_query.from_user.username,
        "country": country_code,
        "plan": plan_type,
        "status": "pending",
        "admin_action": "pending",
        "reserved_number": available_number["phone_number"],
        "timestamp": datetime.now()
    }
    result = pending_approvals.insert_one(payment_data)
    
    # Mark the number as reserved
    numbers_inventory.update_one(
        {"_id": available_number["_id"]},
        {"$set": {"status": "reserved", "reserved_for": callback_query.from_user.id}}
    )
    
    await safe_edit_message(
        callback_query.message,
        "📸 Payment Verification\n\n"
        "Please send a clear screenshot of your payment receipt.\n\n"
        "Our admin will verify it within 15-30 minutes.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"{country_code}_{plan_type}")]
        ])
    )

@user_bot.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    
    pending_payment = pending_approvals.find_one(
        {"user_id": user_id, "admin_action": "pending"},
        sort=[("timestamp", pymongo.DESCENDING)]
    )
    
    if not pending_payment:
        await message.reply_text("⚠️ Please click 'I Have Paid' before sending screenshots!")
        return

    try:
        # Store the screenshot in database
        pending_approvals.update_one(
            {"_id": pending_payment["_id"]},
            {"$set": {"screenshot_id": message.photo.file_id}}
        )
        
        # Format the payment ID as a string
        payment_id_str = str(pending_payment["_id"])
        
        # Log important information
        logger.info(f"Processing payment screenshot from user {user_id}, payment ID: {payment_id_str}")
        print(f"Payment screenshot received: user={user_id}, payment_id={payment_id_str}")
        
        # Handle admin notification with admin_notification helper
        admin_notified = await admin_notification(
            client,
            f"🔄 Payment Verification Request\n\n"
                f"User: {message.from_user.mention} (ID: {user_id})\n"
                f"Country: {pending_payment['country'].upper()}\n"
                f"Plan: {pending_payment['plan'].capitalize()}\n"
                f"Number: {pending_payment.get('reserved_number', 'Not assigned')}\n"
                f"Payment ID: {payment_id_str}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Approve", 
                        callback_data=f"approve_{user_id}_{payment_id_str}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", 
                        callback_data=f"reject_{user_id}_{payment_id_str}"
                    )
                ]
            ])
        )
        
        if not admin_notified:
            # Log the failure
            logger.error(f"Failed to notify admin about payment {payment_id_str}")
            print(f"Admin notification failed for payment {payment_id_str}")
            
            # Update status to indicate admin notification failure
            pending_approvals.update_one(
                {"_id": pending_payment["_id"]},
                {"$set": {
                    "admin_action": "notification_failed",
                    "admin_error": "Failed to notify admin"
                }}
            )
            
            await message.reply_text(
                "⚠️ We're having trouble processing your payment.\n"
                "Please contact admin for assistance."
            )
            return
        
        # Also send the screenshot to admin
        try:
            await client.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo.file_id,
                caption=f"📷 Payment screenshot from user {user_id}\nPayment ID: {payment_id_str}"
            )
            logger.info(f"Payment screenshot forwarded to admin")
            
            # Send success message only after everything is successful
            await message.reply_text(
                "✅ Screenshot received!\n"
                "Admin will verify your payment shortly."
            )
            
        except Exception as e:
            logger.error(f"Failed to forward screenshot to admin: {e}")
            print(f"Failed to forward screenshot to admin: {e}")
            # Send error message only if admin notification fails
            await message.reply_text(
                "❌ Failed to process screenshot. Please try again or contact admin."
            )
        
    except Exception as e:
        logger.error(f"Screenshot handling error: {e}")
        print(f"Screenshot handling error: {e}")
        # Send error message only for general errors
        await message.reply_text(
            "❌ Failed to process screenshot. Please try again or contact admin."
        )

@user_bot.on_callback_query(filters.regex("^(approve|reject)_"))
async def handle_admin_approval(client, callback_query):
    try:
        # Log the callback data
        print(f"Admin approval callback received: {callback_query.data}")
        logger.info(f"Admin approval callback received: {callback_query.data}")
        
        # Split the callback data
        parts = callback_query.data.split('_')
        if len(parts) < 3:
            await callback_query.answer("Invalid callback data format!", show_alert=True)
            return
            
        action = parts[0]
        user_id = int(parts[1])
        payment_id = '_'.join(parts[2:])  # Combine all remaining parts in case ObjectId contains underscores
        
        print(f"Parsed callback data: action={action}, user_id={user_id}, payment_id={payment_id}")
        
        # Try to convert to ObjectId
        try:
            payment_oid = ObjectId(payment_id)
        except Exception as e:
            print(f"Error converting payment_id to ObjectId: {e}")
            await callback_query.answer(f"Invalid payment ID format: {payment_id}", show_alert=True)
            return
            
        # Find the payment
        payment = pending_approvals.find_one({
            "_id": payment_oid,
            "user_id": user_id
        })
        
        if not payment:
            # Try logging the payment we're looking for
            print(f"Payment not found: _id={payment_oid}, user_id={user_id}")
            try:
                # Check if payment exists at all
                payment_exists = pending_approvals.find_one({"_id": payment_oid})
                if payment_exists:
                    print(f"Payment exists but with different user_id: {payment_exists.get('user_id')}")
                else:
                    print(f"No payment with _id={payment_oid} exists")
                    
                # Check if user has any pending payments
                user_payments = list(pending_approvals.find({"user_id": user_id}))
                print(f"User {user_id} has {len(user_payments)} payments in database")
            except Exception as e:
                print(f"Error when searching for payment: {e}")
                
            await callback_query.answer("Payment not found or already processed!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment not found or already processed\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        # Check if payment has already been processed
        if payment.get("admin_action") != "pending":
            await callback_query.answer(f"Payment already {payment.get('admin_action')}!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment already processed ({payment.get('admin_action')})\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        if action == "approve":
            print(f"Approving payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "approved",
                    "admin_action": "approved",
                    "approved_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment in database")
                await callback_query.answer("Failed to update payment!", show_alert=True)
                return
                
            # Assign the number to the user
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                # Check if this number has a session string in the database
                number_data = numbers_inventory.find_one({"phone_number": reserved_number})
                
                if number_data and number_data.get("session_string"):
                    # Number already has a session string, mark as sold
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now()
                        }}
                    )
                    
                    # Start monitoring for OTP immediately
                    success = await start_monitoring_for_otp(reserved_number, user_id)
                    
                    # Send success message to user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"OTP monitoring is {('active' if success else 'not active')}.\n"
                                 f"Use this number to sign in to Telegram, and we'll send you the OTP.",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔢 New Number", callback_data="buy_number")],
                                [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                            ])
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
                else:
                    # No session string found - admin needs to add it
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now(),
                            "needs_session": True
                        }}
                    )
                    
                    # Notify admin that session is needed
                    await admin_notification(
                        client,
                        f"⚠️ Session string needed!\n\n"
                        f"Number: {reserved_number}\n"
                        f"Sold to: {user_id}\n\n"
                        f"Please add a session string for this number using the command:\n"
                        f"/addsession {reserved_number} SESSION_STRING"
                    )
                    
                    # Notify user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"Our admin is preparing this number for you. You'll be notified when it's ready to use."
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
            
            await callback_query.answer("Payment approved!")
            await callback_query.message.edit_text(
                f"✅ Approved payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}\n\n"
                f"Status: Sold"
            )
            
        else:  # Rejection
            print(f"Rejecting payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "rejected",
                    "admin_action": "rejected",
                    "rejected_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment rejection in database")
                await callback_query.answer("Failed to reject payment!", show_alert=True)
                return
            
            # Return the number to available status
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                numbers_inventory.update_one(
                    {"phone_number": reserved_number},
                    {"$set": {"status": "available", "reserved_for": None}}
                )
                
            try:
                await client.send_message(
                    chat_id=user_id,
                    text="❌ Payment Rejected\n\n"
                         "Your payment could not be verified.\n"
                         f"Contact {ADMIN_USERNAME} if this is a mistake.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                    ])
                )
                print(f"Sent rejection notification to user {user_id}")
            except Exception as e:
                print(f"Failed to notify user about rejected payment: {e}")
                logger.error(f"Failed to notify user about rejected payment: {e}")
                
            await callback_query.answer("Payment rejected!")
            await callback_query.message.edit_text(
                f"❌ Rejected payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}"
            )
            
    except Exception as e:
        print(f"Error in admin approval callback: {e}")
        logger.error(f"Error in admin approval: {e}")
        await callback_query.answer(f"Error processing approval: {str(e)}", show_alert=True)

async def monitor_session_files():
    while True:
        try:
            pending_orders = pending_approvals.find({
                "status": "awaiting_session"
            }).sort("timestamp", pymongo.ASCENDING)
            
            for order in pending_orders:
                for filename in os.listdir("sessions"):
                    if filename.endswith(".session"):
                        phone_number, _ = get_otp_from_session(filename[:-8])
                        
                        if phone_number:
                            pending_approvals.update_one(
                                {"_id": order["_id"]},
                                {"$set": {
                                    "status": "awaiting_otp",
                                    "number": phone_number,
                                    "session_file": filename
                                }}
                            )
                            
                            try:
                                await user_bot.send_message(
                                    chat_id=order["user_id"],
                                    text=f"🔢 Number Ready: {phone_number}\n\n"
                                         f"Please:\n"
                                         f"1. Login to Telegram using this number\n"
                                         f"2. Send the OTP you receive\n\n"
                                         f"Your OTP will automatically appear here once sent.",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("✅ I've Sent OTP", callback_data=f"check_otp_{phone_number}")]
                                    ])
                                )
                                os.remove(f"sessions/{filename}")
                                break
                            except Exception as e:
                                print(f"Error notifying user: {e}")
            
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Session monitor error: {e}")
            await asyncio.sleep(30)

@user_bot.on_callback_query(filters.regex("^check_otp_"))
async def check_otp_handler(client, callback_query):
    try:
        phone_number = callback_query.data.split('_')[2]
        _, otp = get_otp_from_session(phone_number)
        
        if not otp:
            await callback_query.answer("OTP not found yet! Try again.", show_alert=True)
            return
            
        await asyncio.sleep(2)
        
        await client.send_message(
            chat_id=callback_query.from_user.id,
            text=f"✅ OTP Received: {otp}\n\n"
                 "Complete login within 2 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👍 Login Successful", callback_data="login_success")],
                [InlineKeyboardButton("🆘 Help", callback_data="support")]
            ])
        )
        
        pending_approvals.update_one(
            {"user_id": callback_query.from_user.id, "status": "awaiting_otp"},
            {"$set": {"status": "otp_delivered", "otp": otp}}
        )
        
        await callback_query.answer("OTP sent!")
        
    except Exception as e:
        print(f"OTP check error: {e}")
        await callback_query.answer("Error fetching OTP", show_alert=True)

@user_bot.on_callback_query(filters.regex("^login_success$"))
async def handle_login_success(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🎉 Thank you for your order!\n\n"
        "Your number is now ready for use.\n\n"
        "Start a new conversation with /start when you need another number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔄 New Order", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^support$"))
async def handle_support(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🆘 Support\n\n"
        f"Contact admin directly: {ADMIN_USERNAME}\n"
        "Include your order details for faster response.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^recharge$"))
async def handle_recharge(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "💰 Recharge Your Wallet\n\n"
        f"Send money to:\n"
        f"UPI: `{UPI_ID}`\n"
        f"Binance ID: {BINANCE_ID}\n\n"
        "After payment, send a screenshot with caption: #recharge",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^check_balance$"))
async def handle_check_balance(client, callback_query):
    user_id = callback_query.from_user.id
    user_data = users.find_one({"user_id": user_id})
    balance = user_data.get("wallet", 0) if user_data else 0
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Your Wallet Balance\n\n"
        f"Current Balance: ₹{balance}\n\n"
        f"Use the recharge option to add funds.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_whatsapp$"))
async def whatsapp_service(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 WhatsApp Service\n\n"
        "WhatsApp virtual numbers will be available soon!\n\n"
        "Please check back later or contact support for updates.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

# --- Admin Command Handlers ---
#@user_bot.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    """Admin panel with management options"""
    if str(message.from_user.id) not in ADMIN_USER_IDS and str(message.from_user.id) != ADMIN_ID:
        await message.reply_text("⛔️ You are not authorized to use this command.")
        return

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

@user_bot.on_callback_query(filters.regex("^admin_manage_orders$"))
async def admin_manage_orders(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    orders_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Pending Orders", callback_data="admin_pending_orders"),
            InlineKeyboardButton("✅ Completed Orders", callback_data="admin_completed_orders")
        ],
        [
            InlineKeyboardButton("💰 Sales Report", callback_data="admin_sales_report"),
            InlineKeyboardButton("📈 Revenue Stats", callback_data="admin_revenue_stats")
        ],
        [
            InlineKeyboardButton("👥 Customer List", callback_data="admin_customer_list"),
            InlineKeyboardButton("📋 Order History", callback_data="admin_order_history")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📊 **Orders & Sales**\n\n"
        "Manage orders and view sales information:",
        reply_markup=orders_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_settings$"))
async def admin_settings(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    settings_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Payment Settings", callback_data="admin_payment_settings"),
            InlineKeyboardButton("🔔 Notification Settings", callback_data="admin_notification_settings")
        ],
        [
            InlineKeyboardButton("⚡ Performance Settings", callback_data="admin_performance_settings"),
            InlineKeyboardButton("🔒 Security Settings", callback_data="admin_security_settings")
        ],
        [
            InlineKeyboardButton("📱 Bot Settings", callback_data="admin_bot_settings"),
            InlineKeyboardButton("🔄 Backup & Restore", callback_data="admin_backup_restore")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "⚙️ **Settings**\n\n"
        "Configure bot settings and preferences:",
        reply_markup=settings_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_reports$"))
async def admin_reports(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    reports_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Daily Report", callback_data="admin_daily_report"),
            InlineKeyboardButton("📈 Weekly Report", callback_data="admin_weekly_report")
        ],
        [
            InlineKeyboardButton("📉 Monthly Report", callback_data="admin_monthly_report"),
            InlineKeyboardButton("📋 Custom Report", callback_data="admin_custom_report")
        ],
        [
            InlineKeyboardButton("📱 System Status", callback_data="admin_system_status"),
            InlineKeyboardButton("⚠️ Error Logs", callback_data="admin_error_logs")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📋 **Reports**\n\n"
        "View various reports and system information:",
        reply_markup=reports_markup
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
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "🔑 Session Management\n\n"
        "Please select an option:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^admin_import_session$"))
async def admin_import_session_menu(client, callback_query):
    """Show menu for importing session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"import_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📥 Import Session\n\n"
        "Select a number to import session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^import_session_"))
async def handle_import_session_button(client, callback_query):
    """Handle import session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("import_session_", "")
    
    # Store the phone number in user state
    user_states[callback_query.from_user.id] = {
        "action": "import_session",
        "phone": phone
    }
    
    await callback_query.message.edit_text(
        f"📥 Import Session\n\n"
        f"Please enter the session string for {phone}:\n\n"
        f"Example: 1BQANOTEzrHE...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_export_session$"))
async def admin_export_session_menu(client, callback_query):
    """Show menu for exporting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"export_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📤 Export Session\n\n"
        "Select a number to export session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^export_session_"))
async def handle_export_session_button(client, callback_query):
    """Handle export session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("export_session_", "")
    
    # Get the session string from the database
    number = numbers_inventory.find_one({"phone": phone})
    if not number:
        await callback_query.answer("❌ Number not found in inventory.", show_alert=True)
        return
    
    session_string = number.get("session_string")
    if not session_string:
        await callback_query.answer("❌ No session string found for this number.", show_alert=True)
        return
    
    # Send the session string
    await callback_query.message.reply_text(
        f"📤 Session String for {phone}:\n\n"
        f"`{session_string}`\n\n"
        f"⚠️ Keep this session string secure and don't share it with anyone!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_export_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_delete_session$"))
async def admin_delete_session_menu(client, callback_query):
    """Show menu for deleting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"delete_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "❌ Delete Session\n\n"
        "Select a number to delete session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^delete_session_"))
async def handle_delete_session_button(client, callback_query):
    """Handle delete session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("delete_session_", "")
    
    # Update the database to remove the session string
    result = numbers_inventory.update_one(
        {"phone": phone},
        {"$unset": {"session_string": ""}}
    )
    
    if result.modified_count > 0:
        await callback_query.answer("✅ Session deleted successfully!", show_alert=True)
    else:
        await callback_query.answer("❌ No session found for this number.", show_alert=True)
    
    # Go back to session management menu
    await admin_session_management(client, callback_query)

def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

@user_bot.on_callback_query(filters.regex("^session_login_number$"))
async def session_login_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "📱 **Login New Number**\n\n"
        "To login a Telegram number, use the command:\n"
        "/loginnumber phone_number\n\n"
        "Example: /loginnumber +917012345678\n\n"
        "You'll receive a verification code on that number which you'll need to enter.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_import$"))
async def session_import(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 **Import Session**\n\n"
        "To import a session string for a number, use the command:\n"
        "/addsession phone_number session_string\n\n"
        "Example: /addsession +917012345678 1BQANOTEzrHE...\n\n"
        "The system will validate the session and start OTP monitoring if the number is sold.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_export$"))
async def session_export(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔑 **Export Session**\n\n"
        "To export a session string for a number, use the command:\n"
        "/exportstring phone_number\n\n"
        "Example: /exportstring +917012345678\n\n"
        "This will generate a session string that can be used with Telethon.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_delete$"))
async def session_delete(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "❌ **Delete Session**\n\n"
        "To delete a session for a number, use the command:\n"
        "/deletesession phone_number\n\n"
        "Example: /deletesession +917012345678\n\n"
        "This will remove the session from the database and delete any session files.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_status$"))
async def session_status(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get numbers with sessions
    numbers_with_sessions = list(numbers_inventory.find({
        "session_string": {"$exists": True}
    }))
    
    if not numbers_with_sessions:
        await safe_edit_message(
            callback_query.message,
            "📋 **Session Status**\n\n"
            "No numbers with active sessions found.\n\n"
            "Use the Login Number or Import Session options to add sessions.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
            ])
        )
        return
    
    # Create status message
    status_text = "📋 **Session Status**\n\n"
    
    for number in numbers_with_sessions:
        phone = number.get("phone_number", "Unknown")
        is_authorized = "✅ Authorized" if number.get("is_authorized") else "❌ Not authorized"
        is_monitoring = "✅ Active" if number.get("otp_monitoring_active") else "❌ Inactive"
        status = number.get("status", "unknown")
        sold_to = number.get("sold_to", "N/A")
        
        status_text += f"📱 **{phone}**\n"
        status_text += f"Status: {status.capitalize()}\n"
        status_text += f"Authorization: {is_authorized}\n"
        status_text += f"Monitoring: {is_monitoring}\n"
        if status == "sold":
            status_text += f"Sold to: {sold_to}\n"
        status_text += "\n"
    
    await safe_edit_message(
        callback_query.message,
        status_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_message(filters.private & filters.reply & filters.incoming)
async def handle_admin_input(client, message):
    user_id = message.from_user.id
    message_text = message.text if message.text else "No text"
    print(f"Admin input received: {message_text} from user: {user_id}")
    
    # Check if user is admin
    if not is_admin(user_id):
        print(f"User {user_id} is not admin, ignoring message")
        return
    
    # Get user data from database
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        print(f"No user data found for user {user_id}")
        users.insert_one({"user_id": user_id, "wallet": 0})
        user_data = users.find_one({"user_id": user_id})
        if not user_data:
            print("Failed to create user data")
            return
        print(f"Created new user data for {user_id}")
    
    print(f"User data: {user_data}")
    
    # Check if admin is in the process of logging in a number
    if "temp_login" in user_data and user_data["temp_login"].get("step") == "awaiting_code":
        print(f"Processing OTP code input: {message_text}")
        # Handle OTP code input for phone login
        try:
            phone_number = user_data["temp_login"]["phone_number"]
            code = message.text.strip()
            
            # Validate code format (basic check)
            if not re.match(r'^\d{5}$', code):
                print(f"Invalid OTP format: {code}")
                await message.reply_text(
                    "⚠️ Invalid code format. Please enter a 5-digit code.\n"
                    "Example: 12345"
                )
                return
            
            print(f"Valid OTP format, attempting to sign in with {phone_number} and code {code}")
            
            # Get client for this phone
            session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
            memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
            await client.connect()
            
            # Sign in with the provided code
            await client.sign_in(phone_number, code)
            print(f"Successfully signed in with {phone_number}")
            
            # Export the session as a string
            string_session = StringSession.save(client.session)
            print(f"Exported session string for {phone_number}")
            
            # Update the database
            update_result = numbers_inventory.update_one(
                {"phone_number": phone_number},
                {"$set": {
                    "session_string": string_session,
                    "session_added_at": datetime.now(),
                    "is_authorized": True
                }}
            )
            print(f"Database update result: {update_result.modified_count} document(s) modified")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            print(f"Cleared temp_login data for user {user_id}")
            
            # Disconnect this temporary client
            await client.disconnect()
            
            # If the number is sold, start monitoring
            number_data = numbers_inventory.find_one({"phone_number": phone_number})
            if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
                user_to_monitor = number_data.get("sold_to")
                print(f"Starting OTP monitoring for number {phone_number} for user {user_to_monitor}")
                success = await start_monitoring_for_otp(phone_number, user_to_monitor)
                monitoring_status = f"OTP monitoring: {'✅ Started' if success else '❌ Failed to start'}"
                
                # Notify the user if monitoring started successfully
                if success:
                    try:
                        await user_bot.send_message(
                            chat_id=user_to_monitor,
                            text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                 f"You can now use this number to sign in to Telegram.\n"
                                 f"When you request an OTP code, it will be automatically sent to you here."
                        )
                        print(f"User {user_to_monitor} notified about active number {phone_number}")
                    except Exception as e:
                        logger.error(f"Failed to notify user about active number: {e}")
                        print(f"Failed to notify user {user_to_monitor}: {e}")
            else:
                monitoring_status = "Number not sold yet, no monitoring started"
                print(f"No monitoring needed for {phone_number} as it's not sold yet")
            
            await message.reply_text(
                f"✅ Successfully logged in to {phone_number}!\n\n"
                f"Session string has been saved to the database.\n"
                f"{monitoring_status}\n\n"
                f"You can now use this number with the OTP service."
            )
            
        except Exception as e:
            logger.error(f"Error in login verification: {str(e)}")
            print(f"Error in login verification: {str(e)}")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            
            await message.reply_text(f"❌ Login error: {str(e)}")
        
        # We've handled the admin input, so return
        return
    
    # Check if admin is in the process of adding a number
    if "temp_add_number" in user_data and user_data["temp_add_number"].get("step") == "enter_phone":
        print(f"Processing phone number input: {message_text}")
        
        # Get the phone number from the message
        phone_number = message.text.strip()
        
        # Validate phone number format (basic validation)
        if not re.match(r'^\+\d{10,15}$', phone_number):
            print(f"Invalid phone number format: {phone_number}")
            await message.reply_text(
                "⚠️ Invalid phone number format. Please use international format:\n"
                "+COUNTRYCODE NUMBER (e.g. +917012345678)"
            )
            return
        
        # Get country and plan from stored data
        country_code = user_data["temp_add_number"]["country"]
        plan_type = user_data["temp_add_number"]["plan"]
        
        # Check if number already exists
        existing_number = numbers_inventory.find_one({"phone_number": phone_number})
        if existing_number:
            print(f"Number {phone_number} already exists in inventory")
            await message.reply_text(
                f"⚠️ Number {phone_number} is already in the inventory."
            )
            return
        
        # Add to inventory
        number_data = {
            "phone_number": phone_number,
            "country": country_code,
            "plan": plan_type,
            "status": "available",
            "added_at": datetime.now(),
            "added_by": user_id
        }
        
        try:
            insert_result = numbers_inventory.insert_one(number_data)
            print(f"Number added to inventory with ID: {insert_result.inserted_id}")
            
            # Clear the temp data
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_add_number": ""}}
            )
            print(f"Cleared temp_add_number data for user {user_id}")
            
            # Show confirmation with options to add more or go back
            await message.reply_text(
                f"✅ Number added to inventory:\n"
                f"📱 {phone_number}\n"
                f"🌍 {country_code.upper()}\n"
                f"📋 {plan_type.capitalize()}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Another Number", callback_data="admin_add_number")],
                    [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ])
            )
            print(f"Confirmation message sent for {phone_number}")
        except Exception as e:
            print(f"Error adding number to inventory: {e}")
            await message.reply_text(f"❌ Error adding number: {str(e)}")
        return
    
    # Handle bulk add
    if "temp_bulk_add" in user_data and user_data["temp_bulk_add"].get("step") == "enter_numbers":
        print(f"Processing bulk add input with {len(message.text.strip().split('\\n'))} lines")
        # Process bulk numbers
        lines = message.text.strip().split('\n')
        added = 0
        errors = []
        
        for i, line in enumerate(lines, 1):
            parts = line.strip().split()
            if len(parts) < 3:
                error_msg = f"Line {i}: Not enough information"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            phone_number = parts[0].strip()
            country_code = parts[1].lower().strip()
            plan_type = parts[2].lower().strip()
            
            # Validate phone format
            if not re.match(r'^\+\d{10,15}$', phone_number):
                error_msg = f"Line {i}: Invalid phone format '{phone_number}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate country code
            valid_countries = ["ind", "bd", "usa", "ng", "other"]
            if country_code not in valid_countries:
                error_msg = f"Line {i}: Invalid country code '{country_code}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate plan type
            valid_plans = ["regular", "vip"]
            if plan_type not in valid_plans:
                error_msg = f"Line {i}: Invalid plan type '{plan_type}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Check if number already exists
            if numbers_inventory.find_one({"phone_number": phone_number}):
                error_msg = f"Line {i}: Number '{phone_number}' already exists"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Add to inventory
            number_data = {
                "phone_number": phone_number,
                "country": country_code,
                "plan": plan_type,
                "status": "available",
                "added_at": datetime.now(),
                "added_by": user_id
            }
            
            try:
                insert_result = numbers_inventory.insert_one(number_data)
                print(f"Added number {phone_number} with ID: {insert_result.inserted_id}")
                added += 1
            except Exception as e:
                error_msg = f"Line {i}: Database error - {str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        # Clear the temp data
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"temp_bulk_add": ""}}
        )
        print(f"Cleared temp_bulk_add data for user {user_id}")
        
        # Prepare result message
        result_message = f"✅ Added {added} numbers to inventory\n\n"
        
        if errors:
            result_message += "⚠️ Errors encountered:\n"
            for error in errors[:10]:  # Show first 10 errors
                result_message += f"- {error}\n"
            
            if len(errors) > 10:
                result_message += f"...and {len(errors) - 10} more errors\n"
        
        # Show confirmation
        await message.reply_text(
            result_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                [InlineKeyboardButton("➕ Add More Numbers", callback_data="admin_bulk_add")],
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        print(f"Bulk add completed: {added} added, {len(errors)} errors")
        return

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Number Management", callback_data="admin_number_management"),
            InlineKeyboardButton("🔐 Session Control", callback_data="admin_session_management")
        ],
        [
            InlineKeyboardButton("📶 OTP Monitoring", callback_data="admin_monitor_otp"),
            InlineKeyboardButton("📊 Orders & Sales", callback_data="admin_orders_sales")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
            InlineKeyboardButton("📋 Reports", callback_data="admin_reports")
        ]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "👨‍💼 **Admin Panel**\n\n"
        "Welcome to the admin control center. Select a category to manage:",
        reply_markup=admin_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_add_number$"))
async def admin_add_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Create markup for number type selection
    type_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Telegram Number", callback_data="add_number_type_telegram")],
        [InlineKeyboardButton("📲 WhatsApp Number", callback_data="add_number_type_whatsapp")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📱 **Select Number Type**\n\n"
        "Choose the type of number you want to add:",
        reply_markup=type_markup
    )

@user_bot.on_callback_query(filters.regex("^add_number_type_(telegram|whatsapp)$"))
async def handle_add_number_type(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    number_type = callback_query.data.split('_')[-1]
#!/usr/bin/env python
# -*- coding: utf-8 -*-

#############################################################
# TELEGRAM BOT MAIN CODE - DO NOT MODIFY DIRECTLY           #
# -------------------------------------------------------   #
# This is the main, stable version of the Telegram bot.     #
# Any changes should be tested in a development branch      #
# before being incorporated into this main version.         #
#                                                           #
# Last updated: April 2, 2025                               #
# Features:                                                 #
# - Telegram and WhatsApp number management                 #
# - OTP forwarding and monitoring                           #
# - Session management with import/export                   #
# - Admin panel with user management                        #
# - Payment processing                                      #
#############################################################

import asyncio
import json
import logging
import os
import random
import re
import requests
import shutil
import string
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import uuid
import glob
import time
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot Credentials ---
API_ID = 25733253
API_HASH = "eabb8d10c13a3a7f63b2b832be8336d6"
BOT_TOKEN = "7011527407:AAEPw2k9NYJbQNL6qpGJWrcmokLp7nq3D2w"
ADMIN_ID = "7536665814"  # Your Telegram user ID as string
ADMIN_USERNAME = "@Mr_Griffiin"  # Your Telegram username

UPI_ID = "sunnysing2632-3@okaxis"
BINANCE_ID = "1018484211"

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client["telegram_bot_new_fresh"]  # Using a new database name to avoid lock conflicts
users = db["users"]
orders = db["orders"]
pending_approvals = db["pending_approvals"]
numbers_inventory = db["numbers_inventory"]

# Initialize Pyrogram Client
# user_bot = Client(
    "number_selling_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Session management ---
# Dictionary to store active telethon clients
active_telethon_clients = {}
# Directory for storing session files
SESSIONS_DIR = "new_fresh_sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# --- Global Variables ---
telethon_user_data = {}  # Store temporary data for Telethon session generation
recent_otps = {}  # Store recent OTPs to prevent duplicates

# --- Helper Functions for OTP Management ---
async def get_telethon_client_for_number(phone_number, session_string=None):
    """
    Get or create a Telethon client for the given phone number.
    Using in-memory sessions to avoid database locks.
    
    Args:
        phone_number: The phone number to get a client for
        session_string: Optional session string to use
        
    Returns:
        TelegramClient: The client
    """
    try:
        # Check if we already have an active client for this number
        if phone_number in active_telethon_clients:
            print(f"Returning existing client for {phone_number}")
            return active_telethon_clients[phone_number]
            
        print(f"Creating new Telethon client for {phone_number}")
        
        # Create a new client using the session string or in-memory session
        if session_string:
            # Use the provided session string
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        else:
            # Always use in-memory session to avoid database locks
            memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        
        # Connect the client but don't start it yet
        await client.connect()
        
        # Check if the client is authorized
        is_authorized = await client.is_user_authorized()
        print(f"Client for {phone_number} authorized: {is_authorized}")
        
        return client
        
    except Exception as e:
        print(f"Error getting Telethon client for {phone_number}: {e}")
        logger.error(f"Error getting Telethon client for {phone_number}: {e}")
        raise

async def start_monitoring_for_otp(phone_number, user_id):
    """
    Start monitoring a phone number for Telegram OTP codes.
    
    Args:
        phone_number: The phone number to monitor
        user_id: The user to send OTP codes to
    
    Returns:
        bool: True if monitoring started successfully, False otherwise
    """
    try:
        print(f"Starting monitoring for OTP codes for {phone_number}, forwarding to user {user_id}")
        
        # Initialize recent OTPs tracker for this number
        recent_otps[phone_number] = set()
        
        # Get session string from database
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        if not number_data:
            print(f"No number found in database for {phone_number}")
            return False
            
        session_string = number_data.get("session_string")
        if not session_string:
            print(f"No session string found for {phone_number}")
            return False
            
        # Store the owner ID for later use in message forwarding
        sold_to_user = number_data.get("sold_to")
        print(f"Number {phone_number} is sold to user: {sold_to_user}")
        
        # Create and start client
        client = await get_telethon_client_for_number(phone_number, session_string)
        
        # Ensure client is logged in
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            print(f"Client for {phone_number} is not authorized")
            await client.disconnect()
            return False
        
        # Store the client in the active clients dictionary
        active_telethon_clients[phone_number] = client
        
        # Update database to indicate monitoring is active
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {"otp_monitoring_active": True}}
        )
        
        # Set up event handler for new messages
        @client.on(events.NewMessage())
        async def handle_new_message(event):
            try:
                message_text = event.message.message
                print(f"New message received on {phone_number}: {message_text}")
                
                # Check if the message is from Telegram or contains OTP code
                is_otp = False
                otp_code = None
                
                # Check if message is from Telegram
                if event.message.from_id and hasattr(event.message.from_id, 'user_id'):
                    sender_id = event.message.from_id.user_id
                    if sender_id == 777000:  # Telegram's official user ID
                        is_otp = True
                
                # Look for OTP patterns in the message
                otp_patterns = [
                    r'Telegram code (?:is|:) (\d{5})',
                    r'Your login code:? (\d{5})',
                    r'Your code:? (\d{5})',
                    r'verification code:? (\d{5})',
                    r'(\d{5}) is your Telegram code',
                    r'Login code:? (\d{5})',
                    r'[^\d](\d{5})[^\d]',
                ]
                
                for pattern in otp_patterns:
                    match = re.search(pattern, message_text)
                    if match:
                        otp_code = match.group(1)
                        is_otp = True
                        break
                
                if is_otp:
                    print(f"OTP detected: {otp_code if otp_code else 'Pattern matched but no code extracted'}")
                    
                    # Check if this is a duplicate OTP
                    if otp_code:
                        otp_key = f"{otp_code}_{int(datetime.now().timestamp()) // 300}"  # Group by 5-min window
                        
                        # Skip if we've already sent this OTP recently
                        if otp_key in recent_otps.get(phone_number, set()):
                            print(f"Skipping duplicate OTP {otp_code} for {phone_number}")
                            return
                        
                        # Add to recent OTPs
                        if phone_number not in recent_otps:
                            recent_otps[phone_number] = set()
                        recent_otps[phone_number].add(otp_key)
                        
                        # Cleanup old OTPs (keep only last 10)
                        if len(recent_otps[phone_number]) > 10:
                            recent_otps[phone_number] = set(list(recent_otps[phone_number])[-10:])
                    
                    # Format the message to send to the user
                    formatted_message = f"📲 **OTP Code Received**\n\n"
                    
                    if otp_code:
                        formatted_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        formatted_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    formatted_message += f"📱 Phone Number: `{phone_number}`\n"
                    formatted_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    formatted_message += "Enter this code in the Telegram app to complete the login."
                    
                    # Add verification completion button
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Verification Complete", callback_data=f"verify_success_{phone_number}")],
                        [InlineKeyboardButton("🔄 Get New OTP", callback_data=f"new_otp_{phone_number}")],
                        [InlineKeyboardButton("ℹ️ Help", callback_data="otp_help")]
                    ])
                    
                    # Get latest owner information from database
                    current_data = numbers_inventory.find_one({"phone_number": phone_number})
                    current_owner = current_data.get("sold_to") if current_data else None
                    
                    # 1. Send the OTP to the user who purchased the number (if sold)
                    if current_owner:
                        try:
                            await user_bot.send_message(
                                chat_id=current_owner,
                                text=formatted_message,
                                reply_markup=reply_markup
                            )
                            print(f"OTP forwarded to owner {current_owner} for number {phone_number}")
                        except Exception as e:
                            print(f"Failed to send OTP to owner {current_owner}: {e}")
                    
                    # 2. Always send the OTP to the admin
                    admin_message = f"📲 **OTP Forwarded**\n\n"
                    if otp_code:
                        admin_message += f"📟 **Code: `{otp_code}`**\n\n"
                    else:
                        admin_message += f"📝 **Original Message:**\n{message_text}\n\n"
                    
                    admin_message += f"📱 Number: `{phone_number}`\n"
                    if current_owner:
                        admin_message += f"👤 Sold to User ID: `{current_owner}`\n"
                    else:
                        admin_message += f"👤 Not sold yet\n"
                    admin_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                    
                    try:
                        await user_bot.send_message(
                            chat_id=ADMIN_ID,
                            text=admin_message
                        )
                        print(f"OTP also forwarded to admin for monitoring")
                    except Exception as e:
                        print(f"Failed to send OTP to admin: {e}")
            except Exception as e:
                print(f"Error handling message in OTP monitor: {e}")
                logger.error(f"Error handling message in OTP monitor: {e}")
        
        # Start the client properly
        print(f"Starting OTP monitoring for {phone_number}...")
        await client.start()
        print(f"✅ Successfully started OTP monitoring for {phone_number}")
        
        return True
        
    except Exception as e:
        print(f"Error starting OTP monitoring: {e}")
        logger.error(f"Error starting OTP monitoring: {e}")
        return False

# --- Helper Functions ---
def initialize_database():
    """Initialize database indexes"""
    try:
        db.pending_approvals.create_index([("user_id", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("admin_action", pymongo.ASCENDING)])
        db.pending_approvals.create_index([("timestamp", pymongo.DESCENDING)])
        print("Database indexes created")
    except Exception as e:
        print(f"Database initialization error: {e}")

async def safe_edit_message(message, text, reply_markup=None):
    """Safely edit message with error handling."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"Error editing message: {e}")

def button_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
        [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
        [InlineKeyboardButton("💳 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="support")]
    ])

def get_otp_from_session(phone_number):
    """Monitor session files for new OTPs and extract phone number"""
    session_path = f"sessions/{phone_number}.session"
    
    if not os.path.exists(session_path):
        return None, None
    
    try:
        with open(session_path, 'r') as f:
            content = f.read()
        
        # Extract phone number
        phone_match = re.search(r'phone_number\s*=\s*([\+\d]+)', content)
        phone_number = phone_match.group(1) if phone_match else None
        
        # Extract OTP
        otp_match = re.search(r'(\b\d{5}\b|\b\d{6}\b)', content)
        otp = otp_match.group(1) if otp_match else None
        
        return phone_number, otp
        
    except Exception as e:
        print(f"Error reading session file: {e}")
        return None, None

# --- Command Handlers ---
@user_bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    
    # Check if user exists, if not create a new entry
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        users.insert_one({"user_id": user_id, "wallet": 0})
        print(f"Created new user: {user_id}")
    
    # Clear any temporary user state that could cause issues
    users.update_one(
        {"user_id": user_id},
        {"$unset": {
            "temp_manual_monitor": "",
            "temp_manual_generate": "",
            "temp_add_number": "",
            "phone_auth": ""
        }}
    )
    
    # Check if message has been processed recently to prevent duplicates
    processed_key = f"start_{user_id}_{int(datetime.now().timestamp()) // 10}"  # Group by 10-second window
    if processed_key in recent_otps:
        print(f"Preventing duplicate start command processing for user {user_id}")
        return
    
    # Mark as processed
    recent_otps[processed_key] = True
    
    # Send a single welcome message
    try:
        await message.reply_text(
            "**Welcome to the Number Selling Bot!**\nChoose an option below:",
            reply_markup=button_menu()
        )
    except Exception as e:
        print(f"Error sending start message: {e}")
        
    # Clean up old processed keys (keep for 30 seconds)
    current_time = int(datetime.now().timestamp())
    old_keys = [k for k in recent_otps.keys() if k.startswith("start_") and int(k.split("_")[-1]) < (current_time // 10 - 3)]
    for k in old_keys:
        if k in recent_otps:
            del recent_otps[k]

@user_bot.on_message(filters.command("help"))
async def help_command(client, message):
    """Send help text when command /help is issued."""
    user_id = message.from_user.id
    
    # Basic help for all users
    help_text = (
        "📝 **Available Commands**\n\n"
        "/start - Start the bot and see main menu\n"
        "/mynumbers - Show numbers you have purchased\n"
        "/help - Show this help message\n"
        "/id - Get your Telegram user ID"
    )
    
    # Additional admin commands
    if is_admin(user_id):
        admin_help = (
            "\n\n👑 **Admin Commands**\n\n"
            "/admin - Access admin panel\n"
            "/listnumbers - List all numbers in inventory\n"
            "/clearinventory - Clear all inventory data\n"
            "/generateSession +PHONE - Generate a session for a number\n"
            "/addsession +PHONE SESSION - Add a session string manually\n"
            "/startmonitor +PHONE - Start OTP monitoring for a number\n"
            "/stopmonitor +PHONE - Stop OTP monitoring for a number\n"
            "/exportstring +PHONE - Export a session string\n"
            "/deletesession +PHONE - Delete a session"
        )
        help_text += admin_help
    
    await message.reply_text(help_text)

@user_bot.on_message(filters.command("mynumbers") & filters.private)
async def my_numbers_command(client, message):
    """Show user's purchased numbers"""
    user_id = message.from_user.id
    
    # Get user's purchased numbers
    user_numbers = list(numbers_inventory.find({"sold_to": user_id, "status": "sold"}))
    
    if not user_numbers:
        await message.reply_text(
            "You don't have any purchased numbers yet. Use the menu below to buy one:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Buy Number", callback_data="buy_number")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
        )
        return
    
    # Display user's numbers
    response = "Your purchased numbers:\n\n"
    
    for i, number in enumerate(user_numbers, 1):
        phone = number.get("phone_number")
        country = number.get("country", "Unknown").upper()
        plan = number.get("plan", "Regular").capitalize()
        
        # Check if number has active session
        has_session = "✅" if number.get("session_string") else "❌"
        is_monitoring = "✅" if number.get("otp_monitoring_active") else "❌"
        
        response += f"{i}. 📱 **{phone}**\n"
        response += f"   Country: {country} | Plan: {plan}\n"
        response += f"   Session: {has_session} | Monitoring: {is_monitoring}\n\n"
    
    await message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔢 Buy Another Number", callback_data="buy_number")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_message(filters.command("id") & filters.private)
async def my_id(client, message):
    """Show the user their Telegram ID"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    print(f"ID command received from {first_name} (@{username}), ID: {user_id}")
    
    await message.reply_text(
        f"Your Telegram Information:\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Name: {first_name}\n"
        f"🔤 Username: @{username}\n\n"
        f"To set yourself as admin, update the ADMIN_ID value in the bot code."
    )

# --- Callback Query Handlers ---
@user_bot.on_callback_query(filters.regex("^main_menu$"))
async def main_menu(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Welcome back! Choose an option below:**",
        reply_markup=button_menu()
    )

@user_bot.on_callback_query(filters.regex("^buy_number$"))
async def select_service(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Service:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Telegram", callback_data="buy_telegram")],
            [InlineKeyboardButton("WhatsApp", callback_data="buy_whatsapp")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_telegram$"))
async def select_country(client, callback_query):
    await safe_edit_message(
        callback_query.message,
        "**Select Country & Plan Type:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇮🇳 India (₹50)", callback_data="ind_regular"),
             InlineKeyboardButton("VIP (₹100)", callback_data="ind_vip")],
            [InlineKeyboardButton("🇧🇩 Bangladesh (₹35)", callback_data="bd_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="bd_vip")],
            [InlineKeyboardButton("🇺🇸 USA (₹50)", callback_data="usa_regular")],
            [InlineKeyboardButton("🇳🇬 Nigeria (₹35)", callback_data="ng_regular"),
             InlineKeyboardButton("VIP (₹80)", callback_data="ng_vip")],
            [InlineKeyboardButton("🌍 Other (₹35)", callback_data="other_regular")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^(ind|bd|usa|ng|other)_(regular|vip)$"))
async def handle_country_selection(client, callback_query):
    country_code = callback_query.data.split('_')[0]
    plan_type = callback_query.data.split('_')[1]
    
    prices = {
        "ind": {"regular": 50, "vip": 100},
        "bd": {"regular": 35, "vip": 80},
        "usa": {"regular": 50, "vip": 80},
        "ng": {"regular": 35, "vip": 80},
        "other": {"regular": 35, "vip": 80}
    }
    
    price = prices[country_code][plan_type]
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Payment Instructions\n\n"
        f"Country: {country_code.upper()}\n"
        f"Plan: {plan_type.capitalize()}\n"
        f"Amount: ₹{price}\n\n"
        f"Please send ₹{price} to:\n"
        f"UPI: `{UPI_ID}`\n\n"
        "After payment, click 'I Have Paid' below.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("✅ I Have Paid", callback_data=f"confirm_{country_code}_{plan_type}")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^confirm_[a-z]+_(regular|vip)$"))
async def handle_payment_confirmation(client, callback_query):
    country_code = callback_query.data.split('_')[1]
    plan_type = callback_query.data.split('_')[2]
    
    # Check if there's an available number for this country and plan
    available_number = numbers_inventory.find_one({
        "country": country_code,
        "plan": plan_type,
        "status": "available"
    })
    
    if not available_number:
        await callback_query.answer("No numbers available for this selection!", show_alert=True)
        await safe_edit_message(
            callback_query.message,
            f"⚠️ Sorry, we're out of stock for {country_code.upper()} {plan_type} numbers.\n\n"
            f"Please try a different country or plan, or contact {ADMIN_USERNAME} for assistance.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="buy_telegram")]
            ])
        )
        return
    
    await callback_query.answer()
    
    payment_data = {
        "user_id": callback_query.from_user.id,
        "username": callback_query.from_user.username,
        "country": country_code,
        "plan": plan_type,
        "status": "pending",
        "admin_action": "pending",
        "reserved_number": available_number["phone_number"],
        "timestamp": datetime.now()
    }
    result = pending_approvals.insert_one(payment_data)
    
    # Mark the number as reserved
    numbers_inventory.update_one(
        {"_id": available_number["_id"]},
        {"$set": {"status": "reserved", "reserved_for": callback_query.from_user.id}}
    )
    
    await safe_edit_message(
        callback_query.message,
        "📸 Payment Verification\n\n"
        "Please send a clear screenshot of your payment receipt.\n\n"
        "Our admin will verify it within 15-30 minutes.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"{country_code}_{plan_type}")]
        ])
    )

@user_bot.on_message(filters.photo & filters.private)
async def handle_screenshot(client, message):
    user_id = message.from_user.id
    
    pending_payment = pending_approvals.find_one(
        {"user_id": user_id, "admin_action": "pending"},
        sort=[("timestamp", pymongo.DESCENDING)]
    )
    
    if not pending_payment:
        await message.reply_text("⚠️ Please click 'I Have Paid' before sending screenshots!")
        return

    try:
        # Store the screenshot in database
        pending_approvals.update_one(
            {"_id": pending_payment["_id"]},
            {"$set": {"screenshot_id": message.photo.file_id}}
        )
        
        # Format the payment ID as a string
        payment_id_str = str(pending_payment["_id"])
        
        # Log important information
        logger.info(f"Processing payment screenshot from user {user_id}, payment ID: {payment_id_str}")
        print(f"Payment screenshot received: user={user_id}, payment_id={payment_id_str}")
        
        # Handle admin notification with admin_notification helper
        admin_notified = await admin_notification(
            client,
            f"🔄 Payment Verification Request\n\n"
                f"User: {message.from_user.mention} (ID: {user_id})\n"
                f"Country: {pending_payment['country'].upper()}\n"
                f"Plan: {pending_payment['plan'].capitalize()}\n"
                f"Number: {pending_payment.get('reserved_number', 'Not assigned')}\n"
                f"Payment ID: {payment_id_str}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Approve", 
                        callback_data=f"approve_{user_id}_{payment_id_str}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", 
                        callback_data=f"reject_{user_id}_{payment_id_str}"
                    )
                ]
            ])
        )
        
        if not admin_notified:
            # Log the failure
            logger.error(f"Failed to notify admin about payment {payment_id_str}")
            print(f"Admin notification failed for payment {payment_id_str}")
            
            # Update status to indicate admin notification failure
            pending_approvals.update_one(
                {"_id": pending_payment["_id"]},
                {"$set": {
                    "admin_action": "notification_failed",
                    "admin_error": "Failed to notify admin"
                }}
            )
            
            await message.reply_text(
                "⚠️ We're having trouble processing your payment.\n"
                "Please contact admin for assistance."
            )
            return
        
        # Also send the screenshot to admin
        try:
            await client.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo.file_id,
                caption=f"📷 Payment screenshot from user {user_id}\nPayment ID: {payment_id_str}"
            )
            logger.info(f"Payment screenshot forwarded to admin")
            
            # Send success message only after everything is successful
            await message.reply_text(
                "✅ Screenshot received!\n"
                "Admin will verify your payment shortly."
            )
            
        except Exception as e:
            logger.error(f"Failed to forward screenshot to admin: {e}")
            print(f"Failed to forward screenshot to admin: {e}")
            # Send error message only if admin notification fails
            await message.reply_text(
                "❌ Failed to process screenshot. Please try again or contact admin."
            )
        
    except Exception as e:
        logger.error(f"Screenshot handling error: {e}")
        print(f"Screenshot handling error: {e}")
        # Send error message only for general errors
        await message.reply_text(
            "❌ Failed to process screenshot. Please try again or contact admin."
        )

@user_bot.on_callback_query(filters.regex("^(approve|reject)_"))
async def handle_admin_approval(client, callback_query):
    try:
        # Log the callback data
        print(f"Admin approval callback received: {callback_query.data}")
        logger.info(f"Admin approval callback received: {callback_query.data}")
        
        # Split the callback data
        parts = callback_query.data.split('_')
        if len(parts) < 3:
            await callback_query.answer("Invalid callback data format!", show_alert=True)
            return
            
        action = parts[0]
        user_id = int(parts[1])
        payment_id = '_'.join(parts[2:])  # Combine all remaining parts in case ObjectId contains underscores
        
        print(f"Parsed callback data: action={action}, user_id={user_id}, payment_id={payment_id}")
        
        # Try to convert to ObjectId
        try:
            payment_oid = ObjectId(payment_id)
        except Exception as e:
            print(f"Error converting payment_id to ObjectId: {e}")
            await callback_query.answer(f"Invalid payment ID format: {payment_id}", show_alert=True)
            return
            
        # Find the payment
        payment = pending_approvals.find_one({
            "_id": payment_oid,
            "user_id": user_id
        })
        
        if not payment:
            # Try logging the payment we're looking for
            print(f"Payment not found: _id={payment_oid}, user_id={user_id}")
            try:
                # Check if payment exists at all
                payment_exists = pending_approvals.find_one({"_id": payment_oid})
                if payment_exists:
                    print(f"Payment exists but with different user_id: {payment_exists.get('user_id')}")
                else:
                    print(f"No payment with _id={payment_oid} exists")
                    
                # Check if user has any pending payments
                user_payments = list(pending_approvals.find({"user_id": user_id}))
                print(f"User {user_id} has {len(user_payments)} payments in database")
            except Exception as e:
                print(f"Error when searching for payment: {e}")
                
            await callback_query.answer("Payment not found or already processed!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment not found or already processed\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        # Check if payment has already been processed
        if payment.get("admin_action") != "pending":
            await callback_query.answer(f"Payment already {payment.get('admin_action')}!", show_alert=True)
            await callback_query.message.edit_text(
                f"⚠️ Payment already processed ({payment.get('admin_action')})\n"
                f"User: {user_id}\n"
                f"Payment ID: {payment_id}"
            )
            return
            
        if action == "approve":
            print(f"Approving payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "approved",
                    "admin_action": "approved",
                    "approved_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment in database")
                await callback_query.answer("Failed to update payment!", show_alert=True)
                return
                
            # Assign the number to the user
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                # Check if this number has a session string in the database
                number_data = numbers_inventory.find_one({"phone_number": reserved_number})
                
                if number_data and number_data.get("session_string"):
                    # Number already has a session string, mark as sold
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now()
                        }}
                    )
                    
                    # Start monitoring for OTP immediately
                    success = await start_monitoring_for_otp(reserved_number, user_id)
                    
                    # Send success message to user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"OTP monitoring is {('active' if success else 'not active')}.\n"
                                 f"Use this number to sign in to Telegram, and we'll send you the OTP.",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔢 New Number", callback_data="buy_number")],
                                [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                            ])
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
                else:
                    # No session string found - admin needs to add it
                    numbers_inventory.update_one(
                        {"phone_number": reserved_number},
                        {"$set": {
                            "status": "sold",
                            "sold_to": user_id,
                            "sold_at": datetime.now(),
                            "needs_session": True
                        }}
                    )
                    
                    # Notify admin that session is needed
                    await admin_notification(
                        client,
                        f"⚠️ Session string needed!\n\n"
                        f"Number: {reserved_number}\n"
                        f"Sold to: {user_id}\n\n"
                        f"Please add a session string for this number using the command:\n"
                        f"/addsession {reserved_number} SESSION_STRING"
                    )
                    
                    # Notify user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text=f"✅ Payment Approved!\n\n"
                                 f"Your payment has been verified.\n"
                                 f"Your virtual number: {reserved_number}\n\n"
                                 f"Our admin is preparing this number for you. You'll be notified when it's ready to use."
                        )
                        print(f"Sent approval notification to user {user_id}")
                    except Exception as e:
                        print(f"Failed to notify user about approved payment: {e}")
                        logger.error(f"Failed to notify user about approved payment: {e}")
            
            await callback_query.answer("Payment approved!")
            await callback_query.message.edit_text(
                f"✅ Approved payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}\n\n"
                f"Status: Sold"
            )
            
        else:  # Rejection
            print(f"Rejecting payment {payment_id} for user {user_id}")
            
            update_result = pending_approvals.update_one(
                {"_id": payment_oid},
                {"$set": {
                    "status": "rejected",
                    "admin_action": "rejected",
                    "rejected_at": datetime.now(),
                    "admin_id": callback_query.from_user.id
                }}
            )
            
            if update_result.modified_count == 0:
                print(f"Failed to update payment rejection in database")
                await callback_query.answer("Failed to reject payment!", show_alert=True)
                return
            
            # Return the number to available status
            reserved_number = payment.get("reserved_number")
            if reserved_number:
                numbers_inventory.update_one(
                    {"phone_number": reserved_number},
                    {"$set": {"status": "available", "reserved_for": None}}
                )
                
            try:
                await client.send_message(
                    chat_id=user_id,
                    text="❌ Payment Rejected\n\n"
                         "Your payment could not be verified.\n"
                         f"Contact {ADMIN_USERNAME} if this is a mistake.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
                    ])
                )
                print(f"Sent rejection notification to user {user_id}")
            except Exception as e:
                print(f"Failed to notify user about rejected payment: {e}")
                logger.error(f"Failed to notify user about rejected payment: {e}")
                
            await callback_query.answer("Payment rejected!")
            await callback_query.message.edit_text(
                f"❌ Rejected payment for user {user_id}\n"
                f"Payment ID: {payment_id}\n"
                f"Number: {reserved_number}"
            )
            
    except Exception as e:
        print(f"Error in admin approval callback: {e}")
        logger.error(f"Error in admin approval: {e}")
        await callback_query.answer(f"Error processing approval: {str(e)}", show_alert=True)

async def monitor_session_files():
    while True:
        try:
            pending_orders = pending_approvals.find({
                "status": "awaiting_session"
            }).sort("timestamp", pymongo.ASCENDING)
            
            for order in pending_orders:
                for filename in os.listdir("sessions"):
                    if filename.endswith(".session"):
                        phone_number, _ = get_otp_from_session(filename[:-8])
                        
                        if phone_number:
                            pending_approvals.update_one(
                                {"_id": order["_id"]},
                                {"$set": {
                                    "status": "awaiting_otp",
                                    "number": phone_number,
                                    "session_file": filename
                                }}
                            )
                            
                            try:
                                await user_bot.send_message(
                                    chat_id=order["user_id"],
                                    text=f"🔢 Number Ready: {phone_number}\n\n"
                                         f"Please:\n"
                                         f"1. Login to Telegram using this number\n"
                                         f"2. Send the OTP you receive\n\n"
                                         f"Your OTP will automatically appear here once sent.",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("✅ I've Sent OTP", callback_data=f"check_otp_{phone_number}")]
                                    ])
                                )
                                os.remove(f"sessions/{filename}")
                                break
                            except Exception as e:
                                print(f"Error notifying user: {e}")
            
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Session monitor error: {e}")
            await asyncio.sleep(30)

@user_bot.on_callback_query(filters.regex("^check_otp_"))
async def check_otp_handler(client, callback_query):
    try:
        phone_number = callback_query.data.split('_')[2]
        _, otp = get_otp_from_session(phone_number)
        
        if not otp:
            await callback_query.answer("OTP not found yet! Try again.", show_alert=True)
            return
            
        await asyncio.sleep(2)
        
        await client.send_message(
            chat_id=callback_query.from_user.id,
            text=f"✅ OTP Received: {otp}\n\n"
                 "Complete login within 2 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👍 Login Successful", callback_data="login_success")],
                [InlineKeyboardButton("🆘 Help", callback_data="support")]
            ])
        )
        
        pending_approvals.update_one(
            {"user_id": callback_query.from_user.id, "status": "awaiting_otp"},
            {"$set": {"status": "otp_delivered", "otp": otp}}
        )
        
        await callback_query.answer("OTP sent!")
        
    except Exception as e:
        print(f"OTP check error: {e}")
        await callback_query.answer("Error fetching OTP", show_alert=True)

@user_bot.on_callback_query(filters.regex("^login_success$"))
async def handle_login_success(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🎉 Thank you for your order!\n\n"
        "Your number is now ready for use.\n\n"
        "Start a new conversation with /start when you need another number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔄 New Order", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^support$"))
async def handle_support(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🆘 Support\n\n"
        f"Contact admin directly: {ADMIN_USERNAME}\n"
        "Include your order details for faster response.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^recharge$"))
async def handle_recharge(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "💰 Recharge Your Wallet\n\n"
        f"Send money to:\n"
        f"UPI: `{UPI_ID}`\n"
        f"Binance ID: {BINANCE_ID}\n\n"
        "After payment, send a screenshot with caption: #recharge",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi_id")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^check_balance$"))
async def handle_check_balance(client, callback_query):
    user_id = callback_query.from_user.id
    user_data = users.find_one({"user_id": user_id})
    balance = user_data.get("wallet", 0) if user_data else 0
    
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        f"💳 Your Wallet Balance\n\n"
        f"Current Balance: ₹{balance}\n\n"
        f"Use the recharge option to add funds.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^buy_whatsapp$"))
async def whatsapp_service(client, callback_query):
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 WhatsApp Service\n\n"
        "WhatsApp virtual numbers will be available soon!\n\n"
        "Please check back later or contact support for updates.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="buy_number")]
        ])
    )

# --- Admin Command Handlers ---
#@user_bot.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    """Admin panel with management options"""
    if str(message.from_user.id) not in ADMIN_USER_IDS and str(message.from_user.id) != ADMIN_ID:
        await message.reply_text("⛔️ You are not authorized to use this command.")
        return

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

@user_bot.on_callback_query(filters.regex("^admin_manage_orders$"))
async def admin_manage_orders(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    orders_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Pending Orders", callback_data="admin_pending_orders"),
            InlineKeyboardButton("✅ Completed Orders", callback_data="admin_completed_orders")
        ],
        [
            InlineKeyboardButton("💰 Sales Report", callback_data="admin_sales_report"),
            InlineKeyboardButton("📈 Revenue Stats", callback_data="admin_revenue_stats")
        ],
        [
            InlineKeyboardButton("👥 Customer List", callback_data="admin_customer_list"),
            InlineKeyboardButton("📋 Order History", callback_data="admin_order_history")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📊 **Orders & Sales**\n\n"
        "Manage orders and view sales information:",
        reply_markup=orders_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_settings$"))
async def admin_settings(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    settings_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Payment Settings", callback_data="admin_payment_settings"),
            InlineKeyboardButton("🔔 Notification Settings", callback_data="admin_notification_settings")
        ],
        [
            InlineKeyboardButton("⚡ Performance Settings", callback_data="admin_performance_settings"),
            InlineKeyboardButton("🔒 Security Settings", callback_data="admin_security_settings")
        ],
        [
            InlineKeyboardButton("📱 Bot Settings", callback_data="admin_bot_settings"),
            InlineKeyboardButton("🔄 Backup & Restore", callback_data="admin_backup_restore")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "⚙️ **Settings**\n\n"
        "Configure bot settings and preferences:",
        reply_markup=settings_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_reports$"))
async def admin_reports(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    reports_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Daily Report", callback_data="admin_daily_report"),
            InlineKeyboardButton("📈 Weekly Report", callback_data="admin_weekly_report")
        ],
        [
            InlineKeyboardButton("📉 Monthly Report", callback_data="admin_monthly_report"),
            InlineKeyboardButton("📋 Custom Report", callback_data="admin_custom_report")
        ],
        [
            InlineKeyboardButton("📱 System Status", callback_data="admin_system_status"),
            InlineKeyboardButton("⚠️ Error Logs", callback_data="admin_error_logs")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📋 **Reports**\n\n"
        "View various reports and system information:",
        reply_markup=reports_markup
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
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "🔑 Session Management\n\n"
        "Please select an option:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^admin_import_session$"))
async def admin_import_session_menu(client, callback_query):
    """Show menu for importing session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"import_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📥 Import Session\n\n"
        "Select a number to import session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^import_session_"))
async def handle_import_session_button(client, callback_query):
    """Handle import session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("import_session_", "")
    
    # Store the phone number in user state
    user_states[callback_query.from_user.id] = {
        "action": "import_session",
        "phone": phone
    }
    
    await callback_query.message.edit_text(
        f"📥 Import Session\n\n"
        f"Please enter the session string for {phone}:\n\n"
        f"Example: 1BQANOTEzrHE...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_export_session$"))
async def admin_export_session_menu(client, callback_query):
    """Show menu for exporting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"export_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📤 Export Session\n\n"
        "Select a number to export session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^export_session_"))
async def handle_export_session_button(client, callback_query):
    """Handle export session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("export_session_", "")
    
    # Get the session string from the database
    number = numbers_inventory.find_one({"phone": phone})
    if not number:
        await callback_query.answer("❌ Number not found in inventory.", show_alert=True)
        return
    
    session_string = number.get("session_string")
    if not session_string:
        await callback_query.answer("❌ No session string found for this number.", show_alert=True)
        return
    
    # Send the session string
    await callback_query.message.reply_text(
        f"📤 Session String for {phone}:\n\n"
        f"`{session_string}`\n\n"
        f"⚠️ Keep this session string secure and don't share it with anyone!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_export_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_delete_session$"))
async def admin_delete_session_menu(client, callback_query):
    """Show menu for deleting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"delete_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "❌ Delete Session\n\n"
        "Select a number to delete session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^delete_session_"))
async def handle_delete_session_button(client, callback_query):
    """Handle delete session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("delete_session_", "")
    
    # Update the database to remove the session string
    result = numbers_inventory.update_one(
        {"phone": phone},
        {"$unset": {"session_string": ""}}
    )
    
    if result.modified_count > 0:
        await callback_query.answer("✅ Session deleted successfully!", show_alert=True)
    else:
        await callback_query.answer("❌ No session found for this number.", show_alert=True)
    
    # Go back to session management menu
    await admin_session_management(client, callback_query)

def is_admin(user_id):
    """Helper function to check if a user is admin"""
    result = str(user_id) == ADMIN_ID or str(user_id) in ADMIN_USER_IDS
    print(f"Admin check: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result

@user_bot.on_callback_query(filters.regex("^session_login_number$"))
async def session_login_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "📱 **Login New Number**\n\n"
        "To login a Telegram number, use the command:\n"
        "/loginnumber phone_number\n\n"
        "Example: /loginnumber +917012345678\n\n"
        "You'll receive a verification code on that number which you'll need to enter.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_import$"))
async def session_import(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔄 **Import Session**\n\n"
        "To import a session string for a number, use the command:\n"
        "/addsession phone_number session_string\n\n"
        "Example: /addsession +917012345678 1BQANOTEzrHE...\n\n"
        "The system will validate the session and start OTP monitoring if the number is sold.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_export$"))
async def session_export(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔑 **Export Session**\n\n"
        "To export a session string for a number, use the command:\n"
        "/exportstring phone_number\n\n"
        "Example: /exportstring +917012345678\n\n"
        "This will generate a session string that can be used with Telethon.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_delete$"))
async def session_delete(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "❌ **Delete Session**\n\n"
        "To delete a session for a number, use the command:\n"
        "/deletesession phone_number\n\n"
        "Example: /deletesession +917012345678\n\n"
        "This will remove the session from the database and delete any session files.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^session_status$"))
async def session_status(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get numbers with sessions
    numbers_with_sessions = list(numbers_inventory.find({
        "session_string": {"$exists": True}
    }))
    
    if not numbers_with_sessions:
        await safe_edit_message(
            callback_query.message,
            "📋 **Session Status**\n\n"
            "No numbers with active sessions found.\n\n"
            "Use the Login Number or Import Session options to add sessions.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
            ])
        )
        return
    
    # Create status message
    status_text = "📋 **Session Status**\n\n"
    
    for number in numbers_with_sessions:
        phone = number.get("phone_number", "Unknown")
        is_authorized = "✅ Authorized" if number.get("is_authorized") else "❌ Not authorized"
        is_monitoring = "✅ Active" if number.get("otp_monitoring_active") else "❌ Inactive"
        status = number.get("status", "unknown")
        sold_to = number.get("sold_to", "N/A")
        
        status_text += f"📱 **{phone}**\n"
        status_text += f"Status: {status.capitalize()}\n"
        status_text += f"Authorization: {is_authorized}\n"
        status_text += f"Monitoring: {is_monitoring}\n"
        if status == "sold":
            status_text += f"Sold to: {sold_to}\n"
        status_text += "\n"
    
    await safe_edit_message(
        callback_query.message,
        status_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")]
        ])
    )

@user_bot.on_message(filters.private & filters.reply & filters.incoming)
async def handle_admin_input(client, message):
    user_id = message.from_user.id
    message_text = message.text if message.text else "No text"
    print(f"Admin input received: {message_text} from user: {user_id}")
    
    # Check if user is admin
    if not is_admin(user_id):
        print(f"User {user_id} is not admin, ignoring message")
        return
    
    # Get user data from database
    user_data = users.find_one({"user_id": user_id})
    if not user_data:
        print(f"No user data found for user {user_id}")
        users.insert_one({"user_id": user_id, "wallet": 0})
        user_data = users.find_one({"user_id": user_id})
        if not user_data:
            print("Failed to create user data")
            return
        print(f"Created new user data for {user_id}")
    
    print(f"User data: {user_data}")
    
    # Check if admin is in the process of logging in a number
    if "temp_login" in user_data and user_data["temp_login"].get("step") == "awaiting_code":
        print(f"Processing OTP code input: {message_text}")
        # Handle OTP code input for phone login
        try:
            phone_number = user_data["temp_login"]["phone_number"]
            code = message.text.strip()
            
            # Validate code format (basic check)
            if not re.match(r'^\d{5}$', code):
                print(f"Invalid OTP format: {code}")
                await message.reply_text(
                    "⚠️ Invalid code format. Please enter a 5-digit code.\n"
                    "Example: 12345"
                )
                return
            
            print(f"Valid OTP format, attempting to sign in with {phone_number} and code {code}")
            
            # Get client for this phone
            session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
            memory_session = StringSession()
            client = TelegramClient(memory_session, API_ID, API_HASH)
            await client.connect()
            
            # Sign in with the provided code
            await client.sign_in(phone_number, code)
            print(f"Successfully signed in with {phone_number}")
            
            # Export the session as a string
            string_session = StringSession.save(client.session)
            print(f"Exported session string for {phone_number}")
            
            # Update the database
            update_result = numbers_inventory.update_one(
                {"phone_number": phone_number},
                {"$set": {
                    "session_string": string_session,
                    "session_added_at": datetime.now(),
                    "is_authorized": True
                }}
            )
            print(f"Database update result: {update_result.modified_count} document(s) modified")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            print(f"Cleared temp_login data for user {user_id}")
            
            # Disconnect this temporary client
            await client.disconnect()
            
            # If the number is sold, start monitoring
            number_data = numbers_inventory.find_one({"phone_number": phone_number})
            if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
                user_to_monitor = number_data.get("sold_to")
                print(f"Starting OTP monitoring for number {phone_number} for user {user_to_monitor}")
                success = await start_monitoring_for_otp(phone_number, user_to_monitor)
                monitoring_status = f"OTP monitoring: {'✅ Started' if success else '❌ Failed to start'}"
                
                # Notify the user if monitoring started successfully
                if success:
                    try:
                        await user_bot.send_message(
                            chat_id=user_to_monitor,
                            text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                 f"You can now use this number to sign in to Telegram.\n"
                                 f"When you request an OTP code, it will be automatically sent to you here."
                        )
                        print(f"User {user_to_monitor} notified about active number {phone_number}")
                    except Exception as e:
                        logger.error(f"Failed to notify user about active number: {e}")
                        print(f"Failed to notify user {user_to_monitor}: {e}")
            else:
                monitoring_status = "Number not sold yet, no monitoring started"
                print(f"No monitoring needed for {phone_number} as it's not sold yet")
            
            await message.reply_text(
                f"✅ Successfully logged in to {phone_number}!\n\n"
                f"Session string has been saved to the database.\n"
                f"{monitoring_status}\n\n"
                f"You can now use this number with the OTP service."
            )
            
        except Exception as e:
            logger.error(f"Error in login verification: {str(e)}")
            print(f"Error in login verification: {str(e)}")
            
            # Clear the temporary login state
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_login": ""}}
            )
            
            await message.reply_text(f"❌ Login error: {str(e)}")
        
        # We've handled the admin input, so return
        return
    
    # Check if admin is in the process of adding a number
    if "temp_add_number" in user_data and user_data["temp_add_number"].get("step") == "enter_phone":
        print(f"Processing phone number input: {message_text}")
        
        # Get the phone number from the message
        phone_number = message.text.strip()
        
        # Validate phone number format (basic validation)
        if not re.match(r'^\+\d{10,15}$', phone_number):
            print(f"Invalid phone number format: {phone_number}")
            await message.reply_text(
                "⚠️ Invalid phone number format. Please use international format:\n"
                "+COUNTRYCODE NUMBER (e.g. +917012345678)"
            )
            return
        
        # Get country and plan from stored data
        country_code = user_data["temp_add_number"]["country"]
        plan_type = user_data["temp_add_number"]["plan"]
        
        # Check if number already exists
        existing_number = numbers_inventory.find_one({"phone_number": phone_number})
        if existing_number:
            print(f"Number {phone_number} already exists in inventory")
            await message.reply_text(
                f"⚠️ Number {phone_number} is already in the inventory."
            )
            return
        
        # Add to inventory
        number_data = {
            "phone_number": phone_number,
            "country": country_code,
            "plan": plan_type,
            "status": "available",
            "added_at": datetime.now(),
            "added_by": user_id
        }
        
        try:
            insert_result = numbers_inventory.insert_one(number_data)
            print(f"Number added to inventory with ID: {insert_result.inserted_id}")
            
            # Clear the temp data
            users.update_one(
                {"user_id": user_id},
                {"$unset": {"temp_add_number": ""}}
            )
            print(f"Cleared temp_add_number data for user {user_id}")
            
            # Show confirmation with options to add more or go back
            await message.reply_text(
                f"✅ Number added to inventory:\n"
                f"📱 {phone_number}\n"
                f"🌍 {country_code.upper()}\n"
                f"📋 {plan_type.capitalize()}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Another Number", callback_data="admin_add_number")],
                    [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ])
            )
            print(f"Confirmation message sent for {phone_number}")
        except Exception as e:
            print(f"Error adding number to inventory: {e}")
            await message.reply_text(f"❌ Error adding number: {str(e)}")
        return
    
    # Handle bulk add
    if "temp_bulk_add" in user_data and user_data["temp_bulk_add"].get("step") == "enter_numbers":
        print(f"Processing bulk add input with {len(message.text.strip().split('\\n'))} lines")
        # Process bulk numbers
        lines = message.text.strip().split('\n')
        added = 0
        errors = []
        
        for i, line in enumerate(lines, 1):
            parts = line.strip().split()
            if len(parts) < 3:
                error_msg = f"Line {i}: Not enough information"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            phone_number = parts[0].strip()
            country_code = parts[1].lower().strip()
            plan_type = parts[2].lower().strip()
            
            # Validate phone format
            if not re.match(r'^\+\d{10,15}$', phone_number):
                error_msg = f"Line {i}: Invalid phone format '{phone_number}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate country code
            valid_countries = ["ind", "bd", "usa", "ng", "other"]
            if country_code not in valid_countries:
                error_msg = f"Line {i}: Invalid country code '{country_code}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Validate plan type
            valid_plans = ["regular", "vip"]
            if plan_type not in valid_plans:
                error_msg = f"Line {i}: Invalid plan type '{plan_type}'"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Check if number already exists
            if numbers_inventory.find_one({"phone_number": phone_number}):
                error_msg = f"Line {i}: Number '{phone_number}' already exists"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Add to inventory
            number_data = {
                "phone_number": phone_number,
                "country": country_code,
                "plan": plan_type,
                "status": "available",
                "added_at": datetime.now(),
                "added_by": user_id
            }
            
            try:
                insert_result = numbers_inventory.insert_one(number_data)
                print(f"Added number {phone_number} with ID: {insert_result.inserted_id}")
                added += 1
            except Exception as e:
                error_msg = f"Line {i}: Database error - {str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        # Clear the temp data
        users.update_one(
            {"user_id": user_id},
            {"$unset": {"temp_bulk_add": ""}}
        )
        print(f"Cleared temp_bulk_add data for user {user_id}")
        
        # Prepare result message
        result_message = f"✅ Added {added} numbers to inventory\n\n"
        
        if errors:
            result_message += "⚠️ Errors encountered:\n"
            for error in errors[:10]:  # Show first 10 errors
                result_message += f"- {error}\n"
            
            if len(errors) > 10:
                result_message += f"...and {len(errors) - 10} more errors\n"
        
        # Show confirmation
        await message.reply_text(
            result_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Inventory", callback_data="admin_view_numbers")],
                [InlineKeyboardButton("➕ Add More Numbers", callback_data="admin_bulk_add")],
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        print(f"Bulk add completed: {added} added, {len(errors)} errors")
        return

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Number Management", callback_data="admin_number_management"),
            InlineKeyboardButton("🔐 Session Control", callback_data="admin_session_management")
        ],
        [
            InlineKeyboardButton("📶 OTP Monitoring", callback_data="admin_monitor_otp"),
            InlineKeyboardButton("📊 Orders & Sales", callback_data="admin_orders_sales")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
            InlineKeyboardButton("📋 Reports", callback_data="admin_reports")
        ]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "👨‍💼 **Admin Panel**\n\n"
        "Welcome to the admin control center. Select a category to manage:",
        reply_markup=admin_markup
    )

@user_bot.on_callback_query(filters.regex("^admin_add_number$"))
async def admin_add_number(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Create markup for number type selection
    type_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Telegram Number", callback_data="add_number_type_telegram")],
        [InlineKeyboardButton("📲 WhatsApp Number", callback_data="add_number_type_whatsapp")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "📱 **Select Number Type**\n\n"
        "Choose the type of number you want to add:",
        reply_markup=type_markup
    )

@user_bot.on_callback_query(filters.regex("^add_number_type_(telegram|whatsapp)$"))
async def handle_add_number_type(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    number_type = callback_query.data.split('_')[-1]
    
    # Store the number type in user data
    user_id = callback_query.from_user.id
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "temp_add_number": {
                "number_type": number_type,
                "step": "select_country"
            }
        }},
        upsert=True
    )
    
    # Create markup for country selection
    country_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇳 India", callback_data=f"add_number_{number_type}_ind")],
        [InlineKeyboardButton("🇧🇩 Bangladesh", callback_data=f"add_number_{number_type}_bd")],
        [InlineKeyboardButton("🇺🇸 USA", callback_data=f"add_number_{number_type}_usa")],
        [InlineKeyboardButton("🇳🇬 Nigeria", callback_data=f"add_number_{number_type}_ng")],
        [InlineKeyboardButton("🌍 Other", callback_data=f"add_number_{number_type}_other")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_add_number")]
    ])
    
    type_display = "Telegram" if number_type == "telegram" else "WhatsApp"
    
    await safe_edit_message(
        callback_query.message,
        f"🌍 **Select Country for New {type_display} Number**\n\n"
        f"Choose the country for the {type_display} number you want to add:",
        reply_markup=country_markup
    )

@user_bot.on_callback_query(filters.regex("^add_number_(telegram|whatsapp)_(ind|bd|usa|ng|other)$"))
async def handle_add_number_country(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    number_type = callback_query.data.split('_')[2]
    country_code = callback_query.data.split('_')[3]
    
    country_names = {
        "ind": "India",
        "bd": "Bangladesh",
        "usa": "USA",
        "ng": "Nigeria",
        "other": "Other"
    }
    
    # Update user data with country
    user_id = callback_query.from_user.id
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "temp_add_number.country": country_code
        }}
    )
    
    # Create markup for plan selection
    plan_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Regular", callback_data=f"add_number_{number_type}_{country_code}_regular")],
        [InlineKeyboardButton("VIP", callback_data=f"add_number_{number_type}_{country_code}_vip")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"add_number_type_{number_type}")]
    ])
    
    type_display = "Telegram" if number_type == "telegram" else "WhatsApp"
    
    await safe_edit_message(
        callback_query.message,
        f"📋 **Select Plan for {country_names[country_code]} {type_display} Number**\n\n"
        f"Choose the plan type for the {type_display} number:",
        reply_markup=plan_markup
    )

@user_bot.on_callback_query(filters.regex("^add_number_(telegram|whatsapp)_(ind|bd|usa|ng|other)_(regular|vip)$"))
async def handle_add_number_plan(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    _, _, number_type, country_code, plan_type = callback_query.data.split('_')
    
    # Store the country and plan in user data for the next step
    user_id = callback_query.from_user.id
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "temp_add_number": {
                "number_type": number_type,
                "country": country_code,
                "plan": plan_type,
                "step": "enter_phone"
            }
        }},
        upsert=True
    )
    
    type_display = "Telegram" if number_type == "telegram" else "WhatsApp"
    
    await safe_edit_message(
        callback_query.message,
        f"📱 **Add New {type_display} Number**\n\n"
        f"Please send the {type_display} number in international format.\n"
        f"Example: +917012345678\n\n"
        f"Number Type: {type_display}\n"
        f"Country: {country_code.upper()}\n"
        f"Plan: {plan_type.capitalize()}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"add_number_{number_type}_{country_code}")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_view_numbers$"))
async def admin_view_numbers(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get all numbers from inventory
    numbers = list(numbers_inventory.find())
    
    if not numbers:
        await safe_edit_message(
            callback_query.message,
            "📋 **Inventory Status**\n\n"
            "No numbers in inventory.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        return
    
    # Group numbers by type, country and plan
    inventory_status = {}
    for number in numbers:
        country = number.get("country", "unknown").upper()
        plan = number.get("plan", "unknown").capitalize()
        status = number.get("status", "unknown")
        number_type = number.get("number_type", "telegram").capitalize()
        
        # Create nested dictionaries if they don't exist
        if number_type not in inventory_status:
            inventory_status[number_type] = {}
        if country not in inventory_status[number_type]:
            inventory_status[number_type][country] = {}
        if plan not in inventory_status[number_type][country]:
            inventory_status[number_type][country][plan] = {"available": 0, "reserved": 0, "sold": 0}
        
        # Increment the count for this combination
        inventory_status[number_type][country][plan][status] += 1
    
    # Create status message
    status_message = "📋 **Inventory Status**\n\n"
    
    # First display Telegram numbers
    if "Telegram" in inventory_status:
        status_message += "📱 **Telegram Numbers**\n\n"
        for country in sorted(inventory_status["Telegram"].keys()):
            status_message += f"**{country}**\n"
            for plan in sorted(inventory_status["Telegram"][country].keys()):
                stats = inventory_status["Telegram"][country][plan]
                status_message += f"  • {plan}: {stats['available']} available, {stats['reserved']} reserved, {stats['sold']} sold\n"
            status_message += "\n"
    
    # Then display WhatsApp numbers
    if "Whatsapp" in inventory_status:
        status_message += "📲 **WhatsApp Numbers**\n\n"
        for country in sorted(inventory_status["Whatsapp"].keys()):
            status_message += f"**{country}**\n"
            for plan in sorted(inventory_status["Whatsapp"][country].keys()):
                stats = inventory_status["Whatsapp"][country][plan]
                status_message += f"  • {plan}: {stats['available']} available, {stats['reserved']} reserved, {stats['sold']} sold\n"
            status_message += "\n"
    
    await safe_edit_message(
        callback_query.message,
        status_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_pending_orders$"))
async def admin_pending_orders(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get pending orders
    pending_orders = list(pending_approvals.find({"admin_action": "pending"}))
    
    if not pending_orders:
        await safe_edit_message(
            callback_query.message,
            "📊 **Pending Orders**\n\n"
            "No pending orders to review.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        return
    
    # Create orders message
    orders_message = "📊 **Pending Orders**\n\n"
    for order in pending_orders:
        orders_message += f"Order ID: {order['_id']}\n"
        orders_message += f"User: {order.get('username', 'Unknown')} ({order['user_id']})\n"
        orders_message += f"Country: {order['country'].upper()}\n"
        orders_message += f"Plan: {order['plan'].capitalize()}\n"
        orders_message += f"Number: {order.get('reserved_number', 'Not assigned')}\n"
        orders_message += f"Time: {order['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    await safe_edit_message(
        callback_query.message,
        orders_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_sales_report$"))
async def admin_sales_report(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get all sold numbers
    sold_numbers = list(numbers_inventory.find({"status": "sold"}))
    
    if not sold_numbers:
        await safe_edit_message(
            callback_query.message,
            "💰 **Sales Report**\n\n"
            "No sales recorded yet.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )
        return
    
    # Calculate sales statistics
    total_sales = len(sold_numbers)
    sales_by_country = {}
    sales_by_plan = {}
    total_revenue = 0
    
    prices = {
        "in": {"regular": 35, "vip": 80},
        "us": {"regular": 50, "vip": 80},
        "ng": {"regular": 35, "vip": 80},
        "other": {"regular": 35, "vip": 80}
    }
    
    for number in sold_numbers:
        country = number.get("country", "other")
        plan = number.get("plan", "regular")
        price = prices.get(country, prices["other"])[plan]
        
        sales_by_country[country] = sales_by_country.get(country, 0) + 1
        sales_by_plan[plan] = sales_by_plan.get(plan, 0) + 1
        total_revenue += price
    
    # Create sales report message
    report_message = "💰 **Sales Report**\n\n"
    report_message += f"Total Sales: {total_sales}\n"
    report_message += f"Total Revenue: ₹{total_revenue}\n\n"
    
    report_message += "**Sales by Country**\n"
    for country, count in sorted(sales_by_country.items()):
        report_message += f"• {country.upper()}: {count} sales\n"
    
    report_message += "\n**Sales by Plan**\n"
    for plan, count in sorted(sales_by_plan.items()):
        report_message += f"• {plan.capitalize()}: {count} sales\n"
    
    await safe_edit_message(
        callback_query.message,
        report_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_bulk_add$"))
async def admin_bulk_add(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "📋 **Bulk Add Numbers**\n\n"
        "To add multiple numbers at once, use the command:\n"
        "/bulkadd country plan\n\n"
        "Example: /bulkadd in regular\n\n"
        "Then send the phone numbers, one per line.\n"
        "Example:\n"
        "+917012345678\n"
        "+917023456789\n"
        "+917034567890",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_back$"))
async def admin_back(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await admin_panel(client, callback_query.message)

async def admin_notification(client, text, reply_markup=None):
    """Helper function to notify admin with proper error handling"""
    try:
        # Make sure we have a valid admin ID
        if not ADMIN_ID or ADMIN_ID == "your_telegram_user_id":
            logger.error(f"Invalid ADMIN_ID: {ADMIN_ID}")
            return False
            
        # Log for debugging
        logger.info(f"Sending admin notification to {ADMIN_ID}")
        print(f"Sending admin notification to {ADMIN_ID}: {text[:50]}...")
        
        if reply_markup:
            await client.send_message(
                chat_id=ADMIN_ID,
                text=text,
                reply_markup=reply_markup
            )
        else:
            await client.send_message(
                chat_id=ADMIN_ID,
                text=text
            )
        logger.info(f"Admin notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")
        print(f"Failed to notify admin: {e}")
        return False

@user_bot.on_message(filters.command("exportstring") & filters.private)
async def export_session_string(client, message):
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return

@user_bot.on_message(filters.command("loginnumber") & filters.private)
async def login_number(client, message):
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return

@user_bot.on_message(filters.command("deletesession") & filters.private)
async def delete_session(client, message):
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return

@user_bot.on_message(filters.command("addsession") & filters.private)
async def add_session_string(client, message):
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ', 2)
    if len(command_parts) < 3:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/addsession phone_number session_string\n\n"
            "Example: /addsession +917206955079 1BQANOTEzrHE..."
        )
        return
    
    phone_number = command_parts[1].strip()
    session_string = command_parts[2].strip()
    
    # Validate phone number format
    if not re.match(r'^\+\d{10,15}$', phone_number):
        await message.reply_text(
            "⚠️ Invalid phone number format. Please use international format:\n"
            "Example: +917206955079"
        )
        return
    
    # Check if the number exists in the inventory
    number_data = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_data:
        await message.reply_text(
            f"⚠️ Number {phone_number} not found in inventory.\n"
            f"Please add the number first using the Add Number option."
        )
        return
    
    # Validate the session string by attempting to connect
    try:
        # Create a temporary client to validate the session
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        # Check if the session is authorized
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            await client.disconnect()
            await message.reply_text(
                f"⚠️ The provided session string is not authorized for {phone_number}.\n"
                f"Please provide a valid, authorized session string."
            )
            return
        
        # Get the actual phone number from the client for verification
        me = await client.get_me()
        client_phone = me.phone
        
        # Check if the session is for the correct phone number
        if client_phone and not phone_number.endswith(client_phone[-5:]):
            await client.disconnect()
            await message.reply_text(
                f"⚠️ The provided session string is for a different phone number.\n"
                f"Expected: {phone_number}\n"
                f"Found: {client_phone}\n\n"
                f"Please provide a session string for the correct number."
            )
            return
        
        # Disconnect the temporary client
        await client.disconnect()
        
        # Update the database with the session string
        update_result = numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {
                "session_string": session_string,
                "session_added_at": datetime.now(),
                "is_authorized": True,
                "needs_session": False
            }}
        )
        
        # Start monitoring if the number is sold
        if number_data.get("status") == "sold" and number_data.get("sold_to"):
            sold_to_user = number_data.get("sold_to")
            success = await start_monitoring_for_otp(phone_number, sold_to_user)
            
            # Notify the user
            try:
                await client.send_message(
                    chat_id=sold_to_user,
                    text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                         f"You can now use this number to sign in to Telegram.\n"
                         f"When you request an OTP code, it will be automatically sent to you here."
                )
            except Exception as e:
                print(f"Error notifying user {sold_to_user}: {e}")
            
            # Response to admin
            await message.reply_text(
                f"✅ Session added for {phone_number}\n\n"
                f"Authorization: {'✅ Authorized' if is_authorized else '❌ Not authorized'}\n"
                f"OTP Monitoring: {'✅ Started' if success else '❌ Failed to start'}\n"
                f"Sold to user: {sold_to_user}\n\n"
                f"User has been notified."
            )
        else:
            # Number is not sold yet
            await message.reply_text(
                f"✅ Session added for {phone_number}\n\n"
                f"Authorization: {'✅ Authorized' if is_authorized else '❌ Not authorized'}\n"
                f"Number is not sold yet, so OTP monitoring has not been started."
            )
        
    except Exception as e:
        print(f"Error adding session string: {e}")
        await message.reply_text(
            f"❌ Error adding session string: {str(e)}\n\n"
            f"Please check the session string and try again."
        )

@user_bot.on_callback_query(filters.regex("^verify_success_(.+)$"))
async def handle_verification_success(client, callback_query):
    """Handle user indicating verification success"""
    await callback_query.answer("Thank you for confirming!")
    
    # Extract phone number from callback data
    match = re.match(r"^verify_success_(.+)$", callback_query.data)
    if not match:
        return
    
    phone_number = match.group(1)
    user_id = callback_query.from_user.id
    
    # Clear recent OTPs for this number
    if phone_number in recent_otps:
        recent_otps[phone_number].clear()
    
    await callback_query.edit_message_text(
        f"✅ **Verification Completed**\n\n"
        f"You've confirmed that you successfully logged in with the number:\n"
        f"📱 {phone_number}\n\n"
        f"If you need to log in again, you'll receive another OTP code here."
    )

@user_bot.on_callback_query(filters.regex("^new_otp_(.+)$"))
async def handle_new_otp_request(client, callback_query):
    """Handle when user requests a new OTP code"""
    try:
        phone_number = callback_query.data.split('_')[2]
        user_id = callback_query.from_user.id
        
        await callback_query.answer("Checking for new OTP codes...")
        
        # Check if this number belongs to the user
        number_data = numbers_inventory.find_one({
            "phone_number": phone_number,
            "status": "sold",
            "sold_to": user_id
        })
        
        if not number_data:
            await callback_query.answer("You don't have access to this number", show_alert=True)
            return
        
        # Update message to indicate we're checking for new OTPs
        await safe_edit_message(
            callback_query.message,
            "🔄 Checking for new OTP codes...\n\n"
            f"Phone Number: {phone_number}\n\n"
            "Please request a new code in the Telegram app.\n"
            "When a new code is received, it will be sent to you automatically."
        )
        
    except Exception as e:
        print(f"Error handling new OTP request: {e}")
        await callback_query.answer("Error processing your request", show_alert=True)

@user_bot.on_callback_query(filters.regex("^otp_help$"))
async def handle_otp_help(client, callback_query):
    """Provide help for OTP verification"""
    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "📱 **OTP Verification Help**\n\n"
        "**What is this?**\n"
        "When you try to log in to Telegram with your virtual number, Telegram sends a verification code (OTP) to that number.\n\n"
        "**How it works:**\n"
        "1. Use your virtual number to sign in to Telegram\n"
        "2. Telegram will send an OTP code to that number\n"
        "3. Our bot captures that code and forwards it to you here\n"
        "4. Enter the code in the Telegram app to complete your login\n\n"
        "**Having issues?**\n"
        "• Make sure you entered the correct phone number\n"
        "• Try clicking 'Get New OTP' after requesting a new code\n"
        "• If you still have problems, contact support",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Back", callback_data=f"main_menu")],
            [InlineKeyboardButton("🆘 Contact Support", callback_data="support")]
        ])
    )

@user_bot.on_message(filters.command("generateSession") & filters.private)
async def generate_telethon_session(client, message):
    """Generate a new Telethon session string for a number without requiring manual authentication"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/generateSession phone_number\n\n"
            "Example: /generateSession +17875699407"
        )
        return
    
    phone_number = command_parts[1].strip()
    
    # Validate phone number format
    if not re.match(r'^\+\d{10,15}$', phone_number):
        await message.reply_text(
            "⚠️ Invalid phone number format. Please use international format:\n"
            "Example: +17875699407"
        )
        return
    
    # Check if the number exists in the inventory
    number_data = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_data:
        await message.reply_text(
            f"⚠️ Number {phone_number} not found in inventory.\n"
            f"Please add the number first using the Add Number option."
        )
        return
    
    # Send a status message
    status_message = await message.reply_text(
        f"🔄 Generating Telethon session for {phone_number}...\n"
        f"This may take a few moments."
    )
    
    try:
        # Create a new Telethon client
        session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
        memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        await client.connect()
        
        # Check if already authorized
        if await client.is_user_authorized():
            # Export the session string
            session_string = StringSession.save(client.session)
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
            
            await status_message.edit_text(
                f"✅ Session already exists for {phone_number}\n\n"
                f"Session string (first 15 chars): ```{session_string[:15]}...```\n\n"
                f"This session has been saved to the database."
            )
            
            # Start monitoring if the number is sold
            if number_data.get("status") == "sold" and number_data.get("sold_to"):
                sold_to_user = number_data.get("sold_to")
                success = await start_monitoring_for_otp(phone_number, sold_to_user)
                
                if success:
                    # Notify the user
                    try:
                        await user_bot.send_message(
                            chat_id=sold_to_user,
                            text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                f"You can use this number to sign in to Telegram.\n"
                                f"When you request an OTP code, it will be automatically sent to you here."
                        )
                    except Exception as e:
                        print(f"Error notifying user {sold_to_user}: {e}")
            
            await client.disconnect()
            return
        
        # Generate a code request
        await status_message.edit_text(
            f"🔄 Requesting authentication code for {phone_number}...\n"
            f"You will need to provide the code sent to this number or entered in the next step."
        )
        
        # Request the code
        phone_code_hash = await client.send_code_request(phone_number)
        
        # Store this information for later use
        telethon_user_data[user_id] = telethon_user_data.get(user_id, {})
        telethon_user_data[user_id]["phone_auth"] = {
            "phone_number": phone_number,
            "phone_code_hash": phone_code_hash.phone_code_hash,
            "step": "waiting_for_code"
        }
        
        # Ask the user to enter the code
        await status_message.edit_text(
            f"📱 Authentication code sent to {phone_number}\n\n"
            f"Please enter the code you received in the format:\n"
            f"/entercode 12345\n\n"
            f"Or if you need to specify a 2FA password:\n"
            f"/entercode 12345 your_password"
        )
        
    except Exception as e:
        print(f"Error generating session: {e}")
        await status_message.edit_text(
            f"❌ Error generating session for {phone_number}: {str(e)}\n\n"
            f"Please try again or use manual method."
        )

@user_bot.on_message(filters.command("entercode") & filters.private)
async def enter_auth_code(client, message):
    """Process the authentication code entered by admin for Telethon session generation"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Check if we're waiting for a code
    if user_id not in telethon_user_data or "phone_auth" not in telethon_user_data[user_id] or telethon_user_data[user_id]["phone_auth"].get("step") != "waiting_for_code":
        await message.reply_text(
            "⚠️ No pending authentication. Please start the process with /generateSession command first."
        )
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ')
    if len(command_parts) < 2:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/entercode CODE [2FA_PASSWORD]\n\n"
            "Example: /entercode 12345"
        )
        return
    
    code = command_parts[1].strip()
    password = command_parts[2].strip() if len(command_parts) > 2 else None
    
    # Get stored auth information
    auth_info = telethon_user_data[user_id]["phone_auth"]
    phone_number = auth_info["phone_number"]
    
    # Send status message
    status_message = await message.reply_text(
        f"🔄 Signing in with code {code} for {phone_number}...\n"
        f"Please wait."
    )
    
    try:
        # Create client with same session
        session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
        memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        await client.connect()
        
        # Sign in with the code
        try:
            await client.sign_in(
                phone=phone_number,
                code=code,
                phone_code_hash=auth_info["phone_code_hash"]
            )
        except SessionPasswordNeededError:
            if not password:
                # Need 2FA password but not provided
                telethon_user_data[user_id]["phone_auth"]["step"] = "waiting_for_2fa"
                await status_message.edit_text(
                    f"🔐 Two-factor authentication required for {phone_number}\n\n"
                    f"Please enter your 2FA password using:\n"
                    f"/enter2fa YOUR_PASSWORD"
                )
                await client.disconnect()
                return
            else:
                # Use the provided 2FA password
                await client.sign_in(password=password)
        
        # Successfully signed in, save the session string
        session_string = StringSession.save(client.session)
        print(f"Generated session string for {phone_number}: {session_string[:15]}...")
        await client.disconnect()
        
        # Clear auth data
        del telethon_user_data[user_id]["phone_auth"]
        
        # Update the database with the session string
        update_result = numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {
                "session_string": session_string,
                "session_added_at": datetime.now(),
                "is_authorized": True,
                "needs_session": False
            }}
        )
        
        # Get number data to check if it's sold
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        
        # Start monitoring if the number is sold
        monitoring_started = False
        if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
            sold_to_user = number_data.get("sold_to")
            monitoring_started = await start_monitoring_for_otp(phone_number, sold_to_user)
            
            # Notify the user
            try:
                await user_bot.send_message(
                    chat_id=sold_to_user,
                    text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                         f"You can use this number to sign in to Telegram.\n"
                         f"When you request an OTP code, it will be automatically sent to you here."
                )
            except Exception as e:
                print(f"Error notifying user {sold_to_user}: {e}")
        
        # Respond to admin
        await status_message.edit_text(
            f"✅ Successfully generated session for {phone_number}\n\n"
            f"Session string (first 15 chars): ```{session_string[:15]}...```\n\n"
            f"This session has been saved to the database.\n"
            f"OTP Monitoring: {'✅ Started' if monitoring_started else '❌ Not started'}\n\n"
            f"{'✅ User notified' if number_data.get('status') == 'sold' else '📝 Number not yet sold to any user'}"
        )
        
    except Exception as e:
        print(f"Error signing in with code: {e}")
        await status_message.edit_text(
            f"❌ Error signing in with code: {str(e)}\n\n"
            f"Please try again with the correct code."
        )

@user_bot.on_message(filters.command("enter2fa") & filters.private)
async def enter_2fa_password(client, message):
    """Process the 2FA password entered by admin for Telethon session generation"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Check if we're waiting for a 2FA password
    if user_id not in telethon_user_data or "phone_auth" not in telethon_user_data[user_id] or telethon_user_data[user_id]["phone_auth"].get("step") != "waiting_for_2fa":
        await message.reply_text(
            "⚠️ No pending 2FA authentication. Please start the process with /generateSession command first."
        )
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/enter2fa YOUR_PASSWORD\n\n"
            "Example: /enter2fa mysecretpassword"
        )
        return
    
    password = command_parts[1].strip()
    
    # Get stored auth information
    auth_info = telethon_user_data[user_id]["phone_auth"]
    phone_number = auth_info["phone_number"]
    
    # Send status message
    status_message = await message.reply_text(
        f"🔄 Signing in with 2FA password for {phone_number}...\n"
        f"Please wait."
    )
    
    try:
        # Create client with same session
        session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
        memory_session = StringSession()
        client = TelegramClient(memory_session, API_ID, API_HASH)
        await client.connect()
        
        # Sign in with the password
        await client.sign_in(password=password)
        
        # Successfully signed in, save the session string
        session_string = StringSession.save(client.session)
        print(f"Generated session string for {phone_number}: {session_string[:15]}...")
        await client.disconnect()
        
        # Clear auth data
        del telethon_user_data[user_id]["phone_auth"]
        
        # Update the database with the session string
        update_result = numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {
                "session_string": session_string,
                "session_added_at": datetime.now(),
                "is_authorized": True,
                "needs_session": False
            }}
        )
        
        # Get number data to check if it's sold
        number_data = numbers_inventory.find_one({"phone_number": phone_number})
        
        # Start monitoring if the number is sold
        monitoring_started = False
        if number_data and number_data.get("status") == "sold" and number_data.get("sold_to"):
            sold_to_user = number_data.get("sold_to")
            monitoring_started = await start_monitoring_for_otp(phone_number, sold_to_user)
            
            # Notify the user
            try:
                await user_bot.send_message(
                    chat_id=sold_to_user,
                    text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                         f"You can use this number to sign in to Telegram.\n"
                         f"When you request an OTP code, it will be automatically sent to you here."
                )
            except Exception as e:
                print(f"Error notifying user {sold_to_user}: {e}")
        
        # Respond to admin
        await status_message.edit_text(
            f"✅ Successfully generated session for {phone_number}\n\n"
            f"Session string (first 15 chars): ```{session_string[:15]}...```\n\n"
            f"This session has been saved to the database.\n"
            f"OTP Monitoring: {'✅ Started' if monitoring_started else '❌ Not started'}\n\n"
            f"{'✅ User notified' if number_data.get('status') == 'sold' else '📝 Number not yet sold to any user'}"
        )
        
    except Exception as e:
        print(f"Error signing in with 2FA password: {e}")
        await status_message.edit_text(
            f"❌ Error signing in with 2FA password: {str(e)}\n\n"
            f"Please try again with the correct password."
        )

@user_bot.on_message(filters.command("listnumbers") & filters.private)
async def list_all_numbers(client, message):
    """List all numbers in inventory for admin users"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Get all numbers from inventory
    all_numbers = list(numbers_inventory.find({}))
    
    if not all_numbers:
        await message.reply_text("📱 No numbers in inventory yet.")
        return
    
    # Pagination - split the numbers into chunks of 10
    chunk_size = 10
    number_chunks = [all_numbers[i:i + chunk_size] for i in range(0, len(all_numbers), chunk_size)]
    
    for i, chunk in enumerate(number_chunks):
        # Create message for each chunk
        numbers_text = f"📋 **Numbers Inventory (Page {i+1}/{len(number_chunks)})**\n\n"
        
        for number in chunk:
            phone = number.get("phone_number", "Unknown")
            country = number.get("country", "unknown").upper()
            plan = number.get("plan", "regular").capitalize()
            status = number.get("status", "unknown").capitalize()
            
            # Format status with emoji
            status_emoji = "✅" if status == "Available" else "🔄" if status == "Reserved" else "💰" if status == "Sold" else "❓"
            
            # Add session status if available
            session_status = ""
            if status == "Sold" and number.get("session_string"):
                is_authorized = "✅" if number.get("is_authorized") else "❌"
                is_monitoring = "✅" if number.get("otp_monitoring_active") else "❌"
                session_status = f"\n   Session: {is_authorized} | Monitoring: {is_monitoring}"
                
                # Add buyer info if sold
                sold_to = number.get("sold_to", "Unknown")
                sold_at = number.get("sold_at", "Unknown date")
                if isinstance(sold_at, datetime):
                    sold_at = sold_at.strftime("%Y-%m-%d %H:%M")
                    
                session_status += f"\n   Sold to: {sold_to}"
                session_status += f"\n   Date: {sold_at}"
            
            numbers_text += f"📱 **{phone}**\n"
            numbers_text += f"   Country: {country} | Plan: {plan}\n"
            numbers_text += f"   Status: {status_emoji} {status}{session_status}\n\n"
        
        # Send the chunk
        await message.reply_text(numbers_text)
        
        # Small delay between messages to avoid flooding
        if i < len(number_chunks) - 1:
            await asyncio.sleep(0.5)
            
    # Send summary after all chunks
    total = len(all_numbers)
    available = sum(1 for n in all_numbers if n.get('status') == 'available')
    reserved = sum(1 for n in all_numbers if n.get('status') == 'reserved')
    sold = sum(1 for n in all_numbers if n.get('status') == 'sold')
    
    summary_text = "📊 **Inventory Summary**\n\n"
    summary_text += f"Total Numbers: {total}\n"
    summary_text += f"Available: {available}\n"
    summary_text += f"Reserved: {reserved}\n"
    summary_text += f"Sold: {sold}"
    
    await message.reply_text(summary_text)

@user_bot.on_message(filters.command("clearinventory") & filters.private)
async def clear_inventory_data(client, message):
    """Clear inventory data for admin users"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Send confirmation message with buttons
    await message.reply_text(
        "⚠️ **DANGER: Data Deletion Warning** ⚠️\n\n"
        "You are about to delete ALL inventory data, including:\n"
        "• All numbers in inventory\n"
        "• All pending approvals\n"
        "• All Telethon sessions\n\n"
        "This action CANNOT be undone!\n\n"
        "Are you absolutely sure you want to proceed?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Clear Everything", callback_data="confirm_clear_all")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^confirm_clear_all$"))
async def confirm_clear_inventory(client, callback_query):
    """Handle confirmation to clear inventory data"""
    user_id = callback_query.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return
    
    await callback_query.answer()
    
    # Send status message
    status_message = await callback_query.message.edit_text(
        "🔄 Clearing inventory data...\n"
        "Please wait, this may take a moment."
    )
    
    try:
        # Get counts before deletion
        numbers_count = numbers_inventory.count_documents({})
        approvals_count = pending_approvals.count_documents({})
        
        # Clear MongoDB collections
        numbers_inventory.delete_many({})
        pending_approvals.delete_many({})
        
        # Remove all session files
        session_files = glob.glob(os.path.join(SESSIONS_DIR, "*.session"))
        for session_file in session_files:
            try:
                os.remove(session_file)
                print(f"Removed session file: {session_file}")
            except Exception as e:
                print(f"Error removing session file {session_file}: {e}")
        
        # Clear active telethon clients
        for phone, client in list(active_telethon_clients.items()):
            try:
                await client.disconnect()
                print(f"Disconnected client for {phone}")
            except Exception as e:
                print(f"Error disconnecting client for {phone}: {e}")
        active_telethon_clients.clear()
        
        # Update status message
        await status_message.edit_text(
            "✅ **Inventory Cleared Successfully**\n\n"
            f"Deleted {numbers_count} number records\n"
            f"Deleted {approvals_count} pending approval records\n"
            f"Removed {len(session_files)} session files\n\n"
            "Your inventory is now empty. You can add new numbers using the admin panel."
        )
        
    except Exception as e:
        print(f"Error clearing inventory: {e}")
        await status_message.edit_text(
            f"❌ Error clearing inventory: {str(e)}\n\n"
            "Some data may not have been completely cleared."
        )

@user_bot.on_callback_query(filters.regex("^cancel_clear$"))
async def cancel_clear_inventory(client, callback_query):
    """Handle cancellation of inventory clearing"""
    await callback_query.answer("Operation cancelled")
    await callback_query.message.edit_text("✅ Inventory clearing cancelled. Your data is safe.")

@user_bot.on_message(filters.command("startmonitor") & filters.private)
async def start_monitor_command(client, message):
    """Start OTP monitoring for a number manually"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/startmonitor phone_number\n\n"
            "Example: /startmonitor +917206955079"
        )
        return
    
    phone_number = command_parts[1].strip()
    
    # Validate phone number format
    if not re.match(r'^\+\d{10,15}$', phone_number):
        await message.reply_text(
            "⚠️ Invalid phone number format. Please use international format:\n"
            "Example: +917206955079"
        )
        return
    
    # Check if the number exists in the inventory
    number_data = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_data:
        await message.reply_text(
            f"⚠️ Number {phone_number} not found in inventory."
        )
        return
    
    # Check if the number has a session string
    if not number_data.get("session_string"):
        await message.reply_text(
            f"⚠️ Number {phone_number} does not have a session string.\n"
            f"Please generate a session first using /generateSession {phone_number}"
        )
        return
    
    # Check if the number is already being monitored
    if number_data.get("otp_monitoring_active"):
        await message.reply_text(
            f"ℹ️ Number {phone_number} is already being monitored.\n"
            f"To restart monitoring, first stop it with /stopmonitor {phone_number}"
        )
        return
    
    # Send status message
    status_message = await message.reply_text(
        f"🔄 Starting OTP monitoring for {phone_number}...\n"
        f"Please wait."
    )
    
    # Get user ID to forward OTPs to
    target_user_id = number_data.get("sold_to")
    if not target_user_id:
        target_user_id = user_id  # If not sold, send to admin
        await status_message.edit_text(
            f"⚠️ Number {phone_number} is not sold to any user.\n"
            f"OTP codes will be forwarded to you (admin) instead."
        )
    
    # Start monitoring
    success = await start_monitoring_for_otp(phone_number, target_user_id)
    
    if success:
        await status_message.edit_text(
            f"✅ Successfully started OTP monitoring for {phone_number}\n\n"
            f"OTP codes will be forwarded to user ID: {target_user_id}"
        )
        
        # Notify the user if it's not the admin
        if target_user_id != user_id:
            try:
                await user_bot.send_message(
                    chat_id=target_user_id,
                    text=f"🔔 OTP monitoring has been activated for your number {phone_number}.\n\n"
                        f"When you request verification codes on Telegram, they will be sent here automatically."
                )
            except Exception as e:
                print(f"Error notifying user {target_user_id}: {e}")
    else:
        await status_message.edit_text(
            f"❌ Failed to start OTP monitoring for {phone_number}.\n\n"
            f"Please check logs for details."
        )

@user_bot.on_message(filters.command("stopmonitor") & filters.private)
async def stop_monitor_command(client, message):
    """Stop OTP monitoring for a number"""
    user_id = message.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Parse command arguments
    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        await message.reply_text(
            "⚠️ Invalid format. Please use:\n"
            "/stopmonitor phone_number\n\n"
            "Example: /stopmonitor +917206955079"
        )
        return
    
    phone_number = command_parts[1].strip()
    
    # Validate phone number format
    if not re.match(r'^\+\d{10,15}$', phone_number):
        await message.reply_text(
            "⚠️ Invalid phone number format. Please use international format:\n"
            "Example: +917206955079"
        )
        return
    
    # Check if the number is being monitored
    if phone_number not in active_telethon_clients:
        await message.reply_text(
            f"ℹ️ Number {phone_number} is not currently being monitored."
        )
        return
    
    # Send status message
    status_message = await message.reply_text(
        f"🔄 Stopping OTP monitoring for {phone_number}...\n"
        f"Please wait."
    )
    
    try:
        # Disconnect the client
        client = active_telethon_clients[phone_number]
        await client.disconnect()
        del active_telethon_clients[phone_number]
        
        # Clear the OTP history for this number
        if phone_number in recent_otps:
            del recent_otps[phone_number]
        
        # Update database
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {"otp_monitoring_active": False}}
        )
        
        await status_message.edit_text(
            f"✅ Successfully stopped OTP monitoring for {phone_number}"
        )
    except Exception as e:
        print(f"Error stopping monitoring for {phone_number}: {e}")
        await status_message.edit_text(
            f"❌ Error stopping monitoring for {phone_number}: {str(e)}"
        )

@user_bot.on_callback_query(filters.regex("^approve_payment_(.+)_(.+)$"))
async def approve_payment(client, callback_query):
    """Handle admin's approval of a payment"""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Extract order ID and user ID from callback data
    match = re.match(r"^approve_payment_(.+)_(.+)$", callback_query.data)
    order_id = match.group(1) if match else None
    user_id = int(match.group(2)) if match and match.group(2).isdigit() else None
    
    if not order_id or not user_id:
        await safe_edit_message(
            callback_query.message,
            "❌ Invalid order information."
        )
        return
    
    try:
        # Get order details
        order = pending_approvals.find_one({"_id": ObjectId(order_id)})
        if not order:
            await safe_edit_message(
                callback_query.message,
                "❌ Order not found."
            )
            return
        
        # Get the reserved number
        reserved_number = order.get("reserved_number")
        if not reserved_number:
            await safe_edit_message(
                callback_query.message,
                "❌ No number associated with this order."
            )
            return
            
        # Mark the payment as approved
        pending_approvals.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "payment_status": "approved",
                "approved_at": datetime.now(),
                "approved_by": callback_query.from_user.id
            }}
        )
        
        # Update number status in inventory
        numbers_inventory.update_one(
            {"phone_number": reserved_number},
            {"$set": {
                "status": "sold",
                "sold_to": user_id,
                "sold_at": datetime.now(),
                "price_paid": order.get("amount", 0)
            }}
        )
        
        # Update the message
        await safe_edit_message(
            callback_query.message,
            f"✅ Payment approved!\n\n"
            f"User: {user_id}\n"
            f"Number: {reserved_number}\n"
            f"Amount: ${order.get('amount', 0)}\n\n"
            f"The user has been notified."
        )
        
        # Check if the number has a session string
        number_data = numbers_inventory.find_one({"phone_number": reserved_number})
        has_session = bool(number_data and number_data.get("session_string"))
        
        # Notify the user
        if has_session:
            # Start OTP monitoring for the user
            await start_monitoring_for_otp(reserved_number, user_id)
            
            await user_bot.send_message(
                chat_id=user_id,
                text=f"✅ Payment Approved!\n\n"
                     f"Your payment has been verified.\n"
                     f"Your virtual number: {reserved_number}\n"
                     f"OTP monitoring is active.\n"
                     f"Use this number to sign in to Telegram, and we'll send you the OTP."
            )
        else:
            # Notify the admin that the number needs a session
            await user_bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ Session string needed!\n\n"
                     f"Number: {reserved_number}\n"
                     f"Sold to: {user_id}\n\n"
                     f"Please add a session string for this number using the command:\n"
                     f"/addsession {reserved_number} SESSION_STRING"
            )
            
            # Notify the user that the number is being prepared
            await user_bot.send_message(
                chat_id=user_id,
                text=f"✅ Payment Approved!\n\n"
                     f"Your payment has been verified.\n"
                     f"Your virtual number: {reserved_number}\n"
                     f"Our team is preparing your number for OTP reception.\n"
                     f"We'll notify you once it's ready to use."
            )
    except Exception as e:
        print(f"Error approving payment: {e}")
        await safe_edit_message(
            callback_query.message,
            f"❌ Error approving payment: {str(e)}"
        )

@user_bot.on_callback_query(filters.regex("^copy_upi_id$"))
async def handle_copy_upi_id(client, callback_query):
    """Send the UPI ID as a separate message for easy copying"""
    await callback_query.answer("UPI ID copied to clipboard!")
    await client.send_message(
        callback_query.from_user.id,
        f"`{UPI_ID}`\n\n_👆 Tap and hold to copy the UPI ID_"
    )

@user_bot.on_message(filters.text & filters.private)
async def handle_text_input(client, message):
    """Handle text input from users"""
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        
        # Check if this is a duplicate message
        processed_key = f"{user_id}_{hash(text)}_{int(time.time() / 10)}"
        if processed_key in recent_otps:
            print(f"Preventing duplicate processing for user {user_id}")
            return
        recent_otps[processed_key] = time.time()
        
        # Clean up old processed keys
        current_time = time.time()
        for key, timestamp in list(recent_otps.items()):
            if current_time - timestamp > 60:  # Keep for 60 seconds
                del recent_otps[key]
        
        # Check if there's a pending action in user_states
        if user_id in user_states:
            state = user_states[user_id]
            
            # Handle import session
            if state.get("action") == "import_session":
                phone = state.get("phone")
                if not phone:
                    await message.reply_text("❌ No phone number found. Please try again.")
                    return
                
                session_string = text.strip()
                if not session_string:
                    await message.reply_text("❌ Please enter a valid session string.")
                    return
                
                try:
                    # Update the session string in the database
                    numbers_inventory.update_one(
                        {"phone": phone},
                        {"$set": {"session_string": session_string}}
                    )
                    
                    # Check if the number is sold and start monitoring if needed
                    number = numbers_inventory.find_one({"phone": phone})
                    if number and number.get("status") == "sold":
                        asyncio.create_task(start_otp_monitoring(phone))
                    
                    await message.reply_text(
                        f"✅ Session string imported successfully for {phone}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
                    )
                except Exception as e:
                    await message.reply_text(
                        f"❌ Error importing session string: {str(e)}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
                    )
                finally:
                    del user_states[user_id]
                return
            
            # Handle generate session manual
            elif state.get("action") == "generate_session_manual" and state.get("step") == "waiting_for_number":
                phone = text.strip()
                if not phone:
                    await message.reply_text("❌ Please enter a valid phone number.")
                    return
                
                # Check if the phone number exists in inventory
                number = numbers_inventory.find_one({"phone": phone})
                if not number:
                    # Add the number to inventory if it doesn't exist
                    numbers_inventory.insert_one({
                        "phone": phone,
                        "added_at": datetime.now(),
                        "status": "available"
                    })
                
                # Clear the user state
                del user_states[user_id]
                
                # Start the session generation process
                await generate_session(client, message, phone)
                return
            
            # Handle manual number input for OTP monitoring
            elif user_data and "temp_manual_monitor" in user_data and user_data["temp_manual_monitor"].get("step") == "waiting_for_number":
                phone_number = text.strip()
                
                # Validate phone number format
                if not re.match(r'^\+[1-9]\d{1,14}$', phone_number):
                    await message.reply_text(
                        "❌ **Invalid phone number format**\n\n"
                        "Please enter a valid phone number in international format starting with '+' followed by country code.\n"
                        "Example: +917012345678",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
                        ])
                    )
                    return
                    
                # Check if number exists in inventory
                number_data = numbers_inventory.find_one({"phone_number": phone_number})
                if not number_data:
                    await message.reply_text(
                        "❌ **Number not found**\n\n"
                        f"The number {phone_number} was not found in your inventory.\n"
                        "Please add the number first using the Add Number option.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ Add Number", callback_data="admin_add_number")],
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
                        ])
                    )
                    return
                    
                # Clear temp data
                users.update_one(
                    {"user_id": user_id},
                    {"$unset": {"temp_manual_monitor": ""}}
                )
                
                # Check if the number has a session string
                if not number_data.get("session_string"):
                    await message.reply_text(
                        f"⚠️ Number {phone_number} does not have a session string.\n"
                        f"Please generate a session first before monitoring.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔑 Generate Session", callback_data=f"generate_session_{phone_number}")],
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
                        ])
                    )
                    return
                    
                # Check if the number is already being monitored
                if number_data.get("otp_monitoring_active"):
                    await message.reply_text(
                        f"ℹ️ Number {phone_number} is already being monitored.\n"
                        f"To restart monitoring, first stop it.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⏹️ Stop Monitoring", callback_data=f"stop_monitor_{phone_number}")],
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
                        ])
                    )
                    return
                    
                # Get user ID to forward OTPs to
                target_user_id = number_data.get("sold_to")
                if not target_user_id:
                    target_user_id = user_id  # If not sold, send to admin
                    await message.reply_text(
                        f"⚠️ Number {phone_number} is not sold to any user.\n"
                        f"OTP codes will be forwarded to you (admin) instead.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Continue", callback_data=f"confirm_monitor_{phone_number}_{target_user_id}")]
                        ])
                    )
                    return
                    
                # Confirm the action
                await message.reply_text(
                    f"📶 **Start OTP Monitoring**\n\n"
                    f"Number: {phone_number}\n"
                    f"OTP codes will be forwarded to user ID: {target_user_id}\n\n"
                    f"Do you want to continue?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Yes, Start Monitoring", callback_data=f"confirm_monitor_{phone_number}_{target_user_id}")],
                        [InlineKeyboardButton("❌ No, Cancel", callback_data="admin_monitor_otp")]
                    ])
                )
                return
            
            # Handle manual number input for session generation
            elif user_data and "temp_manual_generate" in user_data and user_data["temp_manual_generate"].get("step") == "waiting_for_number":
                phone_number = text.strip()
                
                # Validate phone number format
                if not re.match(r'^\+[1-9]\d{1,14}$', phone_number):
                    await message.reply_text(
                        "❌ **Invalid phone number format**\n\n"
                        "Please enter a valid phone number in international format starting with '+' followed by country code.\n"
                        "Example: +917012345678",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_generate_session")]
                        ])
                    )
                    return
                    
                # Check if number exists in inventory
                number_details = numbers_inventory.find_one({"phone_number": phone_number})
                if not number_details:
                    await message.reply_text(
                        "❌ **Number not found**\n\n"
                        f"The number {phone_number} was not found in your inventory.\n"
                        "Please add the number first using the Add Number option.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ Add Number", callback_data="admin_add_number")],
                            [InlineKeyboardButton("🔙 Back", callback_data="admin_generate_session")]
                        ])
                    )
                    return
                    
                # Clear temp data
                users.update_one(
                    {"user_id": user_id},
                    {"$unset": {"temp_manual_generate": ""}}
                )
                
                # Check if the number already has a session
                if number_details.get("session_string"):
                    await message.reply_text(
                        "⚠️ **Session Already Exists**\n\n"
                        f"Number {phone_number} already has a session.\n"
                        "Do you want to regenerate it?",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Yes, Regenerate", callback_data=f"confirm_regenerate_{phone_number}")],
                            [InlineKeyboardButton("No, Cancel", callback_data="admin_generate_session")]
                        ])
                    )
                    return
                    
                # Proceed with session generation
                await message.reply_text(
                    f"🔑 **Generate Telethon Session**\n\n"
                    f"Ready to generate a session for {phone_number}?\n\n"
                    "You will need to provide the verification code that will be sent to this number.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Yes, Continue", callback_data=f"begin_session_{phone_number}")],
                        [InlineKeyboardButton("❌ No, Cancel", callback_data="admin_generate_session")]
                    ])
                )
                return
            
            # Check if this message is an authentication code for session generation
            elif user_data and "phone_auth" in user_data and user_data["phone_auth"].get("step") == "waiting_for_code":
                # This is a verification code for session generation
                phone_number = user_data["phone_auth"]["phone_number"]
                phone_code_hash = user_data["phone_auth"]["phone_code_hash"]
                code = text.strip()
                
                # Validate code format
                if not re.match(r'^\d{5}$', code):
                    await message.reply_text(
                        "❌ **Invalid code format**\n\n"
                        "The code should be 5 digits (e.g., 12345).\n"
                        "Please check and try again.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
                        ])
                    )
                    return
                    
                # Send status message
                status_message = await message.reply_text(
                    f"🔄 Signing in with code {code} for {phone_number}...\n"
                    f"Please wait."
                )
                
                try:
                    # Create client with same session
                    session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
                    telethon_memory_session = StringSession()
                    telethon_client = TelegramClient(telethon_memory_session, API_ID, API_HASH)
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
                            {"$set": {"phone_auth.step": "waiting_for_2fa"}}
                        )
                        
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
                                    text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                        f"You can use this number to sign in to Telegram.\n"
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
                return
            
            # Check if this is a 2FA password for session generation
            elif user_data and "phone_auth" in user_data and user_data["phone_auth"].get("step") == "waiting_for_2fa":
                phone_number = user_data["phone_auth"]["phone_number"]
                password = text.strip()
                
                # Send status message
                status_message = await message.reply_text(
                    f"🔄 Verifying 2FA password for {phone_number}...\n"
                    f"Please wait."
                )
                
                try:
                    # Create client with same session
                    session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
                    telethon_memory_session = StringSession()
                    telethon_client = TelegramClient(telethon_memory_session, API_ID, API_HASH)
                    await telethon_client.connect()
                    
                    # Sign in with the password
                    await telethon_client.sign_in(password=password)
                    
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
                                    text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                        f"You can use this number to sign in to Telegram.\n"
                                        f"When you request an OTP code, it will be automatically sent to you here."
                            )
                            except Exception as e:
                                print(f"Error notifying user {sold_to_user}: {e}")
                    
                except Exception as e:
                    print(f"Error in 2FA verification: {e}")
                    await status_message.edit_text(
                        f"❌ **Error verifying 2FA password**\n\n"
                        f"Error: {str(e)}",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Try Again", callback_data=f"generate_session_{phone_number}")],
                            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                        ])
                    )
                return
            
            # Handle phone number input for admin number adding
            elif user_data and "temp_add_number" in user_data and user_data["temp_add_number"].get("step") == "enter_phone":
                # Get the stored country and plan from user data
                country_code = user_data["temp_add_number"]["country"]
                plan_type = user_data["temp_add_number"]["plan"]
                phone_number = text.strip()
                
                # Validate phone number format
                if not re.match(r'^\+[1-9]\d{1,14}$', phone_number):
                    await message.reply_text(
                        "❌ **Invalid phone number format**\n\n"
                        "Please enter a valid phone number in international format starting with '+' followed by country code.\n"
                        "Example: +917012345678",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Back", callback_data=f"add_number_{country_code}_{plan_type}")]
                        ])
                    )
                    return
                    
                # Check if number already exists in inventory
                existing_number = numbers_inventory.find_one({"phone_number": phone_number})
                if existing_number:
                    await message.reply_text(
                        "❌ **Number already exists**\n\n"
                        "This phone number is already in your inventory.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Back", callback_data=f"add_number_{country_code}_{plan_type}")]
                        ])
                    )
                    return
                    
                # Convert country codes to full names
                country_names = {
                    "ind": "India",
                    "bd": "Bangladesh",
                    "usa": "USA",
                    "ng": "Nigeria",
                    "other": "Other"
                }
                
                # Add number to inventory
                number_type = user_data["temp_add_number"].get("number_type", "telegram")  # Default to telegram if not specified
                type_display = "Telegram" if number_type == "telegram" else "WhatsApp"
                
                numbers_inventory.insert_one({
                    "phone_number": phone_number,
                    "country": country_code,
                    "plan": plan_type,
                    "number_type": number_type,  # Add number_type field
                    "status": "available",
                    "added_by": user_id,
                    "added_at": datetime.now(),
                    "session_string": None
                })
                
                # Clear temp data
                users.update_one(
                    {"user_id": user_id},
                    {"$unset": {"temp_add_number": ""}}
                )
                
                # Send confirmation with Generate Session button
                await message.reply_text(
                    f"✅ **Number Added Successfully**\n\n"
                    f"Phone: {phone_number}\n"
                    f"Type: {type_display}\n"
                    f"Country: {country_names.get(country_code, country_code.upper())}\n"
                    f"Plan: {plan_type.capitalize()}\n"
                    f"Status: Available",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔑 Generate Session", callback_data=f"generate_session_{phone_number}")],
                        [InlineKeyboardButton("➕ Add Another Number", callback_data="admin_add_number")],
                        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                    ])
                )
                return
            
            # For all other text inputs, handle admin replies or show the main menu
            else:
                # Only handle replies for admin
                if message.reply_to_message and is_admin(user_id):
                    await handle_admin_input(client, message)
                else:
                    # For regular users, show the main menu
                    await message.reply_text(
                        "I don't understand that command. Here's the main menu:",
                        reply_markup=button_menu()
                    )
        
        # Clean up old processed keys (keep for 60 seconds)
        current_time = int(datetime.now().timestamp())
        old_keys = [k for k in recent_otps.keys() if k.startswith("text_") and int(k.split("_")[-1]) < (current_time // 10 - 6)]
        for k in old_keys:
            if k in recent_otps:
                del recent_otps[k]
                
    except Exception as e:
        print(f"Error in handle_text_input: {e}")

@user_bot.on_callback_query(filters.regex("^generate_session_"))
async def handle_generate_session_button(client, callback_query):
    user_id = callback_query.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await callback_query.answer("You don't have permission to generate sessions", show_alert=True)
        return
        
    await callback_query.answer("Starting session generation...")
    
    # Extract phone number from callback data
    phone_number = callback_query.data.replace("generate_session_", "")
    print(f"Generate session requested for number: {phone_number}")
    
    # Check if the number exists in inventory
    number_details = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_details:
        print(f"Number {phone_number} not found in inventory")
        await callback_query.message.reply_text(
            "❌ **Error**\n\n"
            f"Number {phone_number} was not found in inventory."
        )
        return
        
    # Check if the number already has a session
    if number_details.get("session_string"):
        print(f"Number {phone_number} already has a session")
        await callback_query.message.reply_text(
            "⚠️ **Session Already Exists**\n\n"
            f"Number {phone_number} already has a session.\n"
            "Do you want to regenerate it?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes, Regenerate", callback_data=f"confirm_regenerate_{phone_number}")],
                [InlineKeyboardButton("No, Cancel", callback_data="admin_back")]
            ])
        )
        return
    
    # Ask for confirmation
    await safe_edit_message(
        callback_query.message,
        f"🔑 **Generate Telethon Session**\n\n"
        f"Are you ready to generate a session for {phone_number}?\n\n"
        "You will need to provide the verification code that will be sent to this number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Continue", callback_data=f"begin_session_{phone_number}")],
            [InlineKeyboardButton("❌ No, Cancel", callback_data="admin_back")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^begin_session_"))
async def handle_begin_session(client, callback_query):
    user_id = callback_query.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await callback_query.answer("You don't have permission to generate sessions", show_alert=True)
        return
        
    await callback_query.answer()
    
    # Extract phone number from callback data
    phone_number = callback_query.data.replace("begin_session_", "")
    
    # Store the phone number in user data
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "temp_session_generation": {
                "phone_number": phone_number,
                "step": "started"
            }
        }},
        upsert=True
    )
    
    # Trigger the session generation
    await generate_session(client, callback_query.message, phone_number)

@user_bot.on_callback_query(filters.regex("^confirm_regenerate_"))
async def handle_confirm_regenerate(client, callback_query):
    user_id = callback_query.from_user.id
    
    # Check if the user is an admin
    if not is_admin(user_id):
        await callback_query.answer("You don't have permission to regenerate sessions", show_alert=True)
        return
        
    await callback_query.answer()
    
    # Extract phone number from callback data
    phone_number = callback_query.data.replace("confirm_regenerate_", "")
    
    # Store the phone number in user data
    users.update_one(
        {"user_id": user_id},
        {"$set": {
            "temp_session_generation": {
                "phone_number": phone_number,
                "step": "started"
            }
        }},
        upsert=True
    )
    
    # Trigger the session generation
    await generate_session(client, callback_query.message, phone_number, regenerate=True)

# Helper function for session generation via button interface
async def generate_session(client, message, phone_number, regenerate=False):
    """Generate a Telethon session for a number with a button-based interface"""
    user_id = message.chat.id
    
    # Check if the number exists in the inventory
    number_data = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_data:
        await message.reply_text(
            f"⚠️ Number {phone_number} not found in inventory.\n"
            f"Please add the number first using the Add Number option."
        )
        return
    
    # If regenerating, check if it currently has a session
    if regenerate and not number_data.get("session_string"):
        await message.reply_text(
            f"⚠️ Number {phone_number} does not have an existing session to regenerate."
        )
        return
    
    # Send a status message
    status_message = await message.reply_text(
        f"🔄 Generating Telethon session for {phone_number}...\n"
        f"This may take a few moments."
    )
    
    try:
        # Create a new Telethon client
        session_file = os.path.join(SESSIONS_DIR, f"{phone_number}.session")
        
        # If regenerating, remove existing session file
        if regenerate and os.path.exists(session_file):
            os.remove(session_file)
            
        telethon_memory_session = StringSession()
        telethon_client = TelegramClient(telethon_memory_session, API_ID, API_HASH)
        await telethon_client.connect()
        
        # Check if already authorized and not regenerating
        if await telethon_client.is_user_authorized() and not regenerate:
            # Export the session string
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
            
            await status_message.edit_text(
                f"✅ Session already exists for {phone_number}\n\n"
                f"Session string (first 15 chars): ```{session_string[:15]}...```\n\n"
                f"This session has been saved to the database.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ])
            )
            
            # Start monitoring if the number is sold
            if number_data.get("status") == "sold" and number_data.get("sold_to"):
                sold_to_user = number_data.get("sold_to")
                success = await start_monitoring_for_otp(phone_number, sold_to_user)
                
                if success:
                    # Notify the user
                    try:
                        await client.send_message(
                            chat_id=sold_to_user,
                            text=f"🔔 Your virtual number {phone_number} is now active!\n\n"
                                f"You can use this number to sign in to Telegram.\n"
                                f"When you request an OTP code, it will be automatically sent to you here."
                        )
                    except Exception as e:
                        print(f"Error notifying user {sold_to_user}: {e}")
            
            await telethon_client.disconnect()
            return
        
        # Generate a code request
        await status_message.edit_text(
            f"🔄 Requesting authentication code for {phone_number}...\n"
            f"You will need to provide the code sent to this number or entered in the next step."
        )
        
        # Request the code
        phone_code_hash = await telethon_client.send_code_request(phone_number)
        await telethon_client.disconnect()
        
        # Store this information for later use
        users.update_one(
            {"user_id": user_id},
            {"$set": {
                "phone_auth": {
                    "phone_number": phone_number,
                    "phone_code_hash": phone_code_hash.phone_code_hash,
                    "step": "waiting_for_code"
                }
            }}
        )
        
        # Ask the user to enter the code
        await status_message.edit_text(
            f"📱 Authentication code sent to {phone_number}\n\n"
            f"Please reply to this message with the code you received.\n\n"
            f"The code should be 5 digits (e.g., 12345).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_back")]
            ])
        )
        
    except Exception as e:
        print(f"Error generating session: {e}")
        await status_message.edit_text(
            f"❌ Error generating session for {phone_number}: {str(e)}\n\n"
            f"Please try again or use manual method.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data=f"generate_session_{phone_number}")],
                [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
            ])
        )

@user_bot.on_callback_query(filters.regex("^admin_generate_session$"))
async def admin_generate_session_menu(client, callback_query):
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get a list of numbers without sessions
    numbers_without_sessions = list(numbers_inventory.find({
        "$or": [
            {"session_string": None},
            {"session_string": {"$exists": False}}
        ]
    }).sort("added_at", -1).limit(10))
    
    numbers_with_sessions = list(numbers_inventory.find({
        "session_string": {"$exists": True, "$ne": None}
    }).sort("added_at", -1).limit(5))
    
    # Create the markup with available numbers
    buttons = []
    
    # First show numbers without sessions
    if numbers_without_sessions:
        buttons.append([InlineKeyboardButton("📱 Numbers Without Sessions:", callback_data="no_action")])
        for number in numbers_without_sessions:
            phone = number.get("phone")
            if phone:
                buttons.append([
                    InlineKeyboardButton(
                        f"📱 {phone}", 
                        callback_data=f"generate_session_{phone}"
                    )
                ])
    
    # Then show some numbers with sessions (for regeneration)
    if numbers_with_sessions:
        buttons.append([InlineKeyboardButton("📱 Numbers With Sessions (Regenerate):", callback_data="no_action")])
        for number in numbers_with_sessions:
            phone = number.get("phone") 
            if phone:
                buttons.append([
                    InlineKeyboardButton(
                        f"📱 {phone}", 
                        callback_data=f"generate_session_{phone}"
                    )
                ])
    
    # Add manual entry option and back button
    buttons.append([InlineKeyboardButton("⌨️ Enter Number Manually", callback_data="generate_session_manual")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "🔑 Generate Session\n\n"
        "Select a number to generate a session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^generate_session_manual$"))
async def admin_generate_session_manual(client, callback_query):
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return
    
    # Store the user state
    user_states[callback_query.from_user.id] = {
        "action": "generate_session_manual",
        "step": "waiting_for_number"
    }
    
    await callback_query.message.edit_text(
        "🔑 Generate Session - Manual Entry\n\n"
        "Please enter the phone number in international format:\n"
        "Example: +917012345678",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_generate_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_monitor_otp$"))
async def admin_monitor_otp_menu(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get a list of numbers with sessions that can be monitored
    numbers_with_sessions = list(numbers_inventory.find({
        "session_string": {"$exists": True, "$ne": None},
        "$or": [
            {"otp_monitoring_active": {"$exists": False}},
            {"otp_monitoring_active": False}
        ]
    }).sort("added_at", -1).limit(15))
    
    numbers_being_monitored = list(numbers_inventory.find({
        "session_string": {"$exists": True, "$ne": None},
        "otp_monitoring_active": True
    }).sort("added_at", -1).limit(5))
    
    # Create the markup with available numbers
    buttons = []
    
    # First show numbers with sessions that are not being monitored
    if numbers_with_sessions:
        buttons.append([InlineKeyboardButton("📱 Numbers Available for Monitoring:", callback_data="no_action")])
        for number in numbers_with_sessions:
            phone = number.get("phone_number")
            country = number.get("country", "").upper()
            plan = number.get("plan", "").capitalize()
            status = number.get("status", "available").capitalize()
            user_id = number.get("sold_to", "Not sold")
            
            # Format button text to show status and sold_to if applicable
            if status == "Sold" and user_id != "Not sold":
                display_text = f"{phone} ({country} - Sold to {user_id})"
            else:
                display_text = f"{phone} ({country} - {status})"
                
            buttons.append([
                InlineKeyboardButton(
                    display_text, 
                    callback_data=f"start_monitor_{phone}"
                )
            ])
    else:
        buttons.append([InlineKeyboardButton("No numbers available for monitoring", callback_data="no_action")])
    
    # Then show some numbers that are already being monitored (for stopping)
    if numbers_being_monitored:
        buttons.append([InlineKeyboardButton("📱 Numbers Being Monitored (Stop):", callback_data="no_action")])
        for number in numbers_being_monitored:
            phone = number.get("phone_number")
            country = number.get("country", "").upper()
            status = number.get("status", "available").capitalize()
            user_id = number.get("sold_to", "Not sold")
            
            # Format button text to show status and sold_to if applicable
            if status == "Sold" and user_id != "Not sold":
                display_text = f"{phone} ({country} - Sold to {user_id})"
            else:
                display_text = f"{phone} ({country} - {status})"
                
            buttons.append([
                InlineKeyboardButton(
                    f"⏹️ Stop {display_text}", 
                    callback_data=f"stop_monitor_{phone}"
                )
            ])
    
    # Add manual entry option and back button
    buttons.append([InlineKeyboardButton("⌨️ Enter Number Manually", callback_data="monitor_otp_manual")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")])
    
    await safe_edit_message(
        callback_query.message,
        "📶 **OTP Monitoring**\n\n"
        "Select a number to start or stop OTP monitoring:\n\n"
        "OTP monitoring allows you to receive verification codes sent to these numbers.\n"
        "Choose from the list or enter a number manually.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@user_bot.on_callback_query(filters.regex("^monitor_otp_manual$"))
async def admin_monitor_otp_manual(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Store that we're waiting for a manual number input
    users.update_one(
        {"user_id": callback_query.from_user.id},
        {"$set": {"temp_manual_monitor": {"step": "waiting_for_number"}}},
        upsert=True
    )
    
    await safe_edit_message(
        callback_query.message,
        "📶 **OTP Monitoring - Manual Entry**\n\n"
        "Please enter the phone number in international format.\n"
        "Example: +917012345678\n\n"
        "Reply to this message with the phone number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^start_monitor_"))
async def start_monitor_button(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer("Starting OTP monitoring...")
    
    # Extract phone number from callback data
    phone_number = callback_query.data.replace("start_monitor_", "")
    print(f"Starting OTP monitoring for number: {phone_number}")
    
    # Check if the number exists in inventory
    number_data = numbers_inventory.find_one({"phone_number": phone_number})
    if not number_data:
        print(f"Number {phone_number} not found in inventory")
        await callback_query.message.reply_text(
            "❌ **Error**\n\n"
            f"Number {phone_number} was not found in inventory."
        )
        return
        
    # Check if the number has a session string
    if not number_data.get("session_string"):
        await callback_query.message.reply_text(
            f"⚠️ Number {phone_number} does not have a session string.\n"
            f"Please generate a session first before monitoring.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Generate Session", callback_data=f"generate_session_{phone_number}")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
            ])
        )
        return
    
    # Check if the number is already being monitored
    if number_data.get("otp_monitoring_active"):
        await callback_query.message.reply_text(
            f"ℹ️ Number {phone_number} is already being monitored.\n"
            f"To restart monitoring, first stop it.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏹️ Stop Monitoring", callback_data=f"stop_monitor_{phone_number}")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
            ])
        )
        return
    
    # Get user ID to forward OTPs to
    target_user_id = number_data.get("sold_to")
    if not target_user_id:
        target_user_id = callback_query.from_user.id  # If not sold, send to admin
        await callback_query.message.reply_text(
            f"⚠️ Number {phone_number} is not sold to any user.\n"
            f"OTP codes will be forwarded to you (admin) instead.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Continue", callback_data=f"confirm_monitor_{phone_number}_{target_user_id}")]
            ])
        )
        return
    
    # Confirm the action
    await callback_query.message.reply_text(
        f"📶 **Start OTP Monitoring**\n\n"
        f"Number: {phone_number}\n"
        f"OTP codes will be forwarded to user ID: {target_user_id}\n\n"
        f"Do you want to continue?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Start Monitoring", callback_data=f"confirm_monitor_{phone_number}_{target_user_id}")],
            [InlineKeyboardButton("❌ No, Cancel", callback_data="admin_monitor_otp")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^confirm_monitor_"))
async def confirm_start_monitor(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Extract phone number and target user ID from callback data
    match = re.match(r"^confirm_monitor_(.+)_(.+)$", callback_query.data)
    if not match:
        await callback_query.message.reply_text("❌ Invalid data format.")
        return
        
    phone_number = match.group(1)
    target_user_id = int(match.group(2))
    
    # Send status message
    status_message = await callback_query.message.reply_text(
        f"🔄 Starting OTP monitoring for {phone_number}...\n"
        f"Please wait."
    )
    
    # Start monitoring
    success = await start_monitoring_for_otp(phone_number, target_user_id)
    
    if success:
        await status_message.edit_text(
            f"✅ Successfully started OTP monitoring for {phone_number}\n\n"
            f"OTP codes will be forwarded to user ID: {target_user_id}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Monitoring Menu", callback_data="admin_monitor_otp")]
            ])
        )
        
        # Notify the user if it's not the admin
        if target_user_id != callback_query.from_user.id:
            try:
                await client.send_message(
                    chat_id=target_user_id,
                    text=f"🔔 OTP monitoring has been activated for your number {phone_number}.\n\n"
                        f"When you request verification codes on Telegram, they will be sent here automatically."
                )
            except Exception as e:
                print(f"Error notifying user {target_user_id}: {e}")
    else:
        await status_message.edit_text(
            f"❌ Failed to start OTP monitoring for {phone_number}.\n\n"
            f"Please check logs for details.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Monitoring Menu", callback_data="admin_monitor_otp")]
            ])
        )

@user_bot.on_callback_query(filters.regex("^stop_monitor_"))
async def stop_monitor_button(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer("Stopping OTP monitoring...")
    
    # Extract phone number from callback data
    phone_number = callback_query.data.replace("stop_monitor_", "")
    print(f"Stopping OTP monitoring for number: {phone_number}")
    
    # Check if the number is being monitored
    if phone_number not in active_telethon_clients:
        await callback_query.message.reply_text(
            f"ℹ️ Number {phone_number} is not currently being monitored.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_monitor_otp")]
            ])
        )
        return
    
    # Send status message
    status_message = await callback_query.message.reply_text(
        f"🔄 Stopping OTP monitoring for {phone_number}...\n"
        f"Please wait."
    )
    
    try:
        # Disconnect the client
        client = active_telethon_clients[phone_number]
        await client.disconnect()
        del active_telethon_clients[phone_number]
        
        # Clear the OTP history for this number
        if phone_number in recent_otps:
            del recent_otps[phone_number]
        
        # Update database
        numbers_inventory.update_one(
            {"phone_number": phone_number},
            {"$set": {"otp_monitoring_active": False}}
        )
        
        await status_message.edit_text(
            f"✅ Successfully stopped OTP monitoring for {phone_number}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Monitoring Menu", callback_data="admin_monitor_otp")]
            ])
        )
    except Exception as e:
        print(f"Error stopping monitoring for {phone_number}: {e}")
        await status_message.edit_text(
            f"❌ Error stopping monitoring for {phone_number}: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Monitoring Menu", callback_data="admin_monitor_otp")]
            ])
        )

@user_bot.on_callback_query(filters.regex("^admin_search_numbers$"))
async def admin_search_numbers(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    await safe_edit_message(
        callback_query.message,
        "🔍 **Search Numbers**\n\n"
        "To search for numbers, use the command:\n"
        "/search [country] [plan] [status]\n\n"
        "Examples:\n"
        "/search ind regular available\n"
        "/search usa vip sold\n"
        "/search bd all pending\n\n"
        "Leave parameters empty to search all.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_number_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_inventory_stats$"))
async def admin_inventory_stats(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get inventory statistics
    total_numbers = numbers_inventory.count_documents({})
    available_numbers = numbers_inventory.count_documents({"status": "available"})
    sold_numbers = numbers_inventory.count_documents({"status": "sold"})
    reserved_numbers = numbers_inventory.count_documents({"status": "reserved"})
    
    # Get numbers by country
    country_stats = {}
    for number in numbers_inventory.find():
        country = number.get("country", "unknown").upper()
        if country not in country_stats:
            country_stats[country] = {"total": 0, "available": 0, "sold": 0, "reserved": 0}
        country_stats[country]["total"] += 1
        country_stats[country][number.get("status", "unknown")] += 1
    
    # Create stats message
    stats_message = "📊 **Inventory Statistics**\n\n"
    stats_message += f"Total Numbers: {total_numbers}\n"
    stats_message += f"Available: {available_numbers}\n"
    stats_message += f"Sold: {sold_numbers}\n"
    stats_message += f"Reserved: {reserved_numbers}\n\n"
    
    stats_message += "**By Country:**\n"
    for country, stats in sorted(country_stats.items()):
        stats_message += f"\n{country}:\n"
        stats_message += f"  • Total: {stats['total']}\n"
        stats_message += f"  • Available: {stats['available']}\n"
        stats_message += f"  • Sold: {stats['sold']}\n"
        stats_message += f"  • Reserved: {stats['reserved']}\n"
    
    await safe_edit_message(
        callback_query.message,
        stats_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_inventory_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_number_management")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_completed_orders$"))
async def admin_completed_orders(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get completed orders
    completed_orders = list(pending_approvals.find({"admin_action": "approved"}))
    
    if not completed_orders:
        await safe_edit_message(
            callback_query.message,
            "✅ **Completed Orders**\n\n"
            "No completed orders found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
            ])
        )
        return
    
    # Create orders message
    orders_message = "✅ **Completed Orders**\n\n"
    for order in completed_orders:
        orders_message += f"Order ID: {order['_id']}\n"
        orders_message += f"User: {order.get('username', 'Unknown')} ({order['user_id']})\n"
        orders_message += f"Country: {order['country'].upper()}\n"
        orders_message += f"Plan: {order['plan'].capitalize()}\n"
        orders_message += f"Number: {order.get('reserved_number', 'Not assigned')}\n"
        orders_message += f"Completed: {order['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    await safe_edit_message(
        callback_query.message,
        orders_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_revenue_stats$"))
async def admin_revenue_stats(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get revenue statistics
    total_revenue = 0
    country_revenue = {}
    plan_revenue = {"regular": 0, "vip": 0}
    
    # Calculate revenue from completed orders
    for order in pending_approvals.find({"admin_action": "approved"}):
        country = order.get("country", "unknown").upper()
        plan = order.get("plan", "unknown")
        price = prices.get(country, {}).get(plan, 0)
        
        total_revenue += price
        
        if country not in country_revenue:
            country_revenue[country] = 0
        country_revenue[country] += price
        
        if plan in plan_revenue:
            plan_revenue[plan] += price
    
    # Create revenue message
    revenue_message = "💰 **Revenue Statistics**\n\n"
    revenue_message += f"Total Revenue: ₹{total_revenue}\n\n"
    
    revenue_message += "**By Country:**\n"
    for country, revenue in sorted(country_revenue.items()):
        revenue_message += f"{country}: ₹{revenue}\n"
    
    revenue_message += "\n**By Plan:**\n"
    for plan, revenue in plan_revenue.items():
        revenue_message += f"{plan.capitalize()}: ₹{revenue}\n"
    
    await safe_edit_message(
        callback_query.message,
        revenue_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_revenue_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_customer_list$"))
async def admin_customer_list(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get unique customers from completed orders
    customers = {}
    for order in pending_approvals.find({"admin_action": "approved"}):
        user_id = order["user_id"]
        if user_id not in customers:
            customers[user_id] = {
                "username": order.get("username", "Unknown"),
                "orders": 0,
                "total_spent": 0,
                "last_order": order["timestamp"]
            }
        
        customers[user_id]["orders"] += 1
        price = prices.get(order["country"], {}).get(order["plan"], 0)
        customers[user_id]["total_spent"] += price
    
    if not customers:
        await safe_edit_message(
            callback_query.message,
            "👥 **Customer List**\n\n"
            "No customers found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
            ])
        )
        return
    
    # Create customer list message
    customer_message = "👥 **Customer List**\n\n"
    for user_id, data in customers.items():
        customer_message += f"User: {data['username']} ({user_id})\n"
        customer_message += f"Orders: {data['orders']}\n"
        customer_message += f"Total Spent: ₹{data['total_spent']}\n"
        customer_message += f"Last Order: {data['last_order'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    await safe_edit_message(
        callback_query.message,
        customer_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_order_history$"))
async def admin_order_history(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You don't have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    # Get all orders sorted by timestamp
    all_orders = list(pending_approvals.find().sort("timestamp", -1))
    
    if not all_orders:
        await safe_edit_message(
            callback_query.message,
            "📋 **Order History**\n\n"
            "No orders found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
            ])
        )
        return
    
    # Create order history message
    history_message = "📋 **Order History**\n\n"
    for order in all_orders:
        status = order.get("admin_action", "pending").capitalize()
        history_message += f"Order ID: {order['_id']}\n"
        history_message += f"User: {order.get('username', 'Unknown')} ({order['user_id']})\n"
        history_message += f"Country: {order['country'].upper()}\n"
        history_message += f"Plan: {order['plan'].capitalize()}\n"
        history_message += f"Number: {order.get('reserved_number', 'Not assigned')}\n"
        history_message += f"Status: {status}\n"
        history_message += f"Time: {order['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    await safe_edit_message(
        callback_query.message,
        history_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_orders_sales")]
        ])
    )

@user_bot.on_callback_query(filters.regex("^admin_import_session$"))
async def admin_import_session_menu(client, callback_query):
    """Show menu for importing session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"import_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📥 Import Session\n\n"
        "Select a number to import session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^import_session_"))
async def handle_import_session_button(client, callback_query):
    """Handle import session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("import_session_", "")
    
    # Store the phone number in user state
    user_states[callback_query.from_user.id] = {
        "action": "import_session",
        "phone": phone
    }
    
    await callback_query.message.edit_text(
        f"📥 Import Session\n\n"
        f"Please enter the session string for {phone}:\n\n"
        f"Example: 1BQANOTEzrHE...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_import_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_export_session$"))
async def admin_export_session_menu(client, callback_query):
    """Show menu for exporting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"export_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "📤 Export Session\n\n"
        "Select a number to export session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^export_session_"))
async def handle_export_session_button(client, callback_query):
    """Handle export session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("export_session_", "")
    
    # Get the session string from the database
    number = numbers_inventory.find_one({"phone": phone})
    if not number:
        await callback_query.answer("❌ Number not found in inventory.", show_alert=True)
        return
    
    session_string = number.get("session_string")
    if not session_string:
        await callback_query.answer("❌ No session string found for this number.", show_alert=True)
        return
    
    # Send the session string
    await callback_query.message.reply_text(
        f"📤 Session String for {phone}:\n\n"
        f"`{session_string}`\n\n"
        f"⚠️ Keep this session string secure and don't share it with anyone!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_export_session")]])
    )

@user_bot.on_callback_query(filters.regex("^admin_delete_session$"))
async def admin_delete_session_menu(client, callback_query):
    """Show menu for deleting session"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    # Get all numbers from inventory
    numbers = list(numbers_inventory.find({}))
    
    buttons = []
    for number in numbers:
        phone = number.get("phone")
        if phone:
            buttons.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"delete_session_{phone}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_session_management")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(
        "❌ Delete Session\n\n"
        "Select a number to delete session for:",
        reply_markup=keyboard
    )

@user_bot.on_callback_query(filters.regex("^delete_session_"))
async def handle_delete_session_button(client, callback_query):
    """Handle delete session button click"""
    if str(callback_query.from_user.id) not in ADMIN_USER_IDS and str(callback_query.from_user.id) != ADMIN_ID:
        await callback_query.answer("⛔️ You are not authorized to use this feature.", show_alert=True)
        return

    phone = callback_query.data.replace("delete_session_", "")
    
    # Update the database to remove the session string
    result = numbers_inventory.update_one(
        {"phone": phone},
        {"$unset": {"session_string": ""}}
    )
    
# --- Main Execution ---
if __name__ == "__main__":
    initialize_database()
    print("Bot is running...")
    
    async def run_bot():
        await user_bot.start()
        
        # Connect all existing number sessions that should be monitored
        try:
            print("Checking for active virtual numbers that need monitoring...")
            sold_numbers_cursor = numbers_inventory.find({
                "status": "sold", 
                "session_string": {"$exists": True},
                "otp_monitoring_active": {"$ne": True}
            })
            
            count = 0
            sold_numbers = list(sold_numbers_cursor)  # Convert cursor to list for async iteration
            for number in sold_numbers:
                if number.get("sold_to") and number.get("session_string"):
                    print(f"Starting monitoring for previously sold number: {number['phone_number']}")
                    success = await start_monitoring_for_otp(number['phone_number'], number['sold_to'])
                    if success:
                        count += 1
            
            print(f"Started OTP monitoring for {count} previously sold numbers")
            
            # Check for numbers that need to be logged in (have sessions but not authorized)
            print("Checking for numbers with sessions that need login...")
            session_numbers_cursor = numbers_inventory.find({
                "session_string": {"$exists": True},
                "is_authorized": {"$ne": True}
            })
            
            session_count = 0
            session_numbers = list(session_numbers_cursor)  # Convert cursor to list for async iteration
            for number in session_numbers:
                try:
                    phone = number['phone_number']
                    session = number['session_string']
                    print(f"Attempting to connect to {phone} with existing session")
                    
                    client = await get_telethon_client_for_number(phone, session)
                    is_auth = await client.is_user_authorized()
                    
                    # Update authorization status
                    numbers_inventory.update_one(
                        {"phone_number": phone},
                        {"$set": {"is_authorized": is_auth}}
                    )
                    
                    if is_auth:
                        print(f"Successfully authorized {phone}")
                        session_count += 1
                    else:
                        print(f"Session exists but not authorized for {phone}")
                except Exception as e:
                    print(f"Error checking session for {number.get('phone_number', 'unknown')}: {e}")
            
            print(f"Verified {session_count} number sessions with valid authorization")
            
        except Exception as e:
            print(f"Error starting monitoring for existing numbers: {e}")
            logger.error(f"Error starting monitoring for existing numbers: {e}")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(3600)

    try:
        print("Starting Telegram bot...")
        user_bot.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        
        # Close all active Telethon clients
        for phone, client in active_telethon_clients.items():
            try:
                client.disconnect()
                print(f"Disconnected Telethon client for {phone}")
            except:
                pass
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        print("Bot shutdown complete") 