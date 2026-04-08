# create_telegram_sessions_table.py
# Run this script to create the telegram_pending_sessions table

import psycopg2
from config.db_config import get_connection, release_connection

def create_table():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Create telegram_pending_sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telegram_pending_sessions (
                id SERIAL PRIMARY KEY,
                doc_id INTEGER NOT NULL UNIQUE,
                phone_no VARCHAR(20) NOT NULL,
                chat_id VARCHAR(50),
                manifest_no VARCHAR(50),
                advance_amount DECIMAL(15, 2),
                qty DECIMAL(15, 3),
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_sessions_chat_id 
            ON telegram_pending_sessions(chat_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_sessions_status 
            ON telegram_pending_sessions(status)
        """)
        
        conn.commit()
        print("✅ telegram_pending_sessions table created successfully!")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error creating table: {e}")
        
    finally:
        if conn:
            release_connection(conn)


if __name__ == "__main__":
    create_table()
