#!/usr/bin/env python3

# Read the file
with open('/Users/divyanshchugh/Desktop/chat bot/user_bot.py', 'r') as file:
    lines = file.readlines()

# Find line with admin_revenue_stats callback
admin_revenue_stats_line = -1
for i, line in enumerate(lines):
    if '@user_bot.on_callback_query(filters.regex("^admin_revenue_stats$"))' in line:
        admin_revenue_stats_line = i
        break

if admin_revenue_stats_line == -1:
    print("Could not find admin_revenue_stats handler")
    exit(1)

# Define the admin_revenue handler code
admin_revenue_handler = [
    '@user_bot.on_callback_query(filters.regex("^admin_revenue$"))\n',
    'async def admin_revenue(client, callback_query):\n',
    '    if not is_admin(callback_query.from_user.id):\n',
    '        await callback_query.answer("You do not have permission for this action", show_alert=True)\n',
    '        return\n',
    '\n',
    '    await callback_query.answer()\n',
    '    \n',
    '    revenue_markup = InlineKeyboardMarkup([\n',
    '        [\n',
    '            InlineKeyboardButton("📊 Revenue Stats", callback_data="admin_revenue_stats"),\n',
    '            InlineKeyboardButton("📈 Sales Reports", callback_data="admin_sales_report")\n',
    '        ],\n',
    '        [\n',
    '            InlineKeyboardButton("👥 Customer Analytics", callback_data="admin_customer_list"),\n',
    '            InlineKeyboardButton("📋 Order History", callback_data="admin_order_history")\n',
    '        ],\n',
    '        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]\n',
    '    ])\n',
    '    \n',
    '    await safe_edit_message(\n',
    '        callback_query.message,\n',
    '        "💰 **Revenue & Analytics**\\n\\n"\n',
    '        "View financial data and statistics:",\n',
    '        reply_markup=revenue_markup\n',
    '    )\n',
    '\n'
]

# Insert the admin_revenue handler before admin_revenue_stats
new_lines = lines[:admin_revenue_stats_line] + admin_revenue_handler + lines[admin_revenue_stats_line:]

# Write the modified content back to the file
with open('/Users/divyanshchugh/Desktop/chat bot/user_bot.py', 'w') as file:
    file.writelines(new_lines)

print(f"Successfully inserted admin_revenue handler before line {admin_revenue_stats_line+1}") 