import os
import time
import requests
import io

# ---------- Configuration ----------
# TODO: REPLACE WITH THE ACTUAL TOKEN FOR TADAPATRI BRANCH BOT (Get from @BotFather)
TELEGRAM_BOT_TOKEN = "8688697362:AAGSRVBLGXEtc0FzMAlSrYa0QQRiBmkjVYM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Tadapatri (Client 3 - Format 3) Specific Configuration
CLIENT_ID = 3
DOC_FORMAT_ID = 3

# API Endpoint (Production)
UPLOAD_API_URL = "https://kssroadways.boostentryai.com/api/upload"

def upload_to_backend(raw_bytes, filename, mime_type):
    try:
        files_payload = {"file": (filename, io.BytesIO(raw_bytes), mime_type)}
        data = {
            "client_id": CLIENT_ID,
            "doc_format_id": DOC_FORMAT_ID,
            "uploaded_by": "TelegramBot_Tadapatri"
        }
        resp = requests.post(UPLOAD_API_URL, files=files_payload, data=data, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "success":
                final_name = filename
                if result.get("data") and len(result["data"]) > 0:
                    final_name = result["data"][0].get("final_name", filename)
                return True, f"Success! File processed as {final_name}"
            else:
                return False, result.get("message", "Unknown error from server")
        else:
            return False, f"Server returned status code {resp.status_code} - {resp.text}"
    except Exception as e:
        return False, f"Upload Error: {e}"

def handle_document(msg):
    chat_id = msg['chat']['id']
    
    # Handle both Documents and Photos
    if 'document' in msg:
        doc = msg['document']
        filename = doc.get('file_name', 'document.pdf')
        file_id = doc['file_id']
        mime_type = doc.get('mime_type', 'application/octet-stream')
    elif 'photo' in msg:
        doc = msg['photo'][-1] # Highest resolution
        filename = f"photo_{int(time.time())}.jpg"
        file_id = doc['file_id']
        mime_type = 'image/jpeg'
    else:
        return

    if not filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp')):
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ Only images/PDFs supported."})
        return

    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": f"⏳ Processing Tadapatri branch: {filename}..."})
    
    file_info = requests.get(f"{TELEGRAM_API_URL}/getFile", params={"file_id": file_id}).json()
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info['result']['file_path']}"
    file_data = requests.get(file_url).content
    
    success, msg_resp = upload_to_backend(file_data, filename, mime_type)
    text = f"✅ <b>Uploaded to Tadapatri!</b>\n{msg_resp}" if success else f"❌ <b>Failed</b>\n{msg_resp}"
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

def main():
    print(f"🤖 Tadapatri Bot started!")
    offset = None
    while True:
        try:
            resp = requests.get(f"{TELEGRAM_API_URL}/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35).json()
            if resp.get('ok') and resp.get('result'):
                for update in resp['result']:
                    offset = update['update_id'] + 1
                    if 'message' in update:
                        m = update['message']
                        if 'document' in m or 'photo' in m:
                            handle_document(m)
                        elif 'text' in m and m['text'] == '/start':
                            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                                "chat_id": m['chat']['id'],
                                "text": "👋 Welcome to <b>Tadapatri Branch Upload Bot</b>!\n\nPlease upload any <b>PDF invoice</b> or <b>Photo</b> to process it instantly.",
                                "parse_mode": "HTML"
                            })
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
