import sys
import os

sys.path.append(os.getcwd())

def check_data():
    output_file = "db_output.txt"
    try:
        from config.db_config import get_connection, release_connection
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("Starting DB check...\n")
            
            conn = get_connection()
            f.write("Connected to DB.\n")
            
            cur = conn.cursor()

            f.write("\n--- CLIENTS TABLE ---\n")
            cur.execute("SELECT client_id, client_name FROM clients ORDER BY client_id;")
            clients = cur.fetchall()
            for c in clients:
                f.write(f"ID: {c[0]}, Name: {c[1]}\n")

            f.write("\n--- DOC FORMATS TABLE ---\n")
            cur.execute("SELECT doc_format_id, client_id, doc_format_name, doc_type FROM doc_formats ORDER BY client_id, doc_format_id;")
            formats = cur.fetchall()
            for fmt in formats:
                f.write(f"ID: {fmt[0]}, ClientID: {fmt[1]}, Name: {fmt[2]}, Type: {fmt[3]}\n")
            
            release_connection(conn)
            f.write("\nDone.\n")
            
        print(f"Written to {output_file}")

    except Exception as e:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"\nERROR: {e}\n")
        print(f"Error: {e}")

if __name__ == "__main__":
    check_data()
