from fastapi import FastAPI, Query
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

DB_CONFIG = {
    "dbname": "mydb",
    "user": "sql_developer",
    "password": "Dev@123",
    "host": "103.14.123.44",
    "port": 5432,
}

def fetch_rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/logs")
def get_logs(status: str | None = Query(default=None, description="Filter by ERP status")):
    try:
        if status:
            rows = fetch_rows(
                "SELECT * FROM doc_processing_log WHERE UPPER(erp_entry_status)=UPPER(%s) ORDER BY doc_id DESC LIMIT 200;",
                (status,),
            )
        else:
            rows = fetch_rows(
                "SELECT * FROM doc_processing_log ORDER BY doc_id DESC LIMIT 200;"
            )
        return {"status": "success", "rows": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/logs/{doc_id}")
def get_log(doc_id: int):
    try:
        rows = fetch_rows(
            "SELECT * FROM doc_processing_log WHERE doc_id=%s;",
            (doc_id,),
        )
        if not rows:
            return {"status": "not_found", "doc_id": doc_id}
        return {"status": "success", "row": rows[0]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
