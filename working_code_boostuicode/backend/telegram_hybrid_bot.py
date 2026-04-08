# telegram_hybrid_bot.py - Hybrid Telegram Bot with Interactive Buttons
# Uses Telethon to send initial message + Bot API for interactive buttons

import asyncio
import json
import threading
import time
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest
import requests

# ==================== CONFIGURATION ====================
# Telegram API Credentials (for sending initial messages)
API_ID = 30174846
API_HASH = "226783f8520d79c6a5ac471ef2f9ce81"
PHONE = "+918122715213"
SESSION_NAME = "vehicle_hire_session"

# Bot Token (for interactive buttons)
BOT_TOKEN = "8429056081:AAGvjIVnO9-a0I7p4-PZY-p63ZveS_EKfws"
BOT_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Bot username (get this from @BotFather)
BOT_USERNAME = "KSSVehicleHireBot"  # Replace with your actual bot username

# Hardcoded values
HARDCODED_DATA = {
    'payable_at': 'ARAKKONAM',
    'paid_by': 'Bank',
    'account': 'HDFC BANK A/C-8080',
    'paymode': 'UPI',
    'filling_station': 'KKS FUEL SERVICE-HPCL',
    'slip_no': '10',
    'rate': 93.05
}

# Store active sessions
# Format: {chat_id: {doc_id, manifest_no, advance_amount, qty, state, last_reminder}}
active_sessions = {}

# Reminder interval (10 minutes = 600 seconds)
REMINDER_INTERVAL = 600

# ==================== BOT API FUNCTIONS ====================

def send_bot_message(chat_id, text, reply_markup=None):
    """Send message via Bot API"""
    url = f"{BOT_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"❌ Bot API error: {e}")
        return None


def send_buttons_message(chat_id, manifest_no, doc_id):
    """Send message with two buttons"""
    text = f"""📋 *Vehicle Hire Confirmation*

Manifest No: *{manifest_no}*

Please click a button to enter the required data:"""

    reply_markup = {
        "inline_keyboard": [
            [{"text": "💰 Enter Advance Amount", "callback_data": f"advance_{doc_id}"}],
            [{"text": "📦 Enter Quantity", "callback_data": f"qty_{doc_id}"}]
        ]
    }
    
    return send_bot_message(chat_id, text, reply_markup)


def send_ask_advance(chat_id, manifest_no):
    """Ask for advance amount"""
    text = f"""💰 *Enter Advance Amount*

Manifest No: {manifest_no}

Please reply with the amount.
*Example:* `2000`"""
    
    return send_bot_message(chat_id, text)


def send_ask_quantity(chat_id, manifest_no):
    """Ask for quantity"""
    text = f"""📦 *Enter Quantity*

Manifest No: {manifest_no}

Please reply with the quantity.
*Example:* `200`"""
    
    return send_bot_message(chat_id, text)


def send_confirmation(chat_id, session):
    """Send final confirmation"""
    amount = session['qty'] * HARDCODED_DATA['rate']
    current_date = datetime.now().strftime('%d/%m/%Y')
    
    text = f"""✅ *Vehicle Hire Confirmed!*

Manifest No: *{session['manifest_no']}*

*Details:*
• Advance Amount: ₹{session['advance_amount']}
• Quantity: {session['qty']}
• Rate: ₹{HARDCODED_DATA['rate']}
• Total Amount: ₹{amount:.2f}
• Date: {current_date}

Thank you! 🙏"""
    
    return send_bot_message(chat_id, text), amount, current_date


def send_reminder(chat_id, manifest_no, missing_field):
    """Send reminder for missing data"""
    if missing_field == 'qty':
        text = f"""⏰ *Reminder*

Manifest No: {manifest_no}

Please click the button below to enter *Quantity*."""
        reply_markup = {
            "inline_keyboard": [
                [{"text": "📦 Enter Quantity", "callback_data": f"qty_reminder"}]
            ]
        }
    else:
        text = f"""⏰ *Reminder*

Manifest No: {manifest_no}

Please click the button below to enter *Advance Amount*."""
        reply_markup = {
            "inline_keyboard": [
                [{"text": "💰 Enter Advance Amount", "callback_data": f"advance_reminder"}]
            ]
        }
    
    return send_bot_message(chat_id, text, reply_markup)


# ==================== DATABASE FUNCTIONS ====================

def save_to_database(session, amount, current_date):
    """Save completed session to database"""
    try:
        from config.db_config import get_connection, release_connection
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Insert into vehicle_hire
        cur.execute("""
            INSERT INTO vehicle_hire 
            (doc_id, manifest_no, advance_amount, payable_at, paid_by, account, 
             paymode, filling_station, slip_no, slip_date, qty, rate, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['doc_id'],
            session['manifest_no'],
            session['advance_amount'],
            HARDCODED_DATA['payable_at'],
            HARDCODED_DATA['paid_by'],
            HARDCODED_DATA['account'],
            HARDCODED_DATA['paymode'],
            HARDCODED_DATA['filling_station'],
            HARDCODED_DATA['slip_no'],
            current_date,
            session['qty'],
            HARDCODED_DATA['rate'],
            amount
        ))
        
        # Update doc_processing_log status
        cur.execute("""
            UPDATE doc_processing_log
            SET vehicle_hire_status = 'Ready To Run',
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """, (session['doc_id'],))
        
        # Update telegram_pending_sessions
        cur.execute("""
            UPDATE telegram_pending_sessions 
            SET status = 'completed', 
                advance_amount = %s,
                qty = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """, (session['advance_amount'], session['qty'], session['doc_id']))
        
        conn.commit()
        release_connection(conn)
        print(f"✅ Database updated for doc_id {session['doc_id']}")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


# ==================== TELETHON FUNCTIONS ====================

async def send_initial_message_via_telethon(phone_no, manifest_no, doc_id):
    """Send initial message with bot link via Telethon"""
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    
    try:
        # Format phone number
        if not phone_no.startswith('+'):
            phone_no = '+91' + phone_no
        
        # Get or import contact
        try:
            entity = await client.get_entity(phone_no)
        except:
            contact = InputPhoneContact(
                client_id=0,
                phone=phone_no,
                first_name="Driver",
                last_name=""
            )
            await client(ImportContactsRequest([contact]))
            entity = await client.get_entity(phone_no)
        
        # Create deep link to bot with session data
        deep_link = f"https://t.me/{BOT_USERNAME}?start={doc_id}"
        
        message = f"""📋 *Vehicle Hire Confirmation*

Manifest No: *{manifest_no}*

Please click the link below to enter the details:

👉 {deep_link}

(Click the link to open the confirmation form)"""
        
        await client.send_message(entity, message)
        print(f"✅ Initial message sent to {phone_no}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False
    finally:
        await client.disconnect()


def send_initial_message(phone_no, manifest_no, doc_id):
    """Synchronous wrapper"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            send_initial_message_via_telethon(phone_no, manifest_no, doc_id)
        )
        return result
    except Exception as e:
        print(f"Error: {e}")
        return False


# ==================== BOT POLLING & HANDLERS ====================

def handle_callback_query(callback):
    """Handle button clicks"""
    chat_id = callback['message']['chat']['id']
    data = callback['data']
    callback_id = callback['id']
    
    # Answer the callback
    requests.post(f"{BOT_API_URL}/answerCallbackQuery", 
                  json={"callback_query_id": callback_id})
    
    if chat_id not in active_sessions:
        send_bot_message(chat_id, "❌ Session expired. Please start again.")
        return
    
    session = active_sessions[chat_id]
    
    if data.startswith('advance'):
        session['state'] = 'waiting_advance'
        send_ask_advance(chat_id, session['manifest_no'])
        
    elif data.startswith('qty'):
        if session['advance_amount'] is None:
            send_bot_message(chat_id, "⚠️ Please enter Advance Amount first!")
            send_ask_advance(chat_id, session['manifest_no'])
            session['state'] = 'waiting_advance'
        else:
            session['state'] = 'waiting_qty'
            send_ask_quantity(chat_id, session['manifest_no'])


def handle_message(message):
    """Handle text messages (replies with values)"""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    
    # Handle /start with deep link
    if text.startswith('/start'):
        parts = text.split()
        if len(parts) > 1:
            doc_id = int(parts[1])
            # Get manifest from database
            try:
                from config.db_config import get_connection, release_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT manifest_no FROM telegram_pending_sessions WHERE doc_id = %s",
                    (doc_id,)
                )
                row = cur.fetchone()
                release_connection(conn)
                
                if row:
                    manifest_no = row[0]
                    # Create session
                    active_sessions[chat_id] = {
                        'doc_id': doc_id,
                        'manifest_no': manifest_no,
                        'advance_amount': None,
                        'qty': None,
                        'state': 'started',
                        'last_reminder': time.time()
                    }
                    # Send buttons
                    send_buttons_message(chat_id, manifest_no, doc_id)
                else:
                    send_bot_message(chat_id, "❌ Session not found.")
            except Exception as e:
                print(f"Error: {e}")
                send_bot_message(chat_id, "❌ Error loading session.")
        else:
            send_bot_message(chat_id, "👋 Welcome! Please use the link sent to you to start.")
        return
    
    # Handle value input
    if chat_id not in active_sessions:
        return
    
    session = active_sessions[chat_id]
    
    try:
        value = float(text)
    except ValueError:
        send_bot_message(chat_id, "❌ Please enter a valid number.")
        return
    
    if session['state'] == 'waiting_advance':
        session['advance_amount'] = value
        session['state'] = 'advance_done'
        session['last_reminder'] = time.time()
        
        send_bot_message(chat_id, f"✅ Advance Amount saved: ₹{value}")
        
        # Now show quantity button
        text = f"""Now please enter the *Quantity*:"""
        reply_markup = {
            "inline_keyboard": [
                [{"text": "📦 Enter Quantity", "callback_data": f"qty_{session['doc_id']}"}]
            ]
        }
        send_bot_message(chat_id, text, reply_markup)
        
    elif session['state'] == 'waiting_qty':
        session['qty'] = value
        session['state'] = 'completed'
        
        # Send confirmation and save
        result, amount, current_date = send_confirmation(chat_id, session)
        save_to_database(session, amount, current_date)
        
        # Remove session
        del active_sessions[chat_id]
        print(f"✅ Session completed for {session['manifest_no']}")


def reminder_checker():
    """Background thread to send reminders every 10 minutes"""
    while True:
        time.sleep(60)  # Check every minute
        
        current_time = time.time()
        for chat_id, session in list(active_sessions.items()):
            if session['state'] == 'advance_done':
                # Check if 10 minutes passed since last reminder
                if current_time - session['last_reminder'] >= REMINDER_INTERVAL:
                    send_reminder(chat_id, session['manifest_no'], 'qty')
                    session['last_reminder'] = current_time
                    print(f"📢 Reminder sent for {session['manifest_no']}")


def poll_bot():
    """Poll for bot updates"""
    offset = None
    print("🤖 Bot started! Waiting for messages...")
    
    while True:
        try:
            url = f"{BOT_API_URL}/getUpdates"
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    offset = update['update_id'] + 1
                    
                    if 'callback_query' in update:
                        handle_callback_query(update['callback_query'])
                    elif 'message' in update:
                        handle_message(update['message'])
                        
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)


def run_bot():
    """Main function to run the bot"""
    # Start reminder thread
    reminder_thread = threading.Thread(target=reminder_checker, daemon=True)
    reminder_thread.start()
    
    # Start polling
    poll_bot()


if __name__ == "__main__":
    run_bot()
