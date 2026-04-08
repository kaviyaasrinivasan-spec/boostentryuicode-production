
import os
import psycopg
from config.db_config import get_connection

def check_tables():
    print(f"🔌 Connecting to DB...")
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check connection details
        cur.execute("SELECT version(), inet_server_addr(), current_database(), current_user;")
        row = cur.fetchone()
        version, ip, db, user = row
        print(f"✅ Connected to: {ip} | DB: {db} | User: {user}")
        print(f"   Version: {version}")

        # List tables in ALL schemas
        cur.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog') 
            ORDER BY table_schema, table_name;
        """)
        rows = cur.fetchall()
        
        print("\n📊 Tables found:")
        if not rows:
            print("   (No tables found in any user schema)")
        else:
            for schema, table in rows:
                print(f"   - {schema}.{table}")

        # Specific checks
        required = ['doc_processing_log', 'users', 'clients']
        found_tables = [r[1] for r in rows]
        missing = [t for t in required if t not in found_tables]
        
        if missing:
            print(f"\n❌ CRITICAL: The following required tables are MISSING: {missing}")
        else:
            print("\n✅ All core tables (doc_processing_log, users, clients) are present.")

    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")

if __name__ == "__main__":
    check_tables()
