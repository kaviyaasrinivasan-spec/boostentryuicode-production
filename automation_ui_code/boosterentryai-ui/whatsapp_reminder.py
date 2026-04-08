# whatsapp_reminder.py - Background scheduler for WhatsApp reminders
"""
Sends reminder messages to users who haven't responded to vehicle hire requests.
- Checks every 30 minutes for pending sessions
- Sends reminder if no response for 3 hours
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import atexit

# Reminder interval in hours
REMINDER_INTERVAL_HOURS = 3

scheduler = None


def check_pending_sessions():
    """Check for sessions that need reminders"""
    from config.db_config import get_connection, release_connection
    from whatsapp_sender import send_whatsapp_text
    
    print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] Checking for pending WhatsApp sessions...")
    
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Find sessions that haven't been updated in REMINDER_INTERVAL_HOURS
        reminder_threshold = datetime.now() - timedelta(hours=REMINDER_INTERVAL_HOURS)
        
        cur.execute("""
            SELECT id, doc_id, phone_no, manifest_no, advance_amount, status, updated_at
            FROM telegram_pending_sessions 
            WHERE status IN ('pending', 'waiting_advance', 'waiting_qty')
              AND updated_at < %s
            ORDER BY updated_at ASC
        """, (reminder_threshold,))
        
        sessions = cur.fetchall()
        
        if not sessions:
            print(f"   ✅ No pending sessions need reminders")
            release_connection(conn)
            return
        
        print(f"   📋 Found {len(sessions)} sessions needing reminders")
        
        for session in sessions:
            session_id, doc_id, phone_no, manifest_no, advance_amount, status, updated_at = session
            
            # Format phone number
            if not phone_no.startswith('+'):
                phone_no = '+91' + phone_no.replace('+91', '').replace('91', '', 1)
            
            # Determine which message to send
            if advance_amount is None:
                # Still waiting for advance amount
                message = f"""⏰ *Reminder*

Manifest No: *{manifest_no}*

We're still waiting for your *Advance Amount*.

Please reply with the amount.
*Example:* 2000"""
            else:
                # Waiting for quantity
                message = f"""⏰ *Reminder*

Manifest No: *{manifest_no}*
Advance Amount: *₹{advance_amount}*

We're still waiting for the *Quantity*.

Please reply with the quantity.
*Example:* 200"""
            
            # Send reminder
            try:
                send_whatsapp_text(phone_no, message)
                print(f"   ⏰ Sent reminder to {phone_no} for {manifest_no}")
                
                # Update the updated_at timestamp to prevent repeated reminders
                cur.execute("""
                    UPDATE telegram_pending_sessions 
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (session_id,))
                conn.commit()
                
            except Exception as e:
                print(f"   ⚠️ Failed to send reminder to {phone_no}: {e}")
        
    except Exception as e:
        print(f"❌ Error checking pending sessions: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            release_connection(conn)


def start_reminder_scheduler():
    """Start the background scheduler for reminders"""
    global scheduler
    
    if scheduler is not None:
        print("⚠️ Reminder scheduler already running")
        return
    
    scheduler = BackgroundScheduler()
    
    # Run check every 30 minutes
    scheduler.add_job(
        func=check_pending_sessions,
        trigger='interval',
        minutes=30,
        id='whatsapp_reminder_job',
        name='WhatsApp Reminder Check',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ WhatsApp reminder scheduler started (checks every 30 mins, reminds after 3 hours)")
    
    # Shut down scheduler when app stops
    atexit.register(lambda: scheduler.shutdown(wait=False))


def stop_reminder_scheduler():
    """Stop the background scheduler"""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        print("🛑 WhatsApp reminder scheduler stopped")


if __name__ == "__main__":
    # Test the reminder check
    print("Testing reminder check...")
    check_pending_sessions()
