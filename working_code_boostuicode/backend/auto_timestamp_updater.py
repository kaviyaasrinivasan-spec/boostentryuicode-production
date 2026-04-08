#!/usr/bin/env python3
"""
Auto Timestamp Updater - Background Service
Checks database every 4 seconds and automatically sets timestamps when status changes
"""

import threading
import time
from datetime import datetime
from config.db_config import get_connection, release_connection

# Flag to control the background thread
_running = False
_thread = None

def check_and_update_timestamps():
    """
    Check all documents and update timestamps based on status changes
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Find documents where status changed but timestamps not set
        
        # 1. Data Extraction - Set start_time when status is "In Progress" but start_time is NULL
        cur.execute("""
            UPDATE doc_processing_log
            SET data_extraction_start_time = NOW()
            WHERE (data_extraction_status ILIKE '%In Progress%' 
                   OR data_extraction_status ILIKE '%InProgress%'
                   OR data_extraction_status ILIKE '%Processing%'
                   OR data_extraction_status = 'INPROGRESS')
              AND data_extraction_start_time IS NULL
            RETURNING doc_id, doc_file_name
        """)
        started_docs = cur.fetchall()
        for doc in started_docs:
            print(f"🟢 [AUTO] Data Extraction STARTED for doc_id={doc[0]} ({doc[1]})")
        
        # 2. Data Extraction - Set end_time when status is completed/failed but end_time is NULL
        cur.execute("""
            UPDATE doc_processing_log
            SET data_extraction_end_time = NOW()
            WHERE (data_extraction_status ILIKE 'Completed'
                   OR data_extraction_status ILIKE 'Success'
                   OR data_extraction_status ILIKE 'Failed'
                   OR data_extraction_status ILIKE 'Error')
              AND data_extraction_end_time IS NULL
              AND data_extraction_start_time IS NOT NULL
            RETURNING doc_id, doc_file_name, data_extraction_start_time
        """)
        completed_docs = cur.fetchall()
        for doc in completed_docs:
            duration = (datetime.now() - doc[2]).total_seconds() / 60 if doc[2] else 0
            print(f"✅ [AUTO] Data Extraction COMPLETED for doc_id={doc[0]} ({doc[1]}) - Duration: {duration:.1f} min")
        
        # 3. ERP Entry - Set start_time when status is "In Progress" but start_time is NULL
        cur.execute("""
            UPDATE doc_processing_log
            SET erp_entry_start_time = NOW()
            WHERE (erp_entry_status ILIKE '%In Progress%'
                   OR erp_entry_status ILIKE '%InProgress%'
                   OR erp_entry_status ILIKE '%Processing%'
                   OR erp_entry_status = 'INPROGRESS')
              AND erp_entry_start_time IS NULL
            RETURNING doc_id, doc_file_name
        """)
        erp_started_docs = cur.fetchall()
        for doc in erp_started_docs:
            print(f"🟢 [AUTO] Consignment Entry STARTED for doc_id={doc[0]} ({doc[1]})")
        
        # 4. ERP Entry - Set end_time when status is completed/failed/duplicate but end_time is NULL
        cur.execute("""
            UPDATE doc_processing_log
            SET erp_entry_end_time = NOW()
            WHERE (erp_entry_status ILIKE 'Completed'
                   OR erp_entry_status ILIKE 'Completed AHR'
                   OR erp_entry_status ILIKE 'Success'
                   OR erp_entry_status ILIKE 'Failed'
                   OR erp_entry_status ILIKE 'Error'
                   OR erp_entry_status ILIKE 'Duplicate')
              AND erp_entry_end_time IS NULL
              AND erp_entry_start_time IS NOT NULL
            RETURNING doc_id, doc_file_name, erp_entry_start_time
        """)
        erp_completed_docs = cur.fetchall()
        for doc in erp_completed_docs:
            duration = (datetime.now() - doc[2]).total_seconds() / 60 if doc[2] else 0
            print(f"✅ [AUTO] Consignment Entry COMPLETED for doc_id={doc[0]} ({doc[1]}) - Duration: {duration:.1f} min")
        
        conn.commit()
        
        # Log summary if any updates were made
        total_updates = len(started_docs) + len(completed_docs) + len(erp_started_docs) + len(erp_completed_docs)
        if total_updates > 0:
            print(f"📊 [AUTO] Updated {total_updates} timestamp(s) at {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ [AUTO] Error updating timestamps: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_connection(conn)


def _background_worker():
    """
    Background thread that runs every 4 seconds
    """
    global _running
    print("🚀 Auto Timestamp Updater started (checking every 4 seconds)")
    
    # Run immediately on startup to catch any existing status changes
    try:
        print("⚡ Running initial timestamp check...")
        check_and_update_timestamps()
    except Exception as e:
        print(f"❌ [AUTO] Initial check error: {e}")
    
    while _running:
        try:
            check_and_update_timestamps()
        except Exception as e:
            print(f"❌ [AUTO] Background worker error: {e}")
        
        # Wait 4 seconds before next check
        time.sleep(4)
    
    print("🛑 Auto Timestamp Updater stopped")


def start_auto_updater():
    """
    Start the background timestamp updater service
    """
    global _running, _thread
    
    if _running:
        print("⚠️ Auto Timestamp Updater already running")
        return
    
    _running = True
    _thread = threading.Thread(target=_background_worker, daemon=True)
    _thread.start()
    print("✅ Auto Timestamp Updater service started")


def stop_auto_updater():
    """
    Stop the background timestamp updater service
    """
    global _running
    
    if not _running:
        print("⚠️ Auto Timestamp Updater not running")
        return
    
    _running = False
    if _thread:
        _thread.join(timeout=5)
    print("✅ Auto Timestamp Updater service stopped")


# Manual check function for testing
def manual_check():
    """
    Manually trigger a timestamp check (for testing)
    """
    print("🔍 Manual timestamp check triggered...")
    check_and_update_timestamps()
    print("✅ Manual check completed")


if __name__ == "__main__":
    # Test the updater
    print("Testing Auto Timestamp Updater...")
    print("Running one check cycle...")
    manual_check()
    
    print("\nTo run continuously, call start_auto_updater() from app.py")
