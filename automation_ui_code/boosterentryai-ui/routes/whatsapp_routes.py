# routes/whatsapp_routes.py - WhatsApp webhook and API routes
from flask import Blueprint, request, jsonify
import json

whatsapp_bp = Blueprint('whatsapp', __name__)

# Askeva API Configuration
ASKEVA_API_KEY = "099cedfda84c2f24adbf55988b6255517f97afa2011094e7b4e5bd7f19cc2c007ba52f9b2287b224f77b982a27221f11f8af30b0db86323d04beab45794649cf"

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


@whatsapp_bp.route('/api/whatsapp/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """Webhook endpoint for receiving WhatsApp messages from Askeva"""
    
    # GET request - webhook verification
    if request.method == 'GET':
        # Askeva might send verification challenge
        challenge = request.args.get('challenge') or request.args.get('hub.challenge')
        if challenge:
            return challenge, 200
        return jsonify({'status': 'webhook active'}), 200
    
    # POST request - incoming message
    try:
        data = request.get_json() or {}
        print(f"📥 WhatsApp Webhook received: {json.dumps(data, indent=2)}")
        
        # Extract message details based on Askeva's format
        # This may need adjustment based on actual Askeva webhook format
        message_data = extract_message_data(data)
        
        if message_data:
            phone = message_data.get('phone')
            text = message_data.get('text', '').strip()
            
            if phone and text:
                print(f"📨 WhatsApp message from {phone}: {text}")
                process_whatsapp_reply(phone, text)
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def extract_message_data(data):
    """Extract phone number and text from Askeva webhook payload"""
    try:
        # Try different payload formats that Askeva might use
        
        # Format 1: Direct fields
        if 'from' in data and 'text' in data:
            return {
                'phone': data['from'],
                'text': data['text'].get('body') if isinstance(data['text'], dict) else data['text']
            }
        
        # Format 2: Nested in 'message'
        if 'message' in data:
            msg = data['message']
            return {
                'phone': msg.get('from') or data.get('from'),
                'text': msg.get('text', {}).get('body') or msg.get('body') or msg.get('text')
            }
        
        # Format 3: WhatsApp Cloud API format
        if 'entry' in data:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    if messages:
                        msg = messages[0]
                        return {
                            'phone': msg.get('from'),
                            'text': msg.get('text', {}).get('body')
                        }
        
        # Format 4: Simple format
        if 'phone' in data or 'mobile' in data:
            return {
                'phone': data.get('phone') or data.get('mobile'),
                'text': data.get('message') or data.get('text') or data.get('body')
            }
        
        print(f"⚠️ Unknown webhook format: {data}")
        return None
        
    except Exception as e:
        print(f"❌ Error extracting message: {e}")
        return None


def process_whatsapp_reply(phone, text):
    """Process incoming WhatsApp reply from driver"""
    from config.db_config import get_connection, release_connection
    from datetime import datetime
    
    try:
        # Normalize phone number
        phone_normalized = phone.replace('+', '').replace('91', '', 1) if phone.startswith('91') or phone.startswith('+91') else phone
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Find active session for this phone
        cur.execute("""
            SELECT doc_id, phone_no, manifest_no, advance_amount, qty, status
            FROM telegram_pending_sessions 
            WHERE (phone_no = %s OR phone_no = %s OR phone_no = %s)
              AND status != 'completed'
            ORDER BY created_at DESC
            LIMIT 1
        """, (phone, phone_normalized, '+91' + phone_normalized))
        
        session = cur.fetchone()
        
        if not session:
            print(f"⚠️ No active session for {phone}")
            release_connection(conn)
            return
        
        doc_id, db_phone, manifest_no, advance_amount, qty, status = session
        
        # Validate input is a number
        try:
            value = float(text)
            if value <= 0:
                raise ValueError("Must be positive")
        except ValueError:
            # Send error message
            send_error_reply(phone, advance_amount)
            release_connection(conn)
            return
        
        if advance_amount is None:
            # Waiting for advance amount
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET advance_amount = %s, status = 'waiting_qty', updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s
            """, (value, doc_id))
            conn.commit()
            
            print(f"📥 Advance Amount: ₹{value} for {manifest_no}")
            send_quantity_request(phone, value)
        else:
            # Waiting for quantity - complete the session
            total_amount = value * HARDCODED_DATA['rate']
            current_date = datetime.now().strftime('%Y-%m-%d')  # PostgreSQL format
            
            # Insert into vehicle_hire
            cur.execute("""
                INSERT INTO vehicle_hire 
                (doc_id, manifest_no, advance_amount, payable_at, paid_by, account, 
                 paymode, filling_station, slip_no, slip_date, qty, rate, amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                doc_id, manifest_no, advance_amount,
                HARDCODED_DATA['payable_at'], HARDCODED_DATA['paid_by'],
                HARDCODED_DATA['account'], HARDCODED_DATA['paymode'],
                HARDCODED_DATA['filling_station'], HARDCODED_DATA['slip_no'],
                current_date, value, HARDCODED_DATA['rate'], total_amount
            ))
            
            # Update status
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET status = 'completed', qty = %s, updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s
            """, (value, doc_id))
            
            cur.execute("""
                UPDATE doc_processing_log
                SET vehicle_hire_status = 'Ready To Run', updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s
            """, (doc_id,))
            
            conn.commit()
            print(f"✅ Session completed for {manifest_no}")
            
            send_completion_message(phone, manifest_no, advance_amount, value, total_amount)
        
        release_connection(conn)
        
    except Exception as e:
        print(f"❌ Error processing reply: {e}")
        import traceback
        traceback.print_exc()


def send_whatsapp_reply(phone, message):
    """Send a reply message via WhatsApp"""
    try:
        from whatsapp_sender import send_whatsapp_text
        # Use text message for replies (within 24hr window)
        send_whatsapp_text(phone, message)
    except Exception as e:
        print(f"⚠️ Could not send reply: {e}")


def send_error_reply(phone, advance_amount):
    """Send error message for wrong format"""
    if advance_amount is None:
        msg = "❌ *Wrong Format!*\n\nPlease enter a valid *Advance Amount* (numbers only).\n\n*Example:* `2000`"
    else:
        msg = "❌ *Wrong Format!*\n\nPlease enter a valid *Quantity* (numbers only).\n\n*Example:* `200`"
    send_whatsapp_reply(phone, msg)


def send_quantity_request(phone, advance_value):
    """Send request for quantity after receiving advance"""
    msg = f"""✅ *Advance Amount Received!*

We have received: *₹{advance_value}*

━━━━━━━━━━━━━━━━━━━━
📦 Now please enter the *Quantity*

*Example:* `200`
━━━━━━━━━━━━━━━━━━━━"""
    send_whatsapp_reply(phone, msg)


def send_completion_message(phone, manifest_no, advance, qty, total):
    """Send completion confirmation"""
    msg = f"""✅ *Submission Complete!*

Thank you for your submission.

━━━━━━━━━━━━━━━━━━━━
📋 *Summary*
• Manifest No: *{manifest_no}*
• Advance: *₹{advance}*
• Quantity: *{qty}*
• Rate: *₹{HARDCODED_DATA['rate']}*
• Total: *₹{total:.2f}*
━━━━━━━━━━━━━━━━━━━━

We will get back to you soon! 🙏"""
    send_whatsapp_reply(phone, msg)
