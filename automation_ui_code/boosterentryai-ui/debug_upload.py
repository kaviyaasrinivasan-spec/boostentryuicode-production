import requests
import os

# Configuration
BASE_URL = "http://localhost:30010/api/upload"
CLIENT_ID = 2  # JSW
DOC_FORMAT_ID = 2 # JSW Invoice Format

# Create a dummy PDF file
dummy_filename = "test_jsw_upload.pdf"
with open(dummy_filename, "wb") as f:
    f.write(b"%PDF-1.4\n%Dummy PDF content for testing JSW upload log creation.\n%%EOF")

try:
    print(f"Uploading {dummy_filename} for Client {CLIENT_ID}...")
    
    with open(dummy_filename, "rb") as f:
        files = {"files": (dummy_filename, f, "application/pdf")}
        data = {
            "client_id": CLIENT_ID,
            "doc_format_id": DOC_FORMAT_ID,
            "uploaded_by": "DEBUG_SCRIPT"
        }
        
        response = requests.post(BASE_URL, files=files, data=data)
        
    print(f"\nStatus Code: {response.status_code}")
    print("Response JSON:")
    try:
        print(response.json())
    except:
        print(response.text)

finally:
    # Cleanup
    if os.path.exists(dummy_filename):
        os.remove(dummy_filename)
