# telegram_user_client.py - Telegram Reply Listener for Vehicle Hire
# Uses Telethon to listen for replies from specific phone numbers

import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest
from datetime import datetime
import sys
import os

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

# Store sessions by phone number
# Format: {phone_no: {doc_id, manifest_no, advance_amount, qty, state, user_id}}
sessions_by_phone = {}


# Reminder settings
REMINDER_INTERVAL_MINUTES = 20  # Send reminder after 20 minutes of no response


def get_active_sessions_with_time():
    """Get all active sessions from database with timestamps"""
    try:
        from config.db_config import get_connection, release_connection
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT doc_id, phone_no, manifest_no, advance_amount, qty, status, 
                   COALESCE(updated_at, created_at) as last_activity
            FROM telegram_pending_sessions 
            WHERE status != 'completed'
        """)
        
        rows = cur.fetchall()
        release_connection(conn)
        
        sessions = {}
        for row in rows:
            doc_id, phone_no, manifest_no, advance_amount, qty, status, last_activity = row
            # Normalize phone number (remove +91 if present)
            normalized = phone_no.replace('+91', '') if phone_no else ''
            sessions[normalized] = {
                'doc_id': doc_id,
                'phone_no': phone_no,
                'manifest_no': manifest_no,
                'advance_amount': advance_amount,
                'qty': qty,
                'state': 'waiting_qty' if advance_amount else 'waiting_advance',
                'last_activity': last_activity,
                'reminder_sent': False
            }
        
        return sessions
        
    except Exception as e:
        print(f"❌ Error loading sessions: {e}")
        return {}


def get_active_sessions():
    """Get all active sessions from database (without time info)"""
    sessions = get_active_sessions_with_time()
    # Remove time-specific fields for backward compatibility
    for phone in sessions:
        if 'last_activity' in sessions[phone]:
            del sessions[phone]['last_activity']
        if 'reminder_sent' in sessions[phone]:
            del sessions[phone]['reminder_sent']
    return sessions


def update_session_advance(doc_id, advance_amount):
    """Update advance amount in database"""
    try:
        from config.db_config import get_connection, release_connection
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE telegram_pending_sessions 
            SET advance_amount = %s,
                status = 'waiting_qty',
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """, (advance_amount, doc_id))
        
        conn.commit()
        release_connection(conn)
        print(f"📝 Updated advance amount for doc_id {doc_id}")
        
    except Exception as e:
        print(f"❌ Error updating session: {e}")


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
        print(f"✅ Database updated for doc_id {session['doc_id']} - Status: Ready To Run")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main function to run the Telegram listener"""
    global sessions_by_phone
    
    print("🚀 Starting Vehicle Hire Telegram Listener...")
    print("=" * 50)
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    print("✅ Telegram listener connected!")
    
    # Load sessions
    sessions_by_phone = get_active_sessions()
    print(f"📋 Loaded {len(sessions_by_phone)} active sessions")
    for phone, session in sessions_by_phone.items():
        print(f"   📱 {phone} -> {session['manifest_no']} ({session['state']})")
    
    print("=" * 50)
    print("📱 Waiting for messages from these phone numbers...")
    print("=" * 50)
    
    # Handle ALL incoming messages
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        global sessions_by_phone
        
        sender = await event.get_sender()
        if not sender:
            return
        
        # Get sender's phone number
        sender_phone = getattr(sender, 'phone', None)
        if not sender_phone:
            print(f"⚠️ Message from user {sender.id} but no phone number available")
            return
        
        # Normalize phone (remove + and country code)
        normalized_phone = sender_phone.replace('+', '').replace('91', '', 1) if sender_phone.startswith('+91') or sender_phone.startswith('91') else sender_phone
        
        print(f"📨 Message from {sender_phone} (normalized: {normalized_phone}): {event.text}")
        
        # Refresh sessions from database
        sessions_by_phone = get_active_sessions()
        
        # Check if this phone has an active session
        session = sessions_by_phone.get(normalized_phone)
        if not session:
            # Try with full phone number
            session = sessions_by_phone.get(sender_phone)
        
        if not session:
            print(f"⚠️ No active session for phone {sender_phone}")
            return
        
        text = event.text.strip() if event.text else ""
        
        # Validate the input is a number
        try:
            value = float(text)
            if value <= 0:
                raise ValueError("Must be positive")
        except ValueError:
            if session['state'] == 'waiting_advance':
                await event.reply("❌ *Wrong Format!*\n\nPlease enter a valid *Advance Amount* (numbers only).\n\n*Example:* `2000`")
            else:
                await event.reply("❌ *Wrong Format!*\n\nPlease enter a valid *Quantity* (numbers only).\n\n*Example:* `200`")
            return
        
        # Process based on state
        if session['state'] == 'waiting_advance':
            # Save advance amount
            session['advance_amount'] = value
            session['state'] = 'waiting_qty'
            
            update_session_advance(session['doc_id'], value)
            
            await event.reply(f"""✅ *Advance Amount Received!*

We have received: *₹{value}*

━━━━━━━━━━━━━━━━━━━━
📦 Now please enter the *Quantity*

*Example:* `200`
━━━━━━━━━━━━━━━━━━━━""")
            
            print(f"📥 Advance Amount: ₹{value} for {session['manifest_no']}")
            
        elif session['state'] == 'waiting_qty':
            # Save quantity
            session['qty'] = value
            
            # Calculate total
            total_amount = value * HARDCODED_DATA['rate']
            current_date = datetime.now().strftime('%d/%m/%Y')
            
            if save_to_database(session, total_amount, current_date):
                await event.reply(f"""✅ *Submission Complete!*

Thank you for your submission.

━━━━━━━━━━━━━━━━━━━━
📋 *Summary*
• Manifest No: *{session['manifest_no']}*
• Advance: *₹{session['advance_amount']}*
• Quantity: *{value}*
• Rate: *₹{HARDCODED_DATA['rate']}*
• Total: *₹{total_amount:.2f}*
━━━━━━━━━━━━━━━━━━━━

We will get back to you soon! 🙏""")
                
                print(f"✅ Session completed for {session['manifest_no']}")
                
                # Remove from local cache
                if normalized_phone in sessions_by_phone:
                    del sessions_by_phone[normalized_phone]
            else:
                await event.reply("❌ Error saving data. Please contact support.")
    
    # Background task to send reminders
    async def reminder_task():
        """Send reminders to users who haven't replied in 20 minutes"""
        sent_reminders = set()  # Track which sessions got reminders
        
        while True:
            await asyncio.sleep(60)  # Check every 1 minute
            
            try:
                from config.db_config import get_connection, release_connection
                from datetime import timedelta
                
                conn = get_connection()
                cur = conn.cursor()
                
                # Find sessions that are still pending and older than 20 minutes
                cur.execute("""
                    SELECT doc_id, phone_no, manifest_no, advance_amount, status
                    FROM telegram_pending_sessions 
                    WHERE status != 'completed'
                      AND updated_at < NOW() - INTERVAL '%s minutes'
                """, (REMINDER_INTERVAL_MINUTES,))
                
                stale_sessions = cur.fetchall()
                release_connection(conn)
                
                for row in stale_sessions:
                    doc_id, phone_no, manifest_no, advance_amount, status = row
                    
                    # Only send one reminder per session
                    if doc_id in sent_reminders:
                        continue
                    
                    try:
                        # Format phone
                        if phone_no and not phone_no.startswith('+'):
                            phone_no = '+91' + phone_no
                        
                        entity = await client.get_entity(phone_no)
                        
                        if advance_amount:
                            # Waiting for quantity
                            reminder_msg = f"""⏰ *Reminder*

Manifest No: *{manifest_no}*

We're still waiting for your *Quantity* response.

Please reply with just the number.
*Example:* `200`"""
                        else:
                            # Waiting for advance amount
                            reminder_msg = f"""⏰ *Reminder*

Manifest No: *{manifest_no}*

We're still waiting for your *Advance Amount* response.

Please reply with just the number.
*Example:* `2000`"""
                        
                        await client.send_message(entity, reminder_msg)
                        sent_reminders.add(doc_id)
                        print(f"⏰ Sent reminder to {phone_no} for {manifest_no}")
                        
                    except Exception as e:
                        print(f"⚠️ Could not send reminder to {phone_no}: {e}")
                        
            except Exception as e:
                print(f"⚠️ Reminder task error: {e}")
    
    # Start reminder task in background
    asyncio.create_task(reminder_task())
    print("⏰ Reminder task started (will remind after 20 mins of no response)")
    
    # Keep running
    print("\n🔄 Listener is active. Press Ctrl+C to stop.\n")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
