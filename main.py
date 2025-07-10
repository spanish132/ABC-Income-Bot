import sqlite3
import logging
import random
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- আপনার অ্যাডমিন আইডি এখানে দিন ---
# @userinfobot থেকে আপনার নিজের টেলিগ্রাম ইউজার আইডি বের করে এখানে বসান।
# পেমেন্টের অনুরোধগুলো এই আইডিতেই পাঠানো হবে।
ADMIN_USER_ID = 7347006196 
# ------------------------------------

# --- আপনার কাজের লিংকগুলো এখানে যোগ করুন ---
TASK_LINKS = [
    "https://litenewssp.blogspot.com/2025/07/working-online.html",
    "https://YOUR_WEBSITE_LINK_2.com/page-a.html",
    "https://YOUR_WEBSITE_LINK_3.com/task-v2.html",
]
# -----------------------------------------

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation Handler এর জন্য স্টেট تعريف
GET_NAME, GET_PHONE, GET_METHOD, GET_NUMBER, GET_AMOUNT = range(5)

# ডাটাবেস সেটআপ
def setup_database():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    cursor = conn.cursor()
    # users টেবিলে নতুন কলাম যোগ করা
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        phone_number TEXT,
        balance REAL NOT NULL
    )
    """)
    # withdrawals টেবিল তৈরি করা
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method TEXT,
        number TEXT,
        amount REAL,
        status TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn

db_connection = setup_database()

# --- রেজিস্ট্রেশন Conversation ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    cursor = db_connection.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        await update.message.reply_text("আপনি ஏற்கனவே নিবন্ধিত। কাজ পেতে /task চাপুন।")
        return ConversationHandler.END
    else:
        await update.message.reply_text("স্বাগতম! ইনকাম শুরু করার জন্য অনুগ্রহ করে নিবন্ধন সম্পন্ন করুন।\n\nআপনার সম্পূর্ণ নাম লিখুন:")
        return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("ধন্যবাদ! এবার আপনার ১১ সংখ্যার মোবাইল নাম্বারটি দিন:")
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    phone_number = update.message.text
    if len(phone_number) != 11 or not phone_number.isdigit():
        await update.message.reply_text("ভুল নাম্বার! অনুগ্রহ করে ১১ সংখ্যার সঠিক মোবাইল নাম্বার দিন:")
        return GET_PHONE

    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, name, phone_number, balance) VALUES (?, ?, ?, ?)",
        (user.id, context.user_data['name'], phone_number, 0.0)
    )
    db_connection.commit()
    await update.message.reply_text("✅ আপনার নিবন্ধন সফল হয়েছে!\nএখন /task কমান্ড দিয়ে কাজ শুরু করতে পারেন।")
    return ConversationHandler.END

# --- উইথড্র Conversation ---
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply_keyboard = [["বিকাশ", "মোবাইল রিচার্জ"]]
    await update.message.reply_text(
        "আপনি কোন মাধ্যমে টাকা তুলতে চান? (প্রক্রিয়া বাতিল করতে /cancel চাপুন)",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return GET_METHOD

async def get_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['method'] = update.message.text
    await update.message.reply_text("আপনার পেমেন্ট নাম্বারটি দিন (যে নাম্বারে টাকা পাঠাতে হবে):")
    return GET_NUMBER

async def get_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['number'] = update.message.text
    await update.message.reply_text("আপনি কত টাকা তুলতে চান? (যেমন: 50, 100)")
    return GET_AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        amount = float(update.message.text)
        cursor = db_connection.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]

        if amount > balance:
            await update.message.reply_text(f"❌ আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই। আপনার ব্যালেন্স: {balance:.2f} টাকা।")
            return ConversationHandler.END
        if amount < 10: # সর্বনিম্ন উইথড্র লিমিট
             await update.message.reply_text("❌ সর্বনিম্ন ১০ টাকা উইথড্র করতে পারবেন।")
             return ConversationHandler.END

        # ব্যালেন্স থেকে টাকা কেটে নেওয়া
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        
        # উইথড্র অনুরোধ ডাটাবেসে যোগ করা
        method = context.user_data['method']
        number = context.user_data['number']
        cursor.execute(
            "INSERT INTO withdrawals (user_id, method, number, amount, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, method, number, amount, "pending")
        )
        db_connection.commit()

        await update.message.reply_text("✅ আপনার উইথড্র অনুরোধ গ্রহণ করা হয়েছে। ২৪ ঘণ্টার মধ্যে পেমেন্ট সম্পন্ন করা হবে।", reply_markup=ReplyKeyboardRemove())
        
        # অ্যাডমিনকে নোটিফিকেশন পাঠানো
        admin_message = (
            f"🔔 নতুন পেমেন্ট অনুরোধ!\n\n"
            f"ব্যবহারকারী আইডি: {user_id}\n"
            f"মাধ্যম: {method}\n"
            f"নাম্বার: {number}\n"
            f"পরিমাণ: {amount:.2f} টাকা"
        )
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=admin_message)

    except (ValueError):
        await update.message.reply_text("❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন।")
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("প্রক্রিয়াটি বাতিল করা হয়েছে।", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- অন্যান্য কমান্ড ---
async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    random_link = random.choice(TASK_LINKS)
    await update.message.reply_text(f"👇 নিচের লিংকে গিয়ে কাজ সম্পন্ন করুন এবং প্রাপ্ত ১০-সংখ্যার কোডটি জমা দিন:\n\n{random_link}")

async def submit_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    # ... (submit_code এর বাকি কোড আগের মতোই থাকবে, কোনো পরিবর্তন নেই) ...
    try:
        code = context.args[0]
        if len(code) != 10 or not code.isdigit():
            await update.message.reply_text("❌ ভুল ফরম্যাট! কোডটি অবশ্যই ১০ সংখ্যার হতে হবে।")
            return
        part1 = int(code[:5])
        part2 = int(code[5:])
        if part1 + part2 == 30000:
            cursor = db_connection.cursor()
            task_reward = 0.25
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task_reward, user_id))
            db_connection.commit()
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            new_balance = cursor.fetchone()[0]
            await update.message.reply_text(f"🎉 কাজ সফল হয়েছে! আপনার একাউন্টে {task_reward:.2f} টাকা যোগ হয়েছে।\nআপনার বর্তমান ব্যালেন্স: {new_balance:.2f} টাকা।")
        else:
            await update.message.reply_text("❌ আপনার জমা দেওয়া কোডটি সঠিক নয়। অনুগ্রহ করে আবার চেষ্টা করুন।")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ ব্যবহারবিধি: /submit <আপনার ১০ সংখ্যার কোড>")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cursor = db_connection.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        await update.message.reply_text(f"💰 আপনার বর্তমান ব্যালেন্স: {result[0]:.2f} টাকা।")
    else:
        await update.message.reply_text("আপনার একাউন্ট খুঁজে পাওয়া যায়নি। প্রথমে /start চাপুন।")

def main() -> None:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN খুঁজে পাওয়া যায়নি!")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()

    # রেজিস্ট্রেশন Conversation Handler যোগ করা
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # উইথড্র Conversation Handler যোগ করা
    withdraw_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw)],
        states={
            GET_METHOD: [MessageHandler(filters.Regex("^(বিকাশ|মোবাইল রিচার্জ)$"), get_method)],
            GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_number)],
            GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(reg_handler)
    application.add_handler(withdraw_handler)
    application.add_handler(CommandHandler("task", task))
    application.add_handler(CommandHandler("submit", submit_code))
    application.add_handler(CommandHandler("balance", balance))

    application.run_polling()

if __name__ == "__main__":
    main()
