import psycopg
from config.db_config import DB_CONFIG, _conninfo

def check_submission():
    try:
        conn = psycopg.connect(_conninfo(DB_CONFIG))
        cur = conn.cursor()
        
        # Check latest vehicle hire entry
        cur.execute("SELECT * FROM vehicle_hire ORDER BY created_at DESC LIMIT 1")
        latest_vh = cur.fetchone()
        print("\nLatest Vehicle Hire Entry:")
        print(latest_vh)
        
        if latest_vh:
            doc_id = latest_vh[1] # Assuming doc_id is 2nd column
            
            # Check status in doc_processing_log
            cur.execute("SELECT doc_id, vehicle_hire_status FROM doc_processing_log WHERE doc_id = %s", (doc_id,))
            doc_status = cur.fetchone()
            print("\nDocument Status:")
            print(doc_status)
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_submission()
