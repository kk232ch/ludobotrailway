import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. SETUP FIREBASE ---
# If you have serviceAccountKey.json, use it. Otherwise use default (for Cloud Run)
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault() 
    # OR for local testing: cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. SETUP BOT & FLASK ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8460093413:AAEkWlc4VNieR5Zf7jzdQYXLryUwNIE4FwI")
ADMIN_ID = 7317085309 # <--- REPLACE WITH YOUR ID
app = Flask(__name__)

# Initialize Bot Application (async)
bot_app = ApplicationBuilder().token(TOKEN).build()

# --- 3. WALLET & ADMIN FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Ludo Bot! Use /play to start.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    doc = db.collection('users').document(user_id).get()
    bal = doc.to_dict().get('balance', 0) if doc.exists else 0
    await update.message.reply_text(f"💰 Your Wallet Balance: ₹{bal}")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /deposit <TxID>
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /deposit <TransactionID>")
        return

    tx_id = args[0]
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name

    # Save to Firestore
    db.collection('deposits').add({
        'userId': user_id,
        'username': username,
        'txId': tx_id,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    })

    # Notify Admin
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 New Deposit!\nUser: @{username}\nTxID: {tx_id}")
    await update.message.reply_text("✅ Deposit request submitted!")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /approve <UserId> <Amount>
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        target_user_id = context.args[0]
        amount = float(context.args[1])
        
        # Transaction to update balance
        user_ref = db.collection('users').document(target_user_id)
        
        @firestore.transactional
        def update_balance_tx(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            new_balance = (snapshot.to_dict().get('balance', 0) if snapshot.exists else 0) + amount
            transaction.set(ref, {'balance': new_balance}, merge=True)

        transaction = db.transaction()
        update_balance_tx(transaction, user_ref)

        await context.bot.send_message(chat_id=target_user_id, text=f"✅ Deposit Approved! Credited: ${amount}")
        await update.message.reply_text(f"✅ Added ${amount} to {target_user_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- 4. GAME & BETTING ---

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Practice ($0)", callback_data='bet_0'), InlineKeyboardButton("$0.5", callback_data='bet_0.5')],
        [InlineKeyboardButton("$1.0", callback_data='bet_1'), InlineKeyboardButton("$2.0", callback_data='bet_2')]
    ]
    await update.message.reply_text("🎲 Choose your bet amount:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    bet_amount = float(query.data.split('_')[1])
    user_id = str(query.from_user.id)
    
    # Check Balance
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    current_bal = user_doc.to_dict().get('balance', 0) if user_doc.exists else 0
    
    if current_bal < bet_amount:
        await query.edit_message_text(f"❌ Insufficient Balance! You have ₹{current_bal}. Please /deposit.")
        return

    # Deduct Balance
    user_ref.update({'balance': current_bal - bet_amount})
    
    # HERE: Import your game logic from game_engine.py
    # from game_engine import start_ludo_game
    # start_ludo_game(user_id, bet_amount)
    
    await query.edit_message_text(f"✅ Bet Accepted: ₹{bet_amount}\nSearching for opponent...")

# --- 5. REGISTER HANDLERS ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("balance", balance))
bot_app.add_handler(CommandHandler("deposit", deposit))
bot_app.add_handler(CommandHandler("approve", approve))
bot_app.add_handler(CommandHandler("play", play))
bot_app.add_handler(CallbackQueryHandler(handle_bet))

# --- 6. FLASK SERVER FOR CLOUD RUN ---
@app.route("/", methods=["GET"])
def index():
    return "Ludo Bot is Running!"

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    # Retrieve the message in JSON and then transform it to Telegram object
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, bot_app.bot)
    await bot_app.process_update(update)
    return "OK"

# Webhook Setup Function (Run this once manually or check on startup)
async def set_webhook():
    webhook_url = f"https://YOUR-CLOUD-RUN-URL.a.run.app/{TOKEN}"
    await bot_app.bot.set_webhook(webhook_url)

if __name__ == "__main__":
    # This block runs when you execute 'python main.py'
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)