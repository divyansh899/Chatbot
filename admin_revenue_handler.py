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
        "💰 **Revenue & Analytics**\n\n"
        "View financial data and statistics:",
        reply_markup=revenue_markup
    ) 