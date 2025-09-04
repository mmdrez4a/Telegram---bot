from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = "8214464212:AAEOK60CzwkOPerx4a37j9i2093uEppOuLk"
CHANNEL_ID = "@irantonnews"

# user_wallets dict: user_id -> list of { "address": ..., "tag": ..., "muted": False }
user_wallets = {}

# main menu
main_menu = ReplyKeyboardMarkup(
    [["📋 Wallet List", "➕ Add Wallet"]],
    resize_keyboard=True
)

# cancel menu
cancel_menu = ReplyKeyboardMarkup(
    [["❌ Cancel"]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["left", "kicked"]:
            await update.message.reply_text("❌ Please join our channel first:\nhttps://t.me/irantonnews")
            return
    except Exception:
        await update.message.reply_text("⚠️ Error checking channel membership.")
        return

    await update.message.reply_text("✅ Welcome! Please choose an option:", reply_markup=main_menu)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == "📋 Wallet List":
        await show_wallet_list(update.message, user_id)

    elif text == "➕ Add Wallet":
        await update.message.reply_text("🔹 Please send the wallet address.", reply_markup=cancel_menu)
        context.user_data["adding_wallet"] = True

    elif text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("❌ Operation canceled.", reply_markup=main_menu)

    elif context.user_data.get("adding_wallet"):
        context.user_data["new_wallet"] = text
        context.user_data["adding_wallet"] = False
        context.user_data["awaiting_tag"] = True
        await update.message.reply_text(
            "✅ Wallet address received.\n\n"
            "Now set a tag for this wallet using:\n"
            "`/settag YourName`\n\n"
            "Or cancel with `/cancel`",
            parse_mode="Markdown"
        )

async def show_wallet_list(target, user_id):
    wallets = user_wallets.get(user_id, [])
    if not wallets:
        await target.reply_text("⛔ No wallets registered yet.", reply_markup=main_menu)
        return

    buttons = [
        [InlineKeyboardButton(f"{w['tag']} {'🔕' if w.get('muted') else '🔔'}", callback_data=f"wallet_{i}")]
        for i, w in enumerate(wallets)
    ]

    if hasattr(target, "reply_text"):  # message
        await target.reply_text("📋 Your wallets:", reply_markup=InlineKeyboardMarkup(buttons))
    else:  # callback_query
        await target.edit_message_text("📋 Your wallets:", reply_markup=InlineKeyboardMarkup(buttons))

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    wallets = user_wallets.get(user_id, [])
    idx = int(query.data.split("_")[1])
    if idx >= len(wallets):
        return

    context.user_data["selected_wallet"] = idx
    wallet = wallets[idx]

    buttons = [
        [InlineKeyboardButton("✏️ Rename", callback_data="action_rename")],
        [InlineKeyboardButton("🗑 Delete", callback_data="action_delete")],
        [InlineKeyboardButton("🔕 Mute" if not wallet["muted"] else "🔔 Unmute", callback_data="action_togglemute")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="action_back")]
    ]

    await query.edit_message_text(
        f"⚙️ Wallet options:\n\n{wallet['tag']} → {wallet['address']}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def wallet_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    wallets = user_wallets.get(user_id, [])
    idx = context.user_data.get("selected_wallet")
    if idx is None or idx >= len(wallets):
        return

    wallet = wallets[idx]
    action = query.data.split("_")[1]

    if action == "rename":
        context.user_data["renaming_wallet"] = True
        await query.edit_message_text("✏️ Send me the new tag for this wallet.")

    elif action == "delete":
        context.user_data["confirm_delete"] = idx
        await query.edit_message_text(
            f"❓ Are you sure you want to delete:\n{wallet['tag']} → {wallet['address']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data="confirm_yes"),
                 InlineKeyboardButton("❌ No", callback_data="confirm_no")]
            ])
        )

    elif action == "togglemute":
        wallet["muted"] = not wallet.get("muted", False)
        await show_wallet_list(query, user_id)

    elif action == "back":
        await show_wallet_list(query, user_id)

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    wallets = user_wallets.get(user_id, [])
    idx = context.user_data.get("confirm_delete")

    if query.data == "confirm_yes" and idx is not None and idx < len(wallets):
        wallets.pop(idx)
        context.user_data.pop("confirm_delete", None)
        await show_wallet_list(query, user_id)
    else:
        await show_wallet_list(query, user_id)

async def set_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.user_data.get("awaiting_tag") and not context.user_data.get("renaming_wallet"):
        await update.message.reply_text("⚠️ No wallet waiting for a tag.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /settag YourName")
        return

    tag = " ".join(context.args)

    if context.user_data.get("renaming_wallet"):
        idx = context.user_data.get("selected_wallet")
        if idx is not None and idx < len(user_wallets.get(user_id, [])):
            user_wallets[user_id][idx]["tag"] = tag
            await update.message.reply_text(f"✏️ Tag updated to: {tag}", reply_markup=main_menu)
        context.user_data.clear()
        return

    address = context.user_data.get("new_wallet")
    if address:
        user_wallets.setdefault(user_id, []).append({"address": address, "tag": tag, "muted": False})
        await update.message.reply_text(
            f"✅ Wallet saved:\n{tag} → {address}",
            reply_markup=main_menu
        )

    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operation canceled.", reply_markup=main_menu)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("settag", set_tag))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(wallet_menu, pattern="^wallet_"))
    app.add_handler(CallbackQueryHandler(wallet_action, pattern="^action_"))
    app.add_handler(CallbackQueryHandler(confirm_delete, pattern="^confirm_"))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()