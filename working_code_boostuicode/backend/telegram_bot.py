# telegram_bot.py - Telegram Bot for Vehicle Hire Confirmation
import requests
import json
from datetime import datetime
from config.db_config import get_connection, release_connection
import traceback

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8429056081:AAGvjIVnO9-a0I7p4-PZY-p63ZveS_EKfws"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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


def send_telegram_message(chat_id, text, reply_markup=None):
    """Send a message via Telegram API"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None


def send_initial_message(chat_id, manifest_no, doc_id):
    """Send initial message with two buttons"""
    text = f"""📋 <b>Vehicle Hire Confirmation</b>

Manifest No: <b>{manifest_no}</b>

Please provide the following details by clicking the buttons below:"""

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "💰 Enter Advance Amount", "callback_data": f"advance_{doc_id}"},
            ],
            [
                {"text": "📦 Enter Quantity", "callback_data": f"qty_{doc_id}"}
            ]
        ]
    }
    
    return send_telegram_message(chat_id, text, reply_markup)


def ask_for_advance_amount(chat_id, manifest_no):
    """Ask user to enter advance amount"""
    text = f"""💰 <b>Enter Advance Amount</b>

Manifest No: {manifest_no}

Please type the <b>Advance Amount</b> (e.g., 2000):"""
    
    return send_telegram_message(chat_id, text)


def ask_for_quantity(chat_id, manifest_no):
    """Ask user to enter quantity"""
    text = f"""📦 <b>Enter Quantity</b>

Manifest No: {manifest_no}

Please type the <b>Quantity</b> (e.g., 200):"""
    
    return send_telegram_message(chat_id, text)


def send_reminder(chat_id, missing_field, manifest_no):
    """Send reminder for missing data"""
    if missing_field == 'advance_amount':
        field_name = "Advance Amount"
        emoji = "💰"
    else:
        field_name = "Quantity"
        emoji = "📦"
    
    text = f"""⏳ <b>Waiting for {field_name}</b>

Manifest No: {manifest_no}

{emoji} Please enter the <b>{field_name}</b> to complete the process."""
    
    return send_telegram_message(chat_id, text)


def send_confirmation_message(chat_id, session_data):
    """Send final confirmation message after both values received"""
    current_date = datetime.now().strftime('%d/%m/%Y')
    amount = float(session_data['qty']) * HARDCODED_DATA['rate']
    
    text = f"""✅ <b>Vehicle Hire Confirmed!</b>

Hi, this is KSS.
This is the message for confirming the Manifest No: <b>{session_data['manifest_no']}</b>

<b>Details:</b>
• Advance Amount: ₹{session_data['advance_amount']}
• Quantity: {session_data['qty']}
• Rate: ₹{HARDCODED_DATA['rate']}
• Total Amount: ₹{amount:.2f}
• Date: {current_date}

Thank you! 🙏"""
    
    return send_telegram_message(chat_id, text)


def create_session(doc_id, phone_no, manifest_no, chat_id=None):
    """Create a new pending session in database"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if session already exists for this doc_id
        cur.execute(
            "SELECT id FROM telegram_pending_sessions WHERE doc_id = %s AND status != 'completed'",
            (doc_id,)
        )
        existing = cur.fetchone()
        
        if existing:
            # Update existing session
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET phone_no = %s, chat_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s AND status != 'completed'
            """, (phone_no, chat_id, doc_id))
        else:
            # Create new session
            cur.execute("""
                INSERT INTO telegram_pending_sessions 
                (doc_id, phone_no, manifest_no, chat_id, status)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (doc_id, phone_no, manifest_no, chat_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error creating session: {e}")
        traceback.print_exc()
        return False
        
    finally:
        if conn:
            release_connection(conn)


def get_session_by_chat_id(chat_id):
    """Get active session for a chat_id"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, doc_id, phone_no, manifest_no, advance_amount, qty, status
            FROM telegram_pending_sessions 
            WHERE chat_id = %s AND status NOT IN ('completed', 'pending')
            ORDER BY updated_at DESC
            LIMIT 1
        """, (chat_id,))
        
        row = cur.fetchone()
        if row:
            return {
                'id': row[0],
                'doc_id': row[1],
                'phone_no': row[2],
                'manifest_no': row[3],
                'advance_amount': row[4],
                'qty': row[5],
                'status': row[6]
            }
        return None
        
    except Exception as e:
        print(f"Error getting session: {e}")
        return None
        
    finally:
        if conn:
            release_connection(conn)


def update_session_value(session_id, field, value):
    """Update a value in the session"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        if field == 'advance_amount':
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET advance_amount = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (value, session_id))
        elif field == 'qty':
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET qty = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (value, session_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error updating session: {e}")
        return False
        
    finally:
        if conn:
            release_connection(conn)


def update_session_status(session_id, status):
    """Update session status"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE telegram_pending_sessions 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, session_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error updating session status: {e}")
        return False
        
    finally:
        if conn:
            release_connection(conn)


def complete_session_and_save(session_data):
    """Complete the session and save to vehicle_hire table"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        current_date = datetime.now().strftime('%d/%m/%Y')
        amount = float(session_data['qty']) * HARDCODED_DATA['rate']
        
        # Insert into vehicle_hire
        cur.execute("""
            INSERT INTO vehicle_hire 
            (doc_id, manifest_no, advance_amount, payable_at, paid_by, account, 
             paymode, filling_station, slip_no, slip_date, qty, rate, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session_data['doc_id'],
            session_data['manifest_no'],
            session_data['advance_amount'],
            HARDCODED_DATA['payable_at'],
            HARDCODED_DATA['paid_by'],
            HARDCODED_DATA['account'],
            HARDCODED_DATA['paymode'],
            HARDCODED_DATA['filling_station'],
            HARDCODED_DATA['slip_no'],
            current_date,
            session_data['qty'],
            HARDCODED_DATA['rate'],
            amount
        ))
        
        # Update doc_processing_log status to Ready To Run
        cur.execute("""
            UPDATE doc_processing_log
            SET vehicle_hire_status = 'Ready To Run',
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """, (session_data['doc_id'],))
        
        # Update session status to completed
        cur.execute("""
            UPDATE telegram_pending_sessions 
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (session_data['id'],))
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error completing session: {e}")
        traceback.print_exc()
        return False
        
    finally:
        if conn:
            release_connection(conn)


def get_session_by_doc_id(doc_id):
    """Get session by doc_id"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, doc_id, phone_no, manifest_no, advance_amount, qty, status, chat_id
            FROM telegram_pending_sessions 
            WHERE doc_id = %s AND status != 'completed'
            ORDER BY created_at DESC
            LIMIT 1
        """, (doc_id,))
        
        row = cur.fetchone()
        if row:
            return {
                'id': row[0],
                'doc_id': row[1],
                'phone_no': row[2],
                'manifest_no': row[3],
                'advance_amount': row[4],
                'qty': row[5],
                'status': row[6],
                'chat_id': row[7]
            }
        return None
        
    except Exception as e:
        print(f"Error getting session by doc_id: {e}")
        return None
        
    finally:
        if conn:
            release_connection(conn)


def handle_callback_query(callback_query):
    """Handle button click callbacks from Telegram"""
    chat_id = callback_query['message']['chat']['id']
    callback_data = callback_query['data']
    
    # Parse callback data (format: "advance_123" or "qty_123")
    parts = callback_data.split('_')
    if len(parts) != 2:
        return
    
    action, doc_id = parts[0], int(parts[1])
    
    # Get session
    session = get_session_by_doc_id(doc_id)
    if not session:
        send_telegram_message(chat_id, "❌ Session not found. Please try again from the web interface.")
        return
    
    # Update chat_id if not set
    if not session.get('chat_id'):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE telegram_pending_sessions 
            SET chat_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (str(chat_id), session['id']))
        conn.commit()
        release_connection(conn)
        session['chat_id'] = str(chat_id)
    
    if action == 'advance':
        update_session_status(session['id'], 'waiting_advance')
        ask_for_advance_amount(chat_id, session['manifest_no'])
    elif action == 'qty':
        update_session_status(session['id'], 'waiting_qty')
        ask_for_quantity(chat_id, session['manifest_no'])


def handle_text_message(message):
    """Handle text messages from user"""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    
    # Get active session for this chat
    session = get_session_by_chat_id(str(chat_id))
    
    if not session:
        send_telegram_message(chat_id, "ℹ️ No active session. Please start from the web interface.")
        return
    
    # Try to parse the value as a number
    try:
        value = float(text)
    except ValueError:
        send_telegram_message(chat_id, "❌ Please enter a valid number.")
        return
    
    # Update based on current status
    if session['status'] == 'waiting_advance':
        update_session_value(session['id'], 'advance_amount', value)
        
        # Check if qty already exists
        if session['qty']:
            # Both values received, complete the process
            session['advance_amount'] = value
            complete_session_and_save(session)
            send_confirmation_message(chat_id, session)
        else:
            # Still waiting for qty
            send_reminder(chat_id, 'qty', session['manifest_no'])
            # Reset status to pending so user can click the button again
            update_session_status(session['id'], 'pending')
            
    elif session['status'] == 'waiting_qty':
        update_session_value(session['id'], 'qty', value)
        
        # Check if advance_amount already exists
        if session['advance_amount']:
            # Both values received, complete the process
            session['qty'] = value
            complete_session_and_save(session)
            send_confirmation_message(chat_id, session)
        else:
            # Still waiting for advance_amount
            send_reminder(chat_id, 'advance_amount', session['manifest_no'])
            # Reset status to pending so user can click the button again
            update_session_status(session['id'], 'pending')


def process_update(update):
    """Process a single Telegram update"""
    if 'callback_query' in update:
        handle_callback_query(update['callback_query'])
        # Answer the callback to remove loading state
        callback_id = update['callback_query']['id']
        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": callback_id})
    elif 'message' in update and 'text' in update['message']:
        handle_text_message(update['message'])


def get_updates(offset=None):
    """Get updates from Telegram using long polling"""
    url = f"{TELEGRAM_API_URL}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None


def run_bot():
    """Main bot loop using long polling"""
    print("🤖 Telegram bot started!")
    offset = None
    
    while True:
        try:
            updates = get_updates(offset)
            
            if updates and updates.get('ok') and updates.get('result'):
                for update in updates['result']:
                    process_update(update)
                    offset = update['update_id'] + 1
                    
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            break
        except Exception as e:
            print(f"Error in bot loop: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    run_bot()
