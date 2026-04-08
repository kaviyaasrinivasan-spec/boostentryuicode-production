# whatsapp_sender.py - Send WhatsApp messages using Askeva API
import requests
import json

# Askeva API Configuration
ASKEVA_API_URL = "https://backend.askeva.io/v1/message/send-message"
ASKEVA_API_KEY = "c0172afb175286d90590263a4fcaab0083e2211ab7393e7e3c2526634c0d9be331ce3e7a306fc706a7fdad6168809f4e1b71309d445abb9e7b884b5918614d7a"

def send_whatsapp_template(phone_no, template_name, template_params=None):
    """
    Send a WhatsApp template message using Askeva API
    
    Args:
        phone_no: Phone number with country code (e.g., "919876543210")
        template_name: Name of the approved WhatsApp template
        template_params: List of parameters to fill in the template (optional)
    """
    try:
        # Format phone number (should be with country code, no +)
        if phone_no.startswith('+'):
            phone_no = phone_no[1:]
        if not phone_no.startswith('91'):
            phone_no = '91' + phone_no
        
        # Build payload
        payload = {
            "to": phone_no,
            "type": "template",
            "template": {
                "language": {
                    "policy": "deterministic",
                    "code": "en"
                },
                "name": template_name
            }
        }
        
        # Add parameters if provided
        if template_params:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": param} for param in template_params
                    ]
                }
            ]
        
        # Make API request
        url = f"{ASKEVA_API_URL}?token={ASKEVA_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        print(f"📤 Sending WhatsApp template '{template_name}' to {phone_no}")
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"📤 Response: {response.status_code} - {response.text[:500]}")
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ WhatsApp template sent successfully to {phone_no}")
            return True
        else:
            print(f"❌ Failed to send template: {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Error sending WhatsApp template: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_vehicle_hire_request_whatsapp(phone_no, manifest_no, doc_id):
    """
    Send vehicle hire request via WhatsApp using approved template
    
    Template: vehiclehireadvance (APPROVED)
    Variable: manifestno
    """
    # Use the approved template with manifestno variable
    return send_whatsapp_template(phone_no, "vehicle_hire123", [manifest_no])


def send_whatsapp_text(phone_no, message):
    """
    Send a text message (only works within 24hr conversation window)
    This is for replying to customers who already messaged you
    """
    try:
        # Format phone number
        if phone_no.startswith('+'):
            phone_no = phone_no[1:]
        if not phone_no.startswith('91'):
            phone_no = '91' + phone_no
        
        # Build payload for text message
        payload = {
            "to": phone_no,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        url = f"{ASKEVA_API_URL}?token={ASKEVA_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        print(f"📤 Sending WhatsApp text to {phone_no}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"📤 Response: {response.status_code} - {response.text[:500]}")
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ WhatsApp message sent to {phone_no}")
            return True
        else:
            print(f"❌ Failed to send message: {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Error sending WhatsApp: {e}")
        return False


def get_available_templates():
    """Get list of available templates from Askeva"""
    try:
        url = f"https://backend.askeva.io/v1/templates?token={ASKEVA_API_KEY}"
        response = requests.get(url, timeout=30)
        
        print(f"📋 Available templates:")
        print(json.dumps(response.json(), indent=2))
        return response.json()
        
    except Exception as e:
        print(f"❌ Error getting templates: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "templates":
            # List available templates
            get_available_templates()
        else:
            # Test sending to a phone number
            test_phone = sys.argv[1]
            send_vehicle_hire_request_whatsapp(test_phone, "TEST123", 1)
    else:
        print("Usage:")
        print("  python whatsapp_sender.py templates      - List available templates")
        print("  python whatsapp_sender.py <phone>        - Test send to phone number")
