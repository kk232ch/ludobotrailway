import os
import json
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import firebase_admin
from firebase_admin import credentials, firestore

# --- IMPORT THE VISUAL ENGINE ---
# This pulls the function from your game_engine.py file
from game_engine import draw_board 

# --- 1. SETUP FIREBASE ---
if not firebase_admin._apps:
    # Check if we have the key in Environment Variables (Railway method)
    firebase_key = os.environ.get("FIREBASE_KEY")
    
    if firebase_key:
        # Load from the variable we just added in Railway
        cred_dict = json.loads(firebase_key)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback to default (for local testing or Google Cloud)
        cred = credentials.ApplicationDefault()
        
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. SETUP BOT & FLASK ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8460093413:AAEkWlc4VNieR5Zf7jzdQYXLryUwNIE4FwI")
ADMIN_ID = 7317085309 
app = Flask(__name__)

# Initialize Bot Application
bot_app = ApplicationBuilder().token(TOKEN).build()

# --- 3. WALLET & ADMIN FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎲 Welcome to Ludo Bot!\n\nCommands:\n/play - Start Game\n/balance - Check Money\n/deposit <TxID> - Add Money\n/board - Test Visuals")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    doc = db.collection('users').document(user_id).get()
    bal = doc.to_dict().get('balance', 0) if doc.exists else 0
    await update.message.reply_text(f"💰 Your Wallet Balance: ₹{bal}")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /deposit <TransactionID>")
        return

    tx_id = args[0]
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name

    db.collection('deposits').add({
        'userId': user_id,
        'username': username,
        'txId': tx_id,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    })

    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 New Deposit!\nUser: @{username}\nTxID: {tx_id}")
    await update.message.reply_text("✅ Deposit request submitted!")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        target_user_id = context.args[0]
        amount = float(context.args[1])
        
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
    
    # 1. Check Balance
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    current_bal = user_doc.to_dict().get('balance', 0) if user_doc.exists else 0
    
    if current_bal < bet_amount:
        await query.edit_message_text(f"❌ Insufficient Balance! You have ₹{current_bal}. Please /deposit.")
        return

    # 2. Deduct Balance
    user_ref.update({'balance': current_bal - bet_amount})
    
    await query.edit_message_text(f"✅ Bet Accepted: ₹{bet_amount}\nGenerating Board...")

    # 3. START GAME VISUALS
    # Create a starting game state
    initial_state = {
        "red": [0, 'home', 'home', 'home'], # 1 token on start, 3 in home
        "green": ['home', 'home', 'home', 'home'],
        "yellow": ['home', 'home', 'home', 'home'],
        "blue": ['home', 'home', 'home', 'home']
    }

    # Generate the Image
    img_file = draw_board(initial_state)

    if img_file:
        await context.bot.send_photo(
            chat_id=user_id, 
            photo=img_file, 
            caption="🟢 Game Started! Red's Turn."
        )
    else:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Error: Could not generate board image.")

# --- 5. VISUAL TEST COMMAND ---
async def test_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Call this command to calibrate your board image positions"""
    test_state = {
        "red": [0, 1, 2, 'home'], 
        "green": [14, 15, 'home', 'home']
    }
    img = draw_board(test_state)
    if img:
        await update.message.reply_photo(photo=img, caption="📏 Calibration Test Board")
    else:
        await update.message.reply_text("❌ Failed to draw board.")

# --- 6. REGISTER HANDLERS ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("balance", balance))
bot_app.add_handler(CommandHandler("deposit", deposit))
bot_app.add_handler(CommandHandler("approve", approve))
bot_app.add_handler(CommandHandler("play", play))
bot_app.add_handler(CommandHandler("board", test_board)) # Added new command
bot_app.add_handler(CallbackQueryHandler(handle_bet))

# --- 7. FLASK SERVER ---
@app.route("/", methods=["GET"])
def index():
    return "Ludo Bot is Running!"

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    # Retrieve the message in JSON and then transform it to Telegram object
    if request.method == "POST":
        json_update = request.get_json(force=True)
        update = Update.de_json(json_update, bot_app.bot)
        
        # Initialize the application if not already done
        if not bot_app._initialized:
            await bot_app.initialize()
            await bot_app.start()

        await bot_app.process_update(update)
        return "OK"
    return "Method not allowed"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
