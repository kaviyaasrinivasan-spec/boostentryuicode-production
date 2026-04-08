# telegram_service.py - Shared Telegram Service for Vehicle Hire
# Single shared client for both sending and receiving messages

import asyncio
import threading
from telethon import TelegramClient, events
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest
from datetime import datetime
import sys
import os
import queue

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Telegram API Credentials
API_ID = 30174846
API_HASH = "226783f8520d79c6a5ac471ef2f9ce81"
PHONE = "+918122715213"
SESSION_NAME = "vehicle_hire_session"

# Hardcoded values for vehicle hire
HARDCODED_DATA = {
    'payable_at': 'ARAKKONAM',
    'paid_by': 'Bank',
    'account': 'HDFC BANK A/C-8080',
    'paymode': 'UPI',
    'filling_station': 'KKS FUEL SERVICE-HPCL',
    'slip_no': '10',
    'rate': 93.05
}

# Store pending sessions
# Format: {user_id: {doc_id, manifest_no, phone_no, advance_amount, qty, state}}
pending_sessions = {}

# Queue for outgoing messages (to be processed by the async event loop)
message_queue = queue.Queue()

# Global client reference
_client = None
_loop = None
_running = False


async def send_message_to_phone(client, phone_no, message):
    """Send a message to a phone number and return user_id"""
    try:
        # Format phone number
        if not phone_no.startswith('+'):
            phone_no = '+91' + phone_no
        
        # Get user entity
        try:
            entity = await client.get_entity(phone_no)
        except:
            # Import contact first
            contact = InputPhoneContact(
                client_id=0,
                phone=phone_no,
                first_name="Driver",
                last_name=""
            )
            await client(ImportContactsRequest([contact]))
            entity = await client.get_entity(phone_no)
        
        # Send message
        await client.send_message(entity, message)
        return entity.id
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return None


async def start_session_async(client, phone_no, manifest_no, doc_id):
    """Start a new vehicle hire session"""
    
    message = f"""📋 *Vehicle Hire Confirmation*

Manifest No: *{manifest_no}*

━━━━━━━━━━━━━━━━━━━━
💰 Please enter the *Advance Amount*

*Format:* Just type the number
*Example:* `2000`
━━━━━━━━━━━━━━━━━━━━"""

    user_id = await send_message_to_phone(client, phone_no, message)
    
    if user_id:
        # Store session
        pending_sessions[user_id] = {
            'doc_id': doc_id,
            'manifest_no': manifest_no,
            'phone_no': phone_no,
            'advance_amount': None,
            'qty': None,
            'state': 'waiting_advance'
        }
        print(f"✅ Session started for {manifest_no} (user_id: {user_id})")
        return True
    return False


async def handle_incoming_message(event):
    """Handle incoming messages from drivers"""
    sender = await event.get_sender()
    
    # Skip if sender is None
    if sender is None:
        return
    
    user_id = sender.id
    text = event.text.strip() if event.text else ""
    
    # Skip empty messages
    if not text:
        return
    
    # Check if this user has an active session
    if user_id not in pending_sessions:
        return
    
    session = pending_sessions[user_id]
    
    # Validate the input is a number
    try:
        value = float(text)
        if value <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        # Wrong format
        if session['state'] == 'waiting_advance':
            await event.reply("""❌ *Wrong Format!*

The data you entered is incorrect.
Please enter a valid *Advance Amount* (numbers only).

*Example:* `2000`""")
        else:
            await event.reply("""❌ *Wrong Format!*

The data you entered is incorrect.
Please enter a valid *Quantity* (numbers only).

*Example:* `200`""")
        return
    
    # Process based on current state
    if session['state'] == 'waiting_advance':
        # Save advance amount
        session['advance_amount'] = value
        session['state'] = 'waiting_qty'
        
        # Ask for quantity
        await event.reply(f"""✅ *Advance Amount Received!*

We have received the Advance Amount: *₹{value}*

━━━━━━━━━━━━━━━━━━━━
📦 Now please enter the *Quantity*

*Format:* Just type the number
*Example:* `200`
━━━━━━━━━━━━━━━━━━━━""")
        
        print(f"📥 Advance Amount received: ₹{value} for {session['manifest_no']}")
        
    elif session['state'] == 'waiting_qty':
        # Save quantity
        session['qty'] = value
        session['state'] = 'completed'
        
        # Calculate total
        total_amount = value * HARDCODED_DATA['rate']
        current_date = datetime.now().strftime('%d/%m/%Y')
        
        # Save to database
        save_success = save_to_database(session, total_amount, current_date)
        
        if save_success:
            # Send thank you message
            await event.reply(f"""✅ *Submission Complete!*

Thank you for your submission.

━━━━━━━━━━━━━━━━━━━━
📋 *Summary*
• Manifest No: *{session['manifest_no']}*
• Advance Amount: *₹{session['advance_amount']}*
• Quantity: *{value}*
• Rate: *₹{HARDCODED_DATA['rate']}*
• Total Amount: *₹{total_amount:.2f}*
• Date: *{current_date}*
━━━━━━━━━━━━━━━━━━━━

We will get back to you soon! 🙏""")
            
            print(f"✅ Session completed for {session['manifest_no']}")
            
            # Remove from pending
            del pending_sessions[user_id]
        else:
            await event.reply("❌ Error saving data. Please contact support.")


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
        
        # Update doc_processing_log status to Ready To Run
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
        print(f"✅ Database updated for doc_id {session['doc_id']} - Status: Ready To Run")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def process_message_queue(client):
    """Process outgoing messages from the queue"""
    while True:
        try:
            # Check queue every 0.5 seconds
            await asyncio.sleep(0.5)
            
            while not message_queue.empty():
                msg_data = message_queue.get_nowait()
                phone_no = msg_data['phone_no']
                manifest_no = msg_data['manifest_no']
                doc_id = msg_data['doc_id']
                result_queue = msg_data['result_queue']
                
                try:
                    success = await start_session_async(client, phone_no, manifest_no, doc_id)
                    result_queue.put(success)
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    result_queue.put(False)
                    
        except Exception as e:
            print(f"Queue processing error: {e}")


async def run_telegram_service():
    """Main function to run the Telegram service"""
    global _client, _loop, _running
    
    print("🚀 Starting Telegram Service...")
    print("=" * 50)
    
    _client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Register message handler
    @_client.on(events.NewMessage(incoming=True))
    async def message_handler(event):
        await handle_incoming_message(event)
    
    # Start client
    await _client.start(phone=PHONE)
    _running = True
    
    print("✅ Telegram service connected!")
    print("📱 Listening for messages...")
    print("=" * 50)
    
    # Start message queue processor
    asyncio.create_task(process_message_queue(_client))
    
    # Keep running
    await _client.run_until_disconnected()


def start_telegram_service():
    """Start the Telegram service in a background thread"""
    global _loop
    
    def run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_until_complete(run_telegram_service())
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    # Wait for client to connect
    import time
    for _ in range(30):  # Wait up to 15 seconds
        if _running:
            break
        time.sleep(0.5)
    
    return _running


def start_vehicle_hire_session(phone_no, manifest_no, doc_id):
    """Called from Flask to start a new session"""
    global _loop, _running
    
    if not _running:
        print("⚠️ Telegram service not running!")
        return False
    
    # Create result queue
    result_queue = queue.Queue()
    
    # Add to message queue
    message_queue.put({
        'phone_no': phone_no,
        'manifest_no': manifest_no,
        'doc_id': doc_id,
        'result_queue': result_queue
    })
    
    # Wait for result (timeout 30 seconds)
    try:
        result = result_queue.get(timeout=30)
        return result
    except queue.Empty:
        print("⚠️ Timeout waiting for message to send")
        return False


if __name__ == "__main__":
    asyncio.run(run_telegram_service())
