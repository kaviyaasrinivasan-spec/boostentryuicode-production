#!/usr/bin/env python3
"""
migrate_files_to_disk.py

Migrates existing PDFs from database (file_data) to filesystem (/root/boostentry_pdf/)
and updates saved_path column in doc_processing_log.

Run on server: python3 migrate_files_to_disk.py
"""

import os
import psycopg2
from datetime import datetime

# Configuration
DB_CONFIG = {
    "host": "103.14.123.44",
    "port": 5432,
    "database": "mydb",
    "user": "sql_developer",
    "password": "Dev@123",
}

PDF_STORAGE_PATH = "/root/boostentry_pdf"

def migrate():
    print(f"📁 Storage path: {PDF_STORAGE_PATH}")
    os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all records with file_data but no saved_path
    cur.execute("""
        SELECT doc_id, file_data, doc_file_name, file_mime
        FROM doc_processing_log
        WHERE file_data IS NOT NULL 
          AND (saved_path IS NULL OR saved_path = '')
    """)
    
    rows = cur.fetchall()
    print(f"📄 Found {len(rows)} documents to migrate")
    
    migrated = 0
    for doc_id, file_data, doc_file_name, file_mime in rows:
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".pdf" if file_mime and "pdf" in file_mime.lower() else ".bin"
            safe_name = (doc_file_name or f"doc_{doc_id}").replace("/", "_").replace("\\", "_")
            filename = f"{doc_id}_{safe_name}"
            if not filename.endswith(ext):
                filename = f"{filename}{ext}"
            
            file_path = os.path.join(PDF_STORAGE_PATH, filename)
            
            # Convert memoryview to bytes if needed
            if isinstance(file_data, memoryview):
                file_data = file_data.tobytes()
            elif not isinstance(file_data, (bytes, bytearray)):
                file_data = bytes(file_data)
            
            # Write to disk
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # Update saved_path in database
            cur.execute(
                "UPDATE doc_processing_log SET saved_path = %s WHERE doc_id = %s",
                (filename, doc_id)
            )
            
            print(f"  ✅ doc_id={doc_id} -> {filename} ({len(file_data)} bytes)")
            migrated += 1
            
        except Exception as e:
            print(f"  ❌ doc_id={doc_id} failed: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n🎉 Migration complete! {migrated}/{len(rows)} documents migrated.")
    print(f"📂 Files saved to: {PDF_STORAGE_PATH}")

if __name__ == "__main__":
    migrate()
