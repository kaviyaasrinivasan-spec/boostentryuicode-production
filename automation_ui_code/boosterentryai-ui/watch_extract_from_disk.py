#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch_extract_from_disk.py

Loops until there are no rows with data_extraction_status = 'Not Started'.
Reads PDF from FILESYSTEM (saved_path) instead of database BYTEA.

FIXED: Uses filesystem storage for faster processing.
"""

import os
import sys
import json
import time
import logging
import signal
import io
from typing import Optional, Tuple

import requests
import psycopg2
from psycopg2.extras import Json

# -------------------------------------------------------------
# CONFIG (override via env)
# -------------------------------------------------------------
DB_HOST = os.getenv("PGHOST", "103.14.123.44")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "mydb")
DB_USER = os.getenv("PGUSER", "sql_developer")
DB_PASSWORD = os.getenv("PGPASSWORD", "Dev@123")

# PDF storage path on server (runs OUTSIDE docker, uses host path)
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/root/boostentry_pdf")

EXTRACTOR_URL = os.getenv("EXTRACTOR_URL", "http://103.14.123.44:8000/extract")

SLEEP_SECONDS = float(os.getenv("SLEEP_SECONDS", "0.5"))
EXTRACTOR_TIMEOUT = int(os.getenv("EXTRACTOR_TIMEOUT", "1600"))

RETRY_COUNT = int(os.getenv("RETRY_COUNT", "2"))
RETRY_BACKOFF_SECONDS = int(os.getenv("RETRY_BACKOFF_SECONDS", "5"))

LOG_FILE = os.getenv("WATCH_LOG", "./watch_extract_from_disk.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("watch_extract_from_disk")

# -------------------------------------------------------------
# SQL - Now reads saved_path instead of file_data
# -------------------------------------------------------------
SELECT_ONE_PENDING_SQL = """
SELECT
    doc_id,
    client_id,
    doc_format_id,
    doc_file_name,
    saved_path,
    file_data,
    COALESCE(file_mime, 'application/pdf') AS file_mime
FROM doc_processing_log
WHERE data_extraction_status = 'Not Started'
ORDER BY doc_id
LIMIT 1;
"""

UPDATE_IN_PROGRESS_SQL = """
UPDATE doc_processing_log
SET data_extraction_status = 'In Progress',
    updated_at = now()
WHERE doc_id = %s;
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

# -------------------------------------------------------------
# DB helpers
# -------------------------------------------------------------
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )

def to_bytes(db_bytea) -> bytes:
    """psycopg2 may return memoryview for BYTEA; convert robustly."""
    if db_bytea is None:
        return b""
    if isinstance(db_bytea, (bytes, bytearray)):
        return bytes(db_bytea)
    try:
        return bytes(db_bytea)
    except Exception:
        return db_bytea.tobytes() if hasattr(db_bytea, "tobytes") else b""

def read_file_from_disk(saved_path: str) -> bytes:
    """Read PDF from filesystem using saved_path."""
    if not saved_path:
        return b""
    
    file_full_path = os.path.join(PDF_STORAGE_PATH, saved_path)
    
    if not os.path.exists(file_full_path):
        logger.warning("File not found: %s", file_full_path)
        return b""
    
    try:
        with open(file_full_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_full_path, e)
        return b""

# -------------------------------------------------------------
# Extractor call
# -------------------------------------------------------------
def call_extractor_bytes(filename: str, mime: str, data: bytes,
                         client_id: int, format_id: int) -> dict:
    """POST bytes to extractor with query params."""
    url = f"{EXTRACTOR_URL}?client_id={client_id}&format_id={format_id}"
    logger.info("Calling extractor %s (filename=%s, size=%d)", url, filename, len(data))
    files = {"file": (filename, io.BytesIO(data), mime or "application/pdf")}
    resp = requests.post(url, files=files, timeout=EXTRACTOR_TIMEOUT)
    try:
        payload = resp.json()
    except Exception:
        resp.raise_for_status()
        raise
    if resp.status_code != 200:
        raise RuntimeError(f"Extractor returned {resp.status_code}: {payload}")
    return payload

# -------------------------------------------------------------
# Core processing - Reads from FILESYSTEM first
# -------------------------------------------------------------
def process_one_row() -> bool:
    """
    Process exactly one pending row.
    FIXED: Reads from filesystem (saved_path) first, falls back to DB (file_data).
    """
    
    # ============================================
    # STEP 1: Claim the row (quick operation)
    # ============================================
    doc_id = None
    client_id = None
    doc_format_id = None
    doc_file_name = None
    saved_path = None
    blob = None
    file_mime = None
    
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Fetch one pending row
        cur.execute(SELECT_ONE_PENDING_SQL)
        row = cur.fetchone()
        
        if not row:
            logger.info("No pending rows found")
            cur.close()
            conn.close()
            return False
        
        doc_id, client_id, doc_format_id, doc_file_name, saved_path, file_data, file_mime = row
        logger.info("Processing doc_id=%s file=%s saved_path=%s client_id=%s format_id=%s",
                    doc_id, doc_file_name, saved_path, client_id, doc_format_id)
        
        # Validate IDs
        if client_id is None or doc_format_id is None:
            cur.execute(UPDATE_FAILED_SQL, ("Failed: Missing IDs", doc_id))
            conn.commit()
            cur.close()
            conn.close()
            return True
        
        # Try to read from FILESYSTEM first (saved_path)
        if saved_path:
            blob = read_file_from_disk(saved_path)
            if blob:
                logger.info("doc_id=%s: Read %d bytes from filesystem (%s)", doc_id, len(blob), saved_path)
        
        # Fallback to database (file_data) if filesystem failed
        if not blob:
            blob = to_bytes(file_data)
            if blob:
                logger.info("doc_id=%s: Read %d bytes from database (fallback)", doc_id, len(blob))
        
        # No file found anywhere
        if not blob:
            cur.execute(UPDATE_FAILED_SQL, ("Failed: No File", doc_id))
            conn.commit()
            cur.close()
            conn.close()
            return True
        
        # Mark as "In Progress" - this claims the row
        cur.execute(UPDATE_IN_PROGRESS_SQL, (doc_id,))
        conn.commit()
        
        # CLOSE connection immediately - no blocking during extraction!
        cur.close()
        conn.close()
        
        logger.info("doc_id=%s marked as In Progress, connection released", doc_id)
        
    except Exception as e:
        logger.exception("DB fetch/claim error: %s", e)
        try:
            cur.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        return False

    # ============================================
    # STEP 2: Call extractor (NO DB connection held!)
    # ============================================
    filename = doc_file_name or f"document_{doc_id}.pdf"
    mime = file_mime or "application/pdf"
    
    attempt = 0
    last_err = None
    payload = None
    
    while attempt <= RETRY_COUNT:
        try:
            payload = call_extractor_bytes(filename, mime, blob, client_id, doc_format_id)
            break  # Success!
        except Exception as e:
            last_err = e
            attempt += 1
            if attempt > RETRY_COUNT:
                break
            logger.warning("Extractor attempt %d/%d failed for doc_id=%s: %s; retrying in %ss",
                           attempt, RETRY_COUNT, doc_id, e, RETRY_BACKOFF_SECONDS)
            time.sleep(RETRY_BACKOFF_SECONDS)

    # ============================================
    # STEP 3: Reopen connection to update status
    # ============================================
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        if payload:
            # Success - save extracted data
            extracted = payload.get("final_data") or payload.get("final") or payload
            cur.execute(UPDATE_SUCCESS_SQL, (Json(extracted), doc_id))
            conn.commit()
            logger.info("doc_id=%s completed successfully", doc_id)
        else:
            # Failed after all retries
            cur.execute(UPDATE_FAILED_SQL, ("Failed: Extract error", doc_id))
            conn.commit()
            logger.error("doc_id=%s failed after %d attempts: %s", doc_id, RETRY_COUNT + 1, last_err)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.exception("Failed to update final status for doc_id=%s: %s", doc_id, e)
        try:
            cur.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass
    
    return True

# -------------------------------------------------------------
# Signal handling
# -------------------------------------------------------------
_stop_requested = False

def _signal_handler(signum, frame):
    global _stop_requested
    _stop_requested = True
    logger.info("Signal %s received - will stop after current document", signum)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# -------------------------------------------------------------
# Main loop
# -------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("Starting DISK watcher (loop-until-empty)")
    logger.info("=" * 60)
    logger.info("DB: %s@%s:%s/%s", DB_USER, DB_HOST, DB_PORT, DB_NAME)
    logger.info("PDF Storage: %s", PDF_STORAGE_PATH)
    logger.info("Extractor URL: %s", EXTRACTOR_URL)
    logger.info("RETRY_COUNT=%s BACKOFF=%ss SLEEP_SECONDS=%ss",
                RETRY_COUNT, RETRY_BACKOFF_SECONDS, SLEEP_SECONDS)

    try:
        while not _stop_requested:
            processed = process_one_row()
            if not processed:
                logger.info("Queue empty - all 'Not Started' rows processed. Exiting.")
                break
            time.sleep(SLEEP_SECONDS)

    except Exception:
        logger.exception("Fatal error in main loop")
    finally:
        logger.info("Watcher stopped cleanly")

if __name__ == "__main__":
    main()
