import sqlite3
import logging
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- আপনার কাজের লিংকগুলো এখানে যোগ করুন ---
# নিচের তালিকায় আপনার যতগুলো ওয়েবসাইট আছে, সবগুলোর লিংক কমা দিয়ে দিয়ে যোগ করুন।
TASK_LINKS = [
    "https://YOUR_WEBSITE_LINK_1.com/page1.html",
    "https://YOUR_WEBSITE_LINK_2.com/page-a.html",
    "https://YOUR_WEBSITE_LINK_3.com/task-v2.html",
    # আপনি এখানে আরও লিংক যোগ করতে পারবেন
]
# -----------------------------------------

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ডাটাবেস সেটআপ
def setup_database():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL NOT NULL
    )
    """)
    conn.commit()
    return conn

db_connection = setup_database()

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cursor = db_connection.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0.0))
        db_connection.commit()
        await update.message.reply_text("✅ আপনাকে স্বাগতম! আপনার একাউন্ট তৈরি হয়েছে। কাজ শুরু করতে /task চাপুন।")
    else:
        await update.message.reply_text("আপনি ஏற்கனவே নিবন্ধিত। কাজ পেতে /task চাপুন।")

# /task কমান্ড
async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # তালিকা থেকে র‍্যান্ডমভাবে একটি লিংক নির্বাচন করা হবে
    random_link = random.choice(TASK_LINKS)
    await update.message.reply_text(f"👇 নিচের লিংকে গিয়ে কাজ সম্পন্ন করুন এবং প্রাপ্ত ১০-সংখ্যার কোডটি জমা দিন:\n\n{random_link}")

# /submit কমান্ড
async def submit_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        code = context.args[0]
        if len(code) != 10 or not code.isdigit():
            await update.message.reply_text("❌ ভুল ফরম্যাট! কোডটি অবশ্যই ১০ সংখ্যার হতে হবে।")
            return

        part1 = int(code[:5])
        part2 = int(code[5:])

        if part1 + part2 == 30000:
            cursor = db_connection.cursor()
            task_reward = 0.25  # আপনার দেওয়া পুরস্কারের পরিমাণ
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task_reward, user_id))
            db_connection.commit()
            
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            new_balance = cursor.fetchone()[0]
            await update.message.reply_text(f"🎉 কাজ সফল হয়েছে! আপনার একাউন্টে {task_reward:.2f} টাকা যোগ হয়েছে।\nআপনার বর্তমান ব্যালেন্স: {new_balance:.2f} টাকা।")
        else:
            await update.message.reply_text("❌ আপনার জমা দেওয়া কোডটি সঠিক নয়। অনুগ্রহ করে আবার চেষ্টা করুন।")

    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ ব্যবহারবিধি: /submit <আপনার ১০ সংখ্যার কোড>")

# /balance কমান্ড
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
    # এখানে আপনার আসল বট টোকেন বসাতে হবে
    application = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN_HERE").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("task", task))
    application.add_handler(CommandHandler("submit", submit_code))
    application.add_handler(CommandHandler("balance", balance))

    application.run_polling()

if __name__ == "__main__":
    main()
