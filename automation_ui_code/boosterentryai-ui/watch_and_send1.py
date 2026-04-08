#!/usr/bin/env python3
"""
api_doc_log_dynamic.py

Dynamic FastAPI that inserts into doc_processing_log and can store file bytes
directly into the DB (file_data/file_mime/file_size), skipping any external api.php.
"""

from __future__ import annotations
import os
import sys
import logging
import argparse
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, List, Any
from contextlib import asynccontextmanager
import io
import tempfile

from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from pydantic import BaseModel, Field, validator

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import sql
from psycopg2 import Binary as Psycopg2Binary

# image libs
from PIL import Image, UnidentifiedImageError

# PDF generation (reportlab for robust PDF)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doc_processing_log_dynamic")

# -------------------------
# Config
# -------------------------
DB_CONFIG = {
    "host": os.getenv("PGHOST", "103.14.123.44"),
    "port": int(os.getenv("PGPORT", "5432")),
    "database": os.getenv("PGDATABASE", "mydb"),
    "user": os.getenv("PGUSER", "sql_developer"),
    "password": os.getenv("PGPASSWORD", "Dev@123"),
}

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5213"))

MIN_POOL = int(os.getenv("DB_POOL_MIN", 1))
MAX_POOL = int(os.getenv("DB_POOL_MAX", 10))



# Convert client images to PDF before storing (default ON)
CONVERT_IMAGES_TO_PDF = os.getenv("CONVERT_IMAGES_TO_PDF", "1") != "0"

# PDF storage path (same path inside and outside Docker via -v /root/boostentry_pdf:/root/boostentry_pdf)
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/root/boostentry_pdf")
# Ensure storage directory exists
try:
    os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
except Exception as e:
    logger.warning(f"Could not create PDF storage directory {PDF_STORAGE_PATH}: {e}")

# -------------------------
# Globals
# -------------------------
pool: Optional[ThreadedConnectionPool] = None

DOC_LOG_IDENT: Optional[Tuple[str, str]] = None
CLIENTS_IDENT: Optional[Tuple[str, str]] = None
DOCFORMATS_IDENT: Optional[Tuple[str, str]] = None

# mapping: logical_field -> actual_column_name
COLUMN_MAP: Dict[str, str] = {}

# common image extensions
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# -------------------------
# Pydantic model
# -------------------------
class DocLogIn(BaseModel):
    doc_name: str = Field(..., description="Filename e.g. UltraTechCement_Invoice_2025-10-14_06-13-31.pdf")
    uploaded_on: Optional[str] = Field(None, description="Optional timestamp. Example: 2025-10-15 10:45:22")

    @validator("doc_name")
    def doc_name_non_empty(cls, v: str):
        if not v or not v.strip():
            raise ValueError("doc_name is required")
        return v.strip()

# -------------------------
# DB pool helpers
# -------------------------
def init_pool():
    global pool
    if pool is None:
        pool = ThreadedConnectionPool(
            MIN_POOL, MAX_POOL,
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        logger.info("DB pool created")

def close_pool():
    global pool
    if pool:
        try:
            pool.closeall()
            logger.info("DB pool closed")
        except Exception:
            logger.exception("Error closing DB pool")

def get_conn():
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    return pool.getconn()

def put_conn(conn):
    if pool:
        pool.putconn(conn)

# -------------------------
# Schema discovery helpers
# -------------------------
def find_table_schema(cur, table_name: str) -> Optional[str]:
    cur.execute("""
        SELECT table_schema
        FROM information_schema.tables
        WHERE table_name = %s
        ORDER BY CASE WHEN table_schema = 'public' THEN 0 ELSE 1 END, table_schema
        LIMIT 1
    """, (table_name,))
    r = cur.fetchone()
    return r[0] if r else None

def get_table_columns(cur, schema: str, table: str) -> List[str]:
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
    """, (schema, table))
    return [r[0] for r in cur.fetchall()]

# Candidate mappings (extended to include file-related columns)
CANDIDATE_NAMES = {
    "doc_id": ["doc_id", "document_id", "docid", "id"],
    "doc_name": ["doc_name", "doc_file_name", "document_name", "file_name", "filename", "name"],
    "uploaded_on": ["uploaded_on", "uploaded_at", "upload_time", "uploaded_time", "uploaded"],
    "uploaded_by": ["uploaded_by", "uploaded_user", "uploaded_by_user", "created_by", "uploaded", "user_uploaded_by"],
    "client_id": ["client_id", "customer_id", "clientid"],
    "doc_format_id": ["doc_format_id", "docformat_id", "doc_formatid", "format_id", "doc_format"],
    "overall_status": ["overall_status", "status", "overallstatus"],
    "erp_entry_status": ["erp_entry_status", "erp_status", "erp_entrystatus", "erp_entry", "erp_state"],
    "data_extraction_status": ["data_extraction_status", "extraction_status", "data_status"],
    "manual_review_status": ["manual_review_status", "review_status", "manual_review"],
    "created_at": ["created_at", "created", "created_on", "createdat"],
    "updated_at": ["updated_at", "updated", "updated_on", "updatedat"],
    # file-related
    "file_data": ["file_data", "file_bytea", "file_bytes", "file", "file_content", "doc_file_data"],
    "file_mime": ["file_mime", "file_type", "mime_type", "file_mimetype"],
    "file_size": ["file_size", "filesize", "file_length"],
    "saved_path": ["saved_path", "file_path", "saved_filepath", "file_location"],
}

def choose_column(available: List[str], candidates: List[str]) -> Optional[str]:
    avail_lower = {c.lower(): c for c in available}
    for cand in candidates:
        if cand.lower() in avail_lower:
            return avail_lower[cand.lower()]
    for cand in candidates:
        lowcand = cand.lower()
        for col_lower, col_actual in avail_lower.items():
            if lowcand in col_lower or col_lower in lowcand:
                return col_actual
    return None

def build_column_map(cur, schema: str, table: str) -> Dict[str, str]:
    cols = get_table_columns(cur, schema, table)
    logger.info("doc_processing_log columns discovered: %s", cols)
    m: Dict[str, str] = {}
    for logical, cands in CANDIDATE_NAMES.items():
        found = choose_column(cols, cands)
        if found:
            m[logical] = found
    # final fallback for doc_name
    if "doc_name" not in m:
        for alt in ["doc_file_name", "file_name", "document_name"]:
            if alt in cols:
                m["doc_name"] = alt
                logger.warning("Fallback mapping applied: logical 'doc_name' -> '%s'", alt)
                break
    return m

def resolve_table_and_map_columns():
    global DOC_LOG_IDENT, CLIENTS_IDENT, DOCFORMATS_IDENT, COLUMN_MAP
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user, current_setting('search_path');")
        db, user, sp = cur.fetchone()
        logger.info("Connected to DB=%s user=%s search_path=%s", db, user, sp)

        log_schema = find_table_schema(cur, "doc_processing_log")
        if not log_schema:
            raise RuntimeError("doc_processing_log not found in any schema. Create the table or change name.")
        DOC_LOG_IDENT = (log_schema, "doc_processing_log")
        logger.info("Resolved doc_processing_log at %s.%s", log_schema, "doc_processing_log")

        clients_schema = find_table_schema(cur, "clients")
        if clients_schema:
            CLIENTS_IDENT = (clients_schema, "clients")
            logger.info("Resolved clients at %s.clients", clients_schema)
        else:
            CLIENTS_IDENT = None
            logger.warning("clients table not found; client lookup will be skipped")

        docformats_schema = find_table_schema(cur, "doc_formats")
        if docformats_schema:
            DOCFORMATS_IDENT = (docformats_schema, "doc_formats")
            logger.info("Resolved doc_formats at %s.doc_formats", docformats_schema)
        else:
            DOCFORMATS_IDENT = None
            logger.warning("doc_formats table not found; doc_format lookup will be skipped")

        COLUMN_MAP = build_column_map(cur, log_schema, "doc_processing_log")
        logger.info("Column map resolved: %s", COLUMN_MAP)

        required = ["doc_id", "doc_name"]
        missing_required = [r for r in required if r not in COLUMN_MAP]
        if missing_required:
            raise RuntimeError(f"Required logical columns missing in doc_processing_log table: {missing_required}. "
                               f"Detected columns: {get_table_columns(cur, log_schema, 'doc_processing_log')}. "
                               f"Please ALTER TABLE to add these column(s).")
        cur.close()
    except Exception:
        if conn:
            put_conn(conn)
        logger.exception("Failed to resolve table/columns at startup")
        raise
    finally:
        if conn:
            put_conn(conn)

# -------------------------
# Helpers: parsing & lookups
# -------------------------
def parse_doc_name(doc_name: str) -> Tuple[Optional[str], Optional[str]]:
    if not doc_name:
        return None, None
    base = doc_name.rsplit("/", 1)[-1]
    base = base.rsplit(".", 1)[0]
    parts = re.split(r'[_\-\s]+', base)
    client_tok = parts[0].strip() if parts and parts[0].strip() else None
    doc_type_tok = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return client_tok, doc_type_tok

def ilike_pattern(tok: str) -> str:
    tok = re.sub(r"[^A-Za-z0-9]+", " ", tok).strip()
    return f"%{tok}%"

def find_client_and_docformat(cur, client_tok: Optional[str], doc_type_tok: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    client_id = None
    doc_format_id = None

    if CLIENTS_IDENT and client_tok:
        c_schema, c_table = CLIENTS_IDENT
        try:
            cur.execute(sql.SQL("SELECT client_id FROM {}.{} WHERE client_name ILIKE %s LIMIT 1").format(
                sql.Identifier(c_schema), sql.Identifier(c_table)
            ), (ilike_pattern(client_tok),))
            r = cur.fetchone()
            if r:
                client_id = int(r[0])
        except Exception:
            logger.exception("Failed clients lookup for token %s", client_tok)

    if DOCFORMATS_IDENT and doc_type_tok:
        d_schema, d_table = DOCFORMATS_IDENT
        try:
            if client_id:
                cur.execute(sql.SQL("SELECT doc_format_id FROM {}.{} WHERE client_id = %s AND doc_type ILIKE %s LIMIT 1").format(
                    sql.Identifier(d_schema), sql.Identifier(d_table)
                ), (client_id, ilike_pattern(doc_type_tok)))
                r = cur.fetchone()
                if r:
                    doc_format_id = int(r[0])
            if doc_format_id is None:
                cur.execute(sql.SQL("SELECT doc_format_id FROM {}.{} WHERE doc_type ILIKE %s LIMIT 1").format(
                    sql.Identifier(d_schema), sql.Identifier(d_table)
                ), (ilike_pattern(doc_type_tok),))
                r2 = cur.fetchone()
                if r2:
                    doc_format_id = int(r2[0])
        except Exception:
            logger.exception("Failed doc_formats lookup for token %s", doc_type_tok)

    return client_id, doc_format_id

def parse_uploaded_on(s: Optional[str]) -> datetime:
    if s and s.strip():
        s = s.strip()
        fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
        for fmt in fmts:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(s)
        except Exception:
            raise ValueError(f"uploaded_on not parsable: {s}")
    return datetime.now()

# -------------------------
# compute next doc id
# -------------------------
def compute_next_doc_id(cur, schema: str, table: str, doc_id_col: str) -> int:
    # Simple max+1 approach (no blocking lock)
    q = sql.SQL("SELECT COALESCE(MAX({}), 0) FROM {}.{};").format(sql.Identifier(doc_id_col), sql.Identifier(schema), sql.Identifier(table))
    cur.execute(q)
    r = cur.fetchone()
    max_id = int(r[0]) if r and r[0] is not None else 0
    return max_id + 1

# -------------------------
# Core insert (extended to accept file bytes)
# -------------------------
def insert_into_doc_log(payload: DocLogIn,
                        file_bytes: Optional[bytes] = None,
                        file_mime: Optional[str] = None,
                        file_size: Optional[int] = None,
                        saved_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Insert record into doc_processing_log. If file_bytes provided and corresponding
    columns exist in the schema, store bytes into the mapped 'file_data' column using psycopg2.Binary.
    """
    if DOC_LOG_IDENT is None:
        raise HTTPException(status_code=500, detail="Server not ready (doc_processing_log missing)")

    schema, table = DOC_LOG_IDENT
    conn = None
    try:
        conn = get_conn()
        conn.autocommit = False
        cur = conn.cursor()

        # allocate doc_id
        doc_id_col = COLUMN_MAP["doc_id"]
        new_doc_id = compute_next_doc_id(cur, schema, table, doc_id_col)
        logger.info("Allocated new doc_id=%s -> %s.%s", new_doc_id, schema, table)

        # parse filename and find client/docformat
        client_tok, doc_type_tok = parse_doc_name(payload.doc_name)
        client_id, doc_format_id = find_client_and_docformat(cur, client_tok, doc_type_tok)
        logger.info("Parsed %s -> client_tok=%s doc_type_tok=%s -> client_id=%s doc_format_id=%s",
                    payload.doc_name, client_tok, doc_type_tok, client_id, doc_format_id)

        uploaded_on_dt = parse_uploaded_on(payload.uploaded_on)
        now = datetime.now()

        insert_cols: List[sql.Identifier] = []
        insert_vals: List = []

        def add_if_mapped(logical_name: str, value, transform=None):
            col = COLUMN_MAP.get(logical_name)
            if col is not None:
                insert_cols.append(sql.Identifier(col))
                insert_vals.append(transform(value) if transform else value)

        add_if_mapped("doc_id", new_doc_id)
        add_if_mapped("client_id", client_id)
        add_if_mapped("doc_format_id", doc_format_id)
        add_if_mapped("doc_name", payload.doc_name)
        add_if_mapped("uploaded_on", uploaded_on_dt)
        add_if_mapped("overall_status", "INPROGRESS")
        add_if_mapped("erp_entry_status", "Not Started")
        add_if_mapped("uploaded_by", "SYSTEM")
        add_if_mapped("data_extraction_status", "Not Started")
        add_if_mapped("manual_review_status", "Not Review")
        add_if_mapped("created_at", now)
        add_if_mapped("updated_at", now)

        # file fields: only include if values provided and column exists
        if file_bytes is not None:
            # file_data column may exist
            if "file_data" in COLUMN_MAP:
                # wrap as psycopg2.Binary for bytea
                add_if_mapped("file_data", file_bytes, transform=lambda b: Psycopg2Binary(b))
            else:
                logger.warning("Schema does not have mapped 'file_data' column; will skip storing bytes in DB")

            # file_mime / file_size only when file_bytes provided
            add_if_mapped("file_mime", file_mime)
            add_if_mapped("file_size", file_size)
        
        # saved_path should ALWAYS be stored (even when file_bytes is None - file saved to disk)
        if saved_path:
            add_if_mapped("saved_path", saved_path)
            add_if_mapped("file_mime", file_mime)  # Also store mime for disk files
            add_if_mapped("file_size", file_size)  # Also store size for disk files

        if not insert_cols:
            raise RuntimeError("No mapped columns available for insert into doc_processing_log")

        # build SQL and execute
        col_list_sql = sql.SQL(", ").join(insert_cols)
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(insert_vals))
        insert_q = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}").format(
            sql.Identifier(schema), sql.Identifier(table), col_list_sql, placeholders, sql.Identifier(COLUMN_MAP.get("doc_id", "doc_id"))
        )

        logger.debug("Insert SQL: %s", insert_q.as_string(cur))
        cur.execute(insert_q, tuple(insert_vals))
        ret = cur.fetchone()
        inserted_return = ret[0] if ret else None

        conn.commit()
        cur.close()

        response = {
            "status": "success",
            "db_doc_id": new_doc_id,
            "returned_value": inserted_return,
            "client_id": client_id,
            "doc_format_id": doc_format_id,
        }

        # note if file was provided but no file_data column present
        if file_bytes is not None and "file_data" not in COLUMN_MAP:
            response["warning"] = "file provided but target table has no mapped file_data column; file bytes not stored"

        return response

    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.exception("Insert failed")
        raise HTTPException(status_code=500, detail=f"Insertion failed: {e}")
    finally:
        if conn:
            put_conn(conn)

# -------------------------
# FastAPI app + lifespan
# -------------------------
app = FastAPI(title="Doc Processing Log (dynamic + file store)", version="1.2.0")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan startup: init pool and resolve schema/columns")
    init_pool()
    try:
        resolve_table_and_map_columns()
    except Exception:
        logger.exception("Startup resolution failed")
        close_pool()
        raise
    yield
    logger.info("Lifespan shutdown: closing DB pool")
    close_pool()

app.router.lifespan_context = lifespan

# -------------------------
# Minimal endpoints (health/next_doc_id/insert)
# -------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "doc_processing_log": bool(DOC_LOG_IDENT),
        "clients_table": bool(CLIENTS_IDENT),
        "doc_formats_table": bool(DOCFORMATS_IDENT),
        "column_map": COLUMN_MAP,
        "convert_images_to_pdf": CONVERT_IMAGES_TO_PDF,
    }

@app.get("/next_doc_id")
def next_doc_id():
    if DOC_LOG_IDENT is None:
        raise HTTPException(status_code=500, detail="Server not ready")
    schema, table = DOC_LOG_IDENT
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        doc_id_col = COLUMN_MAP["doc_id"]
        cur.execute(sql.SQL("SELECT COALESCE(MAX({}),0) FROM {}.{}").format(sql.Identifier(doc_id_col), sql.Identifier(schema), sql.Identifier(table)))
        r = cur.fetchone()
        max_db = int(r[0]) if r and r[0] is not None else 0
        cur.close()
        return {"next_db_doc_id": max_db + 1}
    except Exception:
        if conn:
            put_conn(conn)
        logger.exception("Failed next_doc_id")
        raise HTTPException(status_code=500, detail="Failed to compute next_doc_id")
    finally:
        if conn:
            put_conn(conn)

@app.post("/insert")
def insert_form(doc_name: str = Form(...), uploaded_on: Optional[str] = Form(None)):
    payload = DocLogIn(doc_name=doc_name, uploaded_on=uploaded_on)
    return insert_into_doc_log(payload)

# -------------------------
# NEW: 
#  — store file bytes directly in DB
# -------------------------
@app.post("/insert_with_file")
async def insert_with_file(doc_name: str = Form(...),
                           uploaded_on: Optional[str] = Form(None),
                           file: Optional[UploadFile] = File(None)):
    """
    Accepts doc_name, optional uploaded_on, and optional file.
    Saves the file AS-IS without any conversion, compression, or processing.
    """
    payload = DocLogIn(doc_name=doc_name, uploaded_on=uploaded_on)

    file_bytes = None
    content_type = None
    fsize = None
    saved_path = None

    if file is not None:
        try:
            # Read file bytes AS-IS (no conversion, no compression)
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            content_type = (file.content_type or "").lower()
            fsize = len(file_bytes)

            # Get original extension from filename
            orig_name = (getattr(file, "filename", None) or "").strip()
            _, ext = os.path.splitext(orig_name)
            ext = (ext or "").lower()

            logger.info(f"📁 Received file: {orig_name} ({fsize} bytes, type: {content_type})")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed reading uploaded file")
            raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {e}")

    # Save PDF to filesystem instead of storing in DB
    saved_file_path = None
    if file_bytes is not None and fsize > 0:
        try:
            import random
            # Generate unique filename from doc_name with random suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds
            random_suffix = random.randint(100000, 999999)  # 6-digit random number
            # Extract client name from doc_name (e.g., "UltraTechCement_Invoice_..." -> "UltraTechCement")
            doc_name_parts = payload.doc_name.split("_") if payload.doc_name else ["Unknown"]
            safe_client_name = re.sub(r'[^\w\-]', '_', doc_name_parts[0] or "Unknown")[:50]
            # Keep original file extension based on content type
            if content_type == "application/pdf":
                file_ext = ".pdf"
            elif content_type in ("image/jpeg", "image/jpg"):
                file_ext = ".jpg"
            elif content_type == "image/png":
                file_ext = ".png"
            elif content_type == "image/heic":
                file_ext = ".heic"
            elif content_type == "image/webp":
                file_ext = ".webp"
            elif content_type == "image/bmp":
                file_ext = ".bmp"
            elif content_type == "image/tiff":
                file_ext = ".tiff"
            else:
                # Try to get extension from original filename
                file_ext = ext if ext else ".bin"
            filename = f"{safe_client_name}_{timestamp}_{random_suffix}{file_ext}"
            file_full_path = os.path.join(PDF_STORAGE_PATH, filename)
            
            # Write file to disk
            with open(file_full_path, "wb") as f:
                f.write(file_bytes)
            
            # Store relative path for portability (filename only)
            saved_file_path = filename
            logger.info(f"Saved PDF to filesystem: {file_full_path} ({fsize} bytes)")
            
            # Clear file_bytes - don't store in DB anymore
            file_bytes = None
            
        except Exception as e:
            logger.warning(f"Failed to save PDF to filesystem: {e}. Will store in DB as fallback.")
            # Keep file_bytes as fallback to store in DB
            saved_file_path = None

    # Now perform insert; file bytes will be stored if file_data column exists
    result = insert_into_doc_log(payload,
                                file_bytes=file_bytes,  # Will be None if saved to disk
                                file_mime=content_type,
                                file_size=fsize,
                                saved_path=saved_file_path)  # Path to file on disk
    return result

# -------------------------
# Entrypoint
# -------------------------
def _run_programmatic(host: str, port: int):
    try:
        import uvicorn
    except Exception:
        logger.error("uvicorn not installed")
        raise
    uvicorn.run(app, host=host, port=port, reload=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doc processing log dynamic (file store)")
    parser.add_argument("--host", default=os.getenv("API_HOST", API_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", API_PORT)))
    args = parser.parse_args()
    try:
        _run_programmatic(host=args.host, port=args.port)
    except Exception:
        logger.exception("Failed to start")
        sys.exit(1)
