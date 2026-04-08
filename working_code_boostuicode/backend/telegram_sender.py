# telegram_sender.py - Send Telegram messages using Telethon (synchronous wrapper)
import asyncio
from telethon import TelegramClient
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest

# Telegram API Credentials
API_ID = 30174846
API_HASH = "226783f8520d79c6a5ac471ef2f9ce81"
PHONE = "+918122715213"
SESSION_NAME = "vehicle_hire_sender"  # Different from listener to avoid lock


async def _send_message(phone_no, message, doc_id, manifest_no):
    """Internal async function to send message"""
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    
    try:
        # Format phone number
        if not phone_no.startswith('+'):
            phone_no = '+91' + phone_no
        
        # Try to get the user entity
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
        print(f"✅ Message sent to {phone_no}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False
    finally:
        await client.disconnect()


def send_telegram_message(phone_no, message, doc_id=None, manifest_no=None):
    """Synchronous wrapper to send Telegram message"""
    import sys
    print(f"📱 send_telegram_message called for {phone_no}", flush=True)
    sys.stdout.flush()
    
    try:
        # Check if there's already a running event loop
        try:
            loop = asyncio.get_running_loop()
            print(f"📱 Existing event loop found, using run_coroutine_threadsafe", flush=True)
            # If there's already a loop, we need to use a different approach
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _send_message(phone_no, message, doc_id, manifest_no))
                result = future.result(timeout=60)
                print(f"📱 Result from thread: {result}", flush=True)
                return result
        except RuntimeError:
            # No running event loop, create a new one
            print(f"📱 No running event loop, creating new one", flush=True)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_send_message(phone_no, message, doc_id, manifest_no))
                print(f"📱 Result: {result}", flush=True)
                return result
            finally:
                loop.close()
    except Exception as e:
        print(f"❌ Error in send_telegram_message: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


def send_vehicle_hire_request(phone_no, manifest_no, doc_id):
    """Send vehicle hire request asking for Advance Amount first"""
    message = f"""📋 *Vehicle Hire Confirmation*

Manifest No: *{manifest_no}*

━━━━━━━━━━━━━━━━━━━━
💰 Please enter the *Advance Amount*

*Format:* Just type the number
*Example:* `2000`
━━━━━━━━━━━━━━━━━━━━"""
    
    return send_telegram_message(phone_no, message, doc_id, manifest_no)


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        test_phone = sys.argv[1]
        send_vehicle_hire_request(test_phone, "ARAK2506601", 1)
