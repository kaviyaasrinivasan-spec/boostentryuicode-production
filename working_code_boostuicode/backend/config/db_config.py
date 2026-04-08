# config/db_config.py
import psycopg
from psycopg_pool import ConnectionPool
from contextlib import contextmanager

DB_CONFIG = {
    "dbname": "mydb",
    "user": "sql_developer",
    "password": "Dev@123",
    "host": "103.14.123.44",
    "port": 5432,
}

def _conninfo(d):
    return (
        f"dbname={d['dbname']} "
        f"user={d['user']} "
        f"password={d['password']} "
        f"host={d['host']} "
        f"port={d['port']}"
    )

try:
    # ✅ Create connection pool (no max_wait error)
    connection_pool = ConnectionPool(
        conninfo=_conninfo(DB_CONFIG),
        min_size=1,
        max_size=10,
        timeout=30,   # wait up to 30s for a free connection (safe and supported)
    )
    print("✅ Connected to Remote PostgreSQL (103.14.123.44)")

except Exception as e:
    connection_pool = None
    print("❌ Database Connection Error:", str(e))


def get_connection():
    """Get a database connection from the pool"""
    if connection_pool is None:
        raise RuntimeError("Connection pool is not initialized")
    return connection_pool.getconn()


def release_connection(conn):
    """Safely release the connection back to the pool"""
    try:
        if connection_pool and conn:
            connection_pool.putconn(conn)
    except Exception:
        pass


@contextmanager
def get_db_cursor(commit: bool = False):
    """
    Usage:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1")

        with get_db_cursor(commit=True) as cur:
            cur.execute("INSERT ...")
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            release_connection(conn)
