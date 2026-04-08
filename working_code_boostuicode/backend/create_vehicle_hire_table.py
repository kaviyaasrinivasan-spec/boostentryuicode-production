"""
Script to create the vehicle_hire table in the database
"""
import psycopg
from config.db_config import DB_CONFIG, _conninfo

def create_vehicle_hire_table():
    try:
        # Connect to database
        conn = psycopg.connect(_conninfo(DB_CONFIG))
        cursor = conn.cursor()
        
        # Read and execute the migration SQL
        with open('migrations/create_vehicle_hire_table.sql', 'r') as f:
            sql = f.read()
        
        cursor.execute(sql)
        conn.commit()
        
        print("✅ Successfully created vehicle_hire table!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    create_vehicle_hire_table()
