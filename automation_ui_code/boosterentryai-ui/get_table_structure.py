#!/usr/bin/env python3
"""
Quick script to retrieve and display the doc_processing_log table structure
"""

import psycopg2

# DB Config (directly defined since db_config.py uses psycopg v3)
DB_CONFIG = {
    "dbname": "mydb",
    "user": "sql_developer",
    "password": "Dev@123",
    "host": "103.14.123.44",
    "port": 5432,
}

def get_table_structure():
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        
        cur = conn.cursor()
        
        # Get the table schema
        print("=" * 80)
        print("TABLE STRUCTURE FOR: doc_processing_log")
        print("=" * 80)
        
        # Query to get all column details
        query = """
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = 'doc_processing_log'
            ORDER BY ordinal_position;
        """
        
        cur.execute(query)
        columns = cur.fetchall()
        
        if not columns:
            print("⚠️  Table 'doc_processing_log' not found!")
            return
        
        print(f"\nTotal Columns: {len(columns)}\n")
        print(f"{'Column Name':<30} {'Data Type':<20} {'Max Length':<12} {'Nullable':<10} {'Default'}")
        print("-" * 120)
        
        for col in columns:
            col_name = col[0]
            data_type = col[1]
            max_length = str(col[2]) if col[2] else "N/A"
            is_nullable = col[3]
            default_val = col[4] if col[4] else ""
            
            print(f"{col_name:<30} {data_type:<20} {max_length:<12} {is_nullable:<10} {default_val}")
        
        print("\n" + "=" * 80)
        
        # Get row count
        cur.execute("SELECT COUNT(*) FROM doc_processing_log;")
        row_count = cur.fetchone()[0]
        print(f"Total Rows in Table: {row_count}")
        print("=" * 80)
        
        # Get a sample row (if any exist)
        if row_count > 0:
            print("\nSample Row (latest entry):")
            print("-" * 80)
            cur.execute("SELECT * FROM doc_processing_log ORDER BY created_at DESC LIMIT 1;")
            sample_row = cur.fetchone()
            
            # Get column names
            col_names = [desc[0] for desc in cur.description]
            
            for idx, col_name in enumerate(col_names):
                value = sample_row[idx] if idx < len(sample_row) else "N/A"
                # Truncate long values
                if isinstance(value, (str, bytes)) and len(str(value)) > 100:
                    value = str(value)[:100] + "..."
                print(f"  {col_name}: {value}")
            print("=" * 80)
        
        cur.close()
        conn.close()
        
        print("\n✅ Table structure retrieved successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_table_structure()
