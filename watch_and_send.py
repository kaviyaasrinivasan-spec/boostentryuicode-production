#!/usr/bin/env python3
"""
watch_and_send.py (Enhanced)

Monitors the Ready_to_Run folder for PDF files and sends them to the local FastAPI endpoint
(http://127.0.0.1:5213/insert). On success, moves the file to Inprogress.

âœ¨ Improvements:
- Auto-detects filenames missing underscores before "Invoice", "PurchaseOrder", "DeliveryChallan", etc.
- Automatically renames them (adds underscores) before upload.
- Prevents "Failed: Missing IDs" due to misformatted filenames.

Author: WorkBooster Automation
"""

import os
import re
import time
import logging
import shutil
import requests
from datetime import datetime

# ----------------------------
# Configuration
# ----------------------------
BASE_DIR = "/root/Boostentry_AI_Doc_Processing"
READY_DIR = os.path.join(BASE_DIR, "Ready_to_Run")
INPROGRESS_DIR = os.path.join(BASE_DIR, "Inprogress")
API_URL = "http://127.0.0.1:5213/insert"
LOG_FILE = "/var/log/doc_watcher.log"

# ----------------------------
# Logging setup
# ----------------------------
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("doc_watcher")

# ----------------------------
# Ensure folders exist
# ----------------------------
for d in [READY_DIR, INPROGRESS_DIR]:
    os.makedirs(d, exist_ok=True)


# ----------------------------
# Filename Normalizer
# ----------------------------
def normalize_filename(filename: str) -> str:
    """
    Detects and fixes missing underscores in filenames like:
    UltraTechCementInvoice2025-10-13_07-23-31.pdf
    â†’ UltraTechCement_Invoice_2025-10-13_07-23-31.pdf
    """
    patterns = ["Invoice", "PurchaseOrder", "DeliveryChallan", "PO", "GRN"]
    for keyword in patterns:
        # Detect e.g., UltraTechCementInvoice2025...
        if re.search(rf"[A-Za-z]+{keyword}\d{{4}}-", filename):
            fixed = re.sub(rf"({keyword})(\d{{4}}-)", r"_\1_\2", filename)
            fixed = re.sub(rf"([A-Za-z])({keyword})", r"\1_\2", fixed)
            if fixed != filename:
                logger.info(f"ðŸ§© Renamed for missing underscore: {filename} â†’ {fixed}")
                return fixed
    return filename


# ----------------------------
# Function to send one file
# ----------------------------
def process_file(file_path):
    try:
        file_name = os.path.basename(file_path)

        # âœ… Normalize filename before sending
        new_name = normalize_filename(file_name)
        if new_name != file_name:
            new_path = os.path.join(READY_DIR, new_name)
            os.rename(file_path, new_path)
            file_path = new_path
            file_name = new_name

        uploaded_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Processing file: {file_name} (uploaded_on={uploaded_on})")

        # POST to FastAPI
        data = {
            "doc_name": file_name,
            "uploaded_on": uploaded_on,
        }

        response = requests.post(API_URL, data=data, timeout=30)
        if response.status_code == 200:
            logger.info(f"âœ… Insert success for {file_name}: {response.text}")

            # Move file to Inprogress
            dest_path = os.path.join(INPROGRESS_DIR, file_name)
            shutil.move(file_path, dest_path)
            logger.info(f"Moved {file_name} â†’ Inprogress folder")

        else:
            logger.error(f"âŒ Failed insert for {file_name}: {response.status_code} {response.text}")

    except Exception as e:
        logger.exception(f"Error processing {file_path}: {e}")


# ----------------------------
# Main execution
# ----------------------------
def main():
    try:
        files = [f for f in os.listdir(READY_DIR) if f.lower().endswith(".pdf")]
        if not files:
            logger.info("No PDF files found in Ready_to_Run. Nothing to do.")
            return

        logger.info(f"Found {len(files)} file(s) in Ready_to_Run: {files}")

        for f in files:
            full_path = os.path.join(READY_DIR, f)
            process_file(full_path)

    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")


if __name__ == "__main__":
    main()
