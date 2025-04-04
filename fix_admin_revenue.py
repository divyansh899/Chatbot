#!/usr/bin/env python3

import re

# Read the current user_bot.py file
file_path = '/Users/divyanshchugh/Desktop/chat bot/user_bot.py'
with open(file_path, 'r') as file:
    content = file.read()

# Define the admin_revenue handler to add
handler_to_add = '''
@user_bot.on_callback_query(filters.regex("^admin_revenue$"))
async def admin_revenue(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("You do not have permission for this action", show_alert=True)
        return

    await callback_query.answer()
    
    revenue_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Revenue Stats", callback_data="admin_revenue_stats"),
            InlineKeyboardButton("📈 Sales Reports", callback_data="admin_sales_report")
        ],
        [
            InlineKeyboardButton("👥 Customer Analytics", callback_data="admin_customer_list"),
            InlineKeyboardButton("📋 Order History", callback_data="admin_order_history")
        ],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
    ])
    
    await safe_edit_message(
        callback_query.message,
        "💰 **Revenue & Analytics**\\n\\n"
        "View financial data and statistics:",
        reply_markup=revenue_markup
    )

'''

# Find the admin_revenue_stats handler and insert our new handler before it
# Using a more flexible pattern with line-by-line search
lines = content.splitlines()
pattern = "admin_revenue_stats"
found = False

for i, line in enumerate(lines):
    if "@user_bot.on_callback_query" in line and pattern in line:
        # Insert our handler before this line
        print(f"Found pattern at line {i+1}")
        lines.insert(i, handler_to_add)
        found = True
        break

if found:
    # Write the modified content back to the file
    modified_content = "\n".join(lines)
    with open(file_path, 'w') as file:
        file.write(modified_content)
    
    print("Successfully added admin_revenue handler to user_bot.py")
else:
    print("Could not find the admin_revenue_stats handler in the file") 