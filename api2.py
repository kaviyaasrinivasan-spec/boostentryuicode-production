#!/usr/bin/env python3
"""
watch_extract_and_update_sequential.py

Linux-only, single-pass by default watcher.

Behavior:
 - Picks one pending row at a time (data_extraction_status = 'Not Started')
 - Finds the PDF file in Inprogress folder
 - Posts the PDF to extractor with client_id & format_id as query params
 - Waits for JSON response, saves per-file JSON to disk (audit), updates DB extracted_json and sets status Completed
 - After DB commit, moves the file to Processed folder (atomic move)
 - Exits after one full pass by default (LOOP_MODE=false). Can run continuously if LOOP_MODE=true.
"""

from __future__ import annotations
import os
import sys
import json
import time
import shutil
import logging
import signal
from typing import Optional, Dict, Any

import requests
import psycopg2
from psycopg2.extras import Json

# ----------------------------
# CONFIGURATION (Linux defaults)
# ----------------------------
# Database (override with env vars)
DB_HOST = os.getenv("PGHOST", "103.14.121.15")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "mydb")
DB_USER = os.getenv("PGUSER", "sql_developer")
DB_PASSWORD = os.getenv("PGPASSWORD", "Dev@123")

# Base folder for processing (Linux)
BASE_PATH = os.path.expanduser(os.getenv("BASE_PATH", "~/Boostentry_AI_Doc_Processing"))

# Where watcher looks for PDFs (pick location)
LOCAL_PDF_DIR = os.path.join(BASE_PATH, "Inprogress")

# Where PDFs are moved after successful processing
PROCESSED_DIR = os.path.join(BASE_PATH, "Processed")

# Where final JSON(s) are saved (per-file JSON) and audit
SCHEMAS_DIR = os.path.join(BASE_PATH, "Schemas")

# Per-file JSON filename pattern: <original_filename>.json
# (e.g. UltraTechCement_Invoice_2025-10-17_19-28-04.pdf -> UltraTechCement_Invoice_2025-10-17_19-28-04.pdf.json)
FINAL_JSON_SUFFIX = os.getenv("FINAL_JSON_SUFFIX", ".json")

# Extractor endpoint (override via env)
EXTRACTOR_URL = os.getenv("EXTRACTOR_URL", "http://103.14.121.15:8000/extract")

# Behavior: default single pass. Set env LOOP_MODE=true to run continuously.
LOOP_MODE = os.getenv("LOOP_MODE", "false").lower() in ("1", "true", "yes")
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "30"))
EXTRACTOR_TIMEOUT = int(os.getenv("EXTRACTOR_TIMEOUT", "300"))

# If no pending rows, number of checks before exiting (only used when LOOP_MODE is true)
NO_PENDING_EXIT_THRESHOLD = int(os.getenv("NO_PENDING_EXIT_THRESHOLD", "2"))

# Logging
LOG_FILE = os.getenv("WATCH_LOG", os.path.join(BASE_PATH, "watch_extract_and_update.log"))
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
)
logger = logging.getLogger("watch_extract_and_update")

# ----------------------------
# SQL statements (single-row)
# ----------------------------
SELECT_ONE_PENDING_SQL = """
SELECT doc_id, client_id, doc_format_id, doc_file_name
FROM doc_processing_log
WHERE data_extraction_status = 'Not Started'
ORDER BY doc_id
LIMIT 1;
"""

UPDATE_SUCCESS_SQL = """
UPDATE doc_processing_log
SET extracted_json = %s,
    data_extraction_status = 'Completed',
    updated_at = now()
WHERE doc_id = %s;
"""

UPDATE_FAILED_SQL = """
UPDATE doc_processing_log
SET data_extraction_status = %s,
    updated_at = now()
WHERE doc_id = %s;
"""

# ----------------------------
# DB helpers
# ----------------------------
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )

# ----------------------------
# FS helpers
# ----------------------------
def ensure_dirs():
    """Create required directories (Inprogress, Processed, Schemas)."""
    for p in (LOCAL_PDF_DIR, PROCESSED_DIR, SCHEMAS_DIR):
        os.makedirs(p, exist_ok=True)
        logger.info("Ensured directory exists: %s", p)

def find_local_file(doc_name: str) -> Optional[str]:
    """
    Case-insensitive search for doc_name inside LOCAL_PDF_DIR.
    Returns absolute path or None.
    """
    candidate = os.path.join(LOCAL_PDF_DIR, doc_name)
    if os.path.isfile(candidate):
        return candidate
    lname = doc_name.lower()
    for f in os.listdir(LOCAL_PDF_DIR):
        if f.lower() == lname:
            return os.path.join(LOCAL_PDF_DIR, f)
    return None

def save_json_audit(doc_name: str, payload: Dict[str, Any]) -> str:
    """
    Save per-file JSON in SCHEMAS_DIR with the pattern: <doc_name>.json
    Returns path to saved JSON.
    """
    safe_name = f"{doc_name}{FINAL_JSON_SUFFIX}"
    dest = os.path.join(SCHEMAS_DIR, safe_name)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    logger.info("Saved extracted JSON to %s", dest)
    return dest

def atomic_move(src: str, dst_dir: str) -> bool:
    """
    Move src file into dst_dir atomically (shutil.move is used).
    Returns True on success.
    """
    try:
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(src))
        shutil.move(src, dst)
        logger.info("Moved %s → %s", src, dst)
        return True
    except Exception:
        logger.exception("Failed moving %s → %s", src, dst_dir)
        return False

# ----------------------------
# Extractor call
# ----------------------------
def call_extractor(file_path: str, client_id: int, format_id: int) -> dict:
    """
    POST file to extractor with query params ?client_id=&format_id=
    Returns parsed JSON (raises on non-200).
    """
    url = f"{EXTRACTOR_URL}?client_id={client_id}&format_id={format_id}"
    logger.info("Calling extractor %s (file=%s)", url, file_path)
    
    # Detect MIME type based on file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    content_type = mime_types.get(file_ext, "application/octet-stream")
    
    with open(file_path, "rb") as fh:
        files = {"file": (os.path.basename(file_path), fh, content_type)}
        resp = requests.post(url, files=files, timeout=EXTRACTOR_TIMEOUT)
    try:
        data = resp.json()
    except Exception:
        # raise HTTP error if not JSON
        resp.raise_for_status()
        raise
    if resp.status_code != 200:
        raise RuntimeError(f"Extractor returned {resp.status_code}: {data}")
    return data

# ----------------------------
# Process logic for one DB row
# ----------------------------
def process_one_row() -> bool:
    """
    Fetch a single pending row and process. Returns True if a row was processed or updated (even if failed).
    Returns False if no pending rows exist.
    """
    ensure_dirs()
    conn = None
    cur = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(SELECT_ONE_PENDING_SQL)
        row = cur.fetchone()
    except Exception as e:
        logger.exception("DB fetch error: %s", e)
        if cur: cur.close()
        if conn: conn.close()
        return False

    if not row:
        logger.info("No pending rows found")
        cur.close(); conn.close()
        return False

    doc_id, client_id, doc_format_id, doc_file_name = row
    logger.info("Processing doc_id=%s file=%s client_id=%s format_id=%s", doc_id, doc_file_name, client_id, doc_format_id)

    # Validate required ids
    if client_id is None or doc_format_id is None:
        logger.warning("Missing client_id/doc_format_id for doc_id=%s — marking Failed: Missing IDs", doc_id)
        try:
            cur.execute(UPDATE_FAILED_SQL, ("Failed: Missing IDs", doc_id))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close(); conn.close()
        return True

    # Find file in Inprogress
    local_file = find_local_file(doc_file_name)
    if not local_file:
        logger.warning("File %s not found in Inprogress — marking Failed: File Missing", doc_file_name)
        try:
            cur.execute(UPDATE_FAILED_SQL, ("Failed: File Missing", doc_id))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close(); conn.close()
        return True

    # Call extractor and update DB
    try:
        response = call_extractor(local_file, client_id, doc_format_id)
        # The extractor may return {"final_data": {...}} or the final JSON directly
        extracted = response.get("final_data") or response.get("final") or response

        # Save per-file JSON for audit: <doc_file_name>.json in SCHEMAS_DIR
        save_json_audit(doc_file_name, extracted)

        # Update DB with JSON (use psycopg2 Json adapter)
        cur.execute(UPDATE_SUCCESS_SQL, (Json(extracted), doc_id))
        conn.commit()
        logger.info("DB updated for doc_id=%s (set data_extraction_status=Completed)", doc_id)

        # Move file into Processed only after successful DB commit
        if not atomic_move(local_file, PROCESSED_DIR):
            logger.warning("Processed DB updated but move to Processed failed for %s", local_file)

    except Exception as e:
        logger.exception("Extraction failed for doc_id=%s: %s", doc_id, e)
        try:
            cur.execute(UPDATE_FAILED_SQL, ("Failed: Extract error", doc_id))
            conn.commit()
        except Exception:
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()

    return True

# ----------------------------
# Graceful shutdown helper
# ----------------------------
_stop_requested = False
def _signal_handler(signum, frame):
    global _stop_requested
    _stop_requested = True
    logger.info("Signal %s received — will stop after current iteration", signum)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# ----------------------------
# Main loop / single pass
# ----------------------------
def main():
    logger.info("Starting watcher (Linux-only)")
    logger.info("PDF pick location (Inprogress): %s", LOCAL_PDF_DIR)
    logger.info("PDF destination (Processed): %s", PROCESSED_DIR)
    logger.info("JSON audit location (Schemas): %s", SCHEMAS_DIR)
    logger.info("Extractor URL: %s", EXTRACTOR_URL)
    logger.info("LOOP_MODE=%s SLEEP_SECONDS=%s", LOOP_MODE, SLEEP_SECONDS)

    no_pending = 0
    try:
        while True:
            if _stop_requested:
                logger.info("Stop requested, exiting loop")
                break

            processed = process_one_row()
            if processed:
                # reset no_pending counter (we processed at least one DB row or marked one failed)
                no_pending = 0
            else:
                no_pending += 1
                logger.info("No pending count: %d/%d", no_pending, NO_PENDING_EXIT_THRESHOLD)

            # If we run single-pass (LOOP_MODE=False), exit after one full pass
            if not LOOP_MODE:
                logger.info("Single-pass mode (LOOP_MODE=false) — exiting after one run")
                break

            # In LOOP_MODE, exit only after NO_PENDING_EXIT_THRESHOLD consecutive empty passes
            if LOOP_MODE and no_pending >= NO_PENDING_EXIT_THRESHOLD:
                logger.info("No pending rows for %d consecutive checks — exiting", NO_PENDING_EXIT_THRESHOLD)
                break

            time.sleep(SLEEP_SECONDS)

    except Exception:
        logger.exception("Fatal error in main loop")
    finally:
        logger.info("Watcher stopped cleanly")

if __name__ == "__main__":
    main()
