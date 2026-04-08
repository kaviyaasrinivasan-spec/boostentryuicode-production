#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_bp.py

Flask blueprint providing:
- GET /api/clients
- GET /api/doc_formats/<client_id>
- POST /api/upload         -> full upload flow (client_id + doc_format_id required)
- POST /api/upload_direct  -> shortcut (uses client_id=1 and doc_format_id=1)

Features:
- Accepts camera-captured images and gallery picks (works on mobile & desktop)
- Converts any image to a single-page PDF (in-memory), safely handling very large images
- Attempts multipart POST to FASTAPI_INSERT_URL (preferred) so FastAPI can insert bytes into DB
- Fallback: call FASTAPI_INSERT_URL (form) then PHP_FILE_ATTACH_URL (multipart attach)
- Environment-driven config; defaults keep backward compatibility
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import io
import os
import datetime
import requests
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image

upload_bp = Blueprint("upload_bp", __name__)

# ---------- Configuration (via env) ----------
# Prefer an endpoint that accepts multipart file + doc_name (insert_with_file)
FASTAPI_INSERT_URL = os.getenv("PROCESSOR_INSERT_URL", "http://103.14.123.44:30011/insert_with_file")
# Legacy PHP attach endpoint (fallback)
PHP_FILE_ATTACH_URL = os.getenv("PHP_FILE_ATTACH_URL", "http://103.14.123.44:30015/api.php")

# Image extension set (lower-case)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".heic"}

# Defaults for upload_direct
UPLOAD_DIRECT_CLIENT_ID = int(os.getenv("UPLOAD_DIRECT_CLIENT_ID", 1))
UPLOAD_DIRECT_DOC_FORMAT_ID = int(os.getenv("UPLOAD_DIRECT_DOC_FORMAT_ID", 1))


# ---------- Helpers ----------
def _norm(s: str) -> str:
    return (s or "").strip().replace(" ", "_")


def _json_or_text(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def compress_image_to_limit(image_bytes: bytes, max_size_mb: float = 2.0, min_quality: int = 50) -> Tuple[bytes, str]:
    """
    Compress an image to be under max_size_mb while maintaining quality.
    
    Strategy:
    1. Try progressive quality reduction: 95 ? 85 ? 75 ? 65 ? 50
    2. If still too large, reduce dimensions by 10% iteratively
    3. Convert PNG to JPEG for better compression
    
    Args:
        image_bytes: Original image bytes
        max_size_mb: Maximum size in MB (default 2.0)
        min_quality: Minimum acceptable quality (default 50)
    
    Returns:
        Tuple of (compressed_bytes, format) where format is 'JPEG' or 'PNG'
    """
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    
    # Check if compression is needed
    if len(image_bytes) <= max_size_bytes:
        # No compression needed, return original
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return image_bytes, img.format or 'JPEG'
        except:
            return image_bytes, 'JPEG'
    
    try:
        # Open image
        img = Image.open(io.BytesIO(image_bytes))
        original_format = img.format
        
        # Convert RGBA to RGB for JPEG compatibility
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # For PNG, try converting to JPEG first (usually much smaller)
        output_format = 'JPEG' if original_format in ('PNG', 'BMP', 'TIFF') else (original_format or 'JPEG')
        
        # Strategy 1: Progressive quality reduction
        quality_levels = [95, 85, 75, 65, min_quality]
        for quality in quality_levels:
            output = io.BytesIO()
            img.save(output, format=output_format, quality=quality, optimize=True)
            compressed_bytes = output.getvalue()
            
            if len(compressed_bytes) <= max_size_bytes:
                current_app.logger.info(
                    f"Compressed image from {len(image_bytes)/(1024*1024):.2f}MB to "
                    f"{len(compressed_bytes)/(1024*1024):.2f}MB at quality {quality}"
                )
                return compressed_bytes, output_format
        
        # Strategy 2: Reduce dimensions if quality reduction wasn't enough
        current_app.logger.info("Quality reduction insufficient, reducing dimensions...")
        scale_factor = 0.9  # Reduce by 10% each iteration
        max_iterations = 10
        
        for iteration in range(max_iterations):
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Try with minimum quality
            output = io.BytesIO()
            resized_img.save(output, format=output_format, quality=min_quality, optimize=True)
            compressed_bytes = output.getvalue()
            
            if len(compressed_bytes) <= max_size_bytes:
                current_app.logger.info(
                    f"Compressed image from {len(image_bytes)/(1024*1024):.2f}MB to "
                    f"{len(compressed_bytes)/(1024*1024):.2f}MB by resizing to {new_width}x{new_height}"
                )
                return compressed_bytes, output_format
            
            # Update for next iteration
            img = resized_img
        
        # If still too large, return the last attempt
        current_app.logger.warning(
            f"Could not compress image below {max_size_mb}MB. Final size: {len(compressed_bytes)/(1024*1024):.2f}MB"
        )
        return compressed_bytes, output_format
        
    except Exception as e:
        current_app.logger.error(f"Image compression failed: {e}")
        # Return original if compression fails
        return image_bytes, 'JPEG'


# ---------- DB-backed endpoints (kept unchanged) ----------
@upload_bp.route("/api/clients", methods=["GET"])
def get_clients():
    from config.db_config import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT client_id, client_name FROM clients ORDER BY client_name;")
        rows = cur.fetchall()
        release_connection(conn)
        return jsonify({"status": "success", "data": [{"id": r[0], "name": r[1]} for r in rows]}), 200
    except Exception:
        current_app.logger.exception("Error fetching clients")
        return jsonify({"status": "error", "message": "Failed to load clients"}), 500


@upload_bp.route("/api/doc_formats/<int:client_id>", methods=["GET"])
def get_doc_formats(client_id):
    from config.db_config import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT doc_format_id, doc_type, doc_format_name, file_type
            FROM doc_formats
            WHERE client_id = %s
            ORDER BY doc_format_name;
            """,
            (client_id,),
        )
        rows = cur.fetchall()
        release_connection(conn)
        return (
            jsonify(
                {
                    "status": "success",
                    "data": [{"id": r[0], "doc_type": r[1], "name": r[2], "file_type": r[3]} for r in rows],
                }
            ),
            200,
        )
    except Exception:
        current_app.logger.exception("Error fetching document formats")
        return jsonify({"status": "error", "message": "Failed to load formats"}), 500


# ---------- Core upload handler (reusable) ----------
def _process_and_upload_files(client_id: int, doc_format_id: int, uploaded_by: str, files_list: List[Any]) -> Dict[str, Any]:
    """
    Core worker that processes a list of werkzeug FileStorage objects.
    Returns: {"status":"success","data":[ per-file-result ] }
    """
    results = []
    # Use Asia/Kolkata (IST) for uploaded_on timestamps to avoid timezone mismatch
    try:
        # Python 3.9+ zoneinfo
        from zoneinfo import ZoneInfo

        now = datetime.datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    except Exception:
        try:
            # fallback to pytz if available
            import pytz

            now = datetime.datetime.now(tz=pytz.timezone("Asia/Kolkata"))
        except Exception:
            # final fallback: server local time
            now = datetime.datetime.now()

    # Resolve nicenames (client_name & doc_type) for final filename generation
    from config.db_config import get_connection, release_connection
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT client_name FROM clients WHERE client_id = %s;", (client_id,))
        row = cur.fetchone()
        if not row:
            return {"status": "error", "message": "Invalid client_id"}
        # Use first word only (e.g. "JSW Cement" -> "JSW") so server parser works
        raw_name = row[0] or ""
        first_word = raw_name.strip().split(" ")[0]
        client_name = _norm(first_word)

        cur.execute("SELECT doc_type FROM doc_formats WHERE doc_format_id = %s;", (doc_format_id,))
        row2 = cur.fetchone()
        if not row2:
            return {"status": "error", "message": "Invalid doc_format_id"}
        doc_type = _norm(row2[0])
    finally:
        release_connection(conn)

    for f in files_list:
        res_item: Dict[str, Optional[Any]] = {"source": None, "final_name": None, "insert_api": None, "attach_api": None, "error": None}
        tmp_path = None
        file_stream_for_send = None
        try:
            orig_name = secure_filename(f.filename or "upload")
            res_item["source"] = orig_name
            _, ext = os.path.splitext(orig_name)
            ext = (ext or "").lower()

            # robust read (camera captures sometimes present as streams)
            try:
                f.stream.seek(0)
            except Exception:
                pass
            raw_bytes = f.read()
            if not raw_bytes:
                res_item["error"] = "empty file uploaded"
                results.append(res_item)
                continue

            mimetype = getattr(f, "mimetype", None) or "application/octet-stream"
            if not ext:
                # derive extension from mimetype
                if mimetype.startswith("image/"):
                    sub = mimetype.split("/", 1)[1]
                    ext = ".jpg" if sub == "jpeg" else "." + sub.split("+")[0]
                elif mimetype == "application/pdf":
                    ext = ".pdf"
                else:
                    ext = ""

            # Check for image compression (if > 2MB)
            # We treat it as image if mimetype says so OR extension says so
            is_image = (mimetype and mimetype.startswith("image/")) or (ext and ext in IMAGE_EXTS)
            
            if is_image and len(raw_bytes) > (2 * 1024 * 1024):
                current_app.logger.info(f"Image {orig_name} is {len(raw_bytes)/(1024*1024):.2f}MB, attempting compression...")
                compressed_bytes, fmt = compress_image_to_limit(raw_bytes, max_size_mb=2.0)
                
                # If we actually compressed it
                if len(compressed_bytes) < len(raw_bytes):
                    raw_bytes = compressed_bytes
                    # Update extension/mimetype if format changed (e.g. PNG -> JPEG)
                    if fmt == 'JPEG' and ext != '.jpg':
                         ext = '.jpg'
                         mimetype = 'image/jpeg'
                    elif fmt == 'PNG' and ext != '.png':
                         ext = '.png'
                         mimetype = 'image/png'

            # build final_name - keep original extension for all file types (no conversion)
            ts_date = now.strftime("%Y%m%d")
            ts_time = now.strftime("%H%M%S_%f")
            base = f"{client_name}_{doc_type}_{ts_date}_{ts_time}"
            # Keep original extension for all files (jpg stays jpg, png stays png, pdf stays pdf)
            final_name = base + ext
            res_item["final_name"] = final_name

            # Send raw bytes directly - NO image-to-PDF conversion
            # All files (images, PDFs, etc.) are uploaded in their original format
            file_stream_for_send = io.BytesIO(raw_bytes)
            file_stream_for_send.seek(0)
            send_content_type = mimetype or "application/octet-stream"

            # --- Preferred: try multipart POST to FastAPI insert endpoint (file + doc_name) ---
            fastapi_resp = None
            try:
                files_payload = {"file": (final_name, file_stream_for_send, send_content_type)}
                # send uploaded_on as ISO 8601 with timezone (e.g. 2025-11-21T15:33:00+05:30)
                data = {"doc_name": final_name, "uploaded_on": now.isoformat()}
                fastapi_resp = requests.post(FASTAPI_INSERT_URL, files=files_payload, data=data, timeout=60)
            except Exception as multipart_exc:
                current_app.logger.warning("FASTAPI multipart attempt failed: %s", multipart_exc)
                fastapi_resp = None
            finally:
                # rewind so fallback can reuse
                try:
                    if file_stream_for_send:
                        file_stream_for_send.seek(0)
                except:
                    pass

            if fastapi_resp is not None and fastapi_resp.status_code == 200:
                res_item["insert_api"] = _json_or_text(fastapi_resp)
                try:
                    if file_stream_for_send:
                        file_stream_for_send.close()
                except:
                    pass
                results.append(res_item)
                continue

            # --- Fallback: form-insert then php attach ---
            try:
                # send ISO 8601 timestamp to make timezone explicit
                form_payload = {"doc_name": final_name, "uploaded_on": now.isoformat()}
                ins = requests.post(FASTAPI_INSERT_URL, data=form_payload, timeout=30)
            except Exception as e:
                res_item["error"] = f"insert network error: {e}"
                try:
                    if file_stream_for_send:
                        file_stream_for_send.close()
                except:
                    pass
                results.append(res_item)
                continue

            if ins.status_code != 200:
                res_item["error"] = f"insert failed: {ins.status_code} {ins.text}"
                try:
                    if file_stream_for_send:
                        file_stream_for_send.close()
                except:
                    pass
                results.append(res_item)
                continue

            res_item["insert_api"] = _json_or_text(ins)

            # Optional: check php endpoint for existing final_name (legacy)
            php_rows = None
            try:
                chk = requests.get(PHP_FILE_ATTACH_URL, params={"limit": 200}, timeout=20)
                if chk.status_code == 200:
                    php_rows = _json_or_text(chk)
                    if isinstance(php_rows, dict) and "data" in php_rows:
                        php_rows = php_rows["data"]
            except Exception:
                php_rows = None

            already_attached = False
            if php_rows and isinstance(php_rows, list):
                for rr in php_rows:
                    name = rr.get("doc_file_name") or rr.get("file_name") or rr.get("doc_name")
                    if name == final_name:
                        if rr.get("has_file") or rr.get("file_data") or (rr.get("file_size") and int(rr.get("file_size")) > 0):
                            res_item["attach_api"] = {"status": "already_attached", "row": rr}
                            already_attached = True
                            break

            if already_attached:
                try:
                    if file_stream_for_send:
                        file_stream_for_send.close()
                except:
                    pass
                results.append(res_item)
                continue

            # Prepare fileobj for php attach
            try:
                file_stream_for_send.seek(0)
                fileobj = file_stream_for_send
                send_ct = send_content_type
            except Exception:
                # fallback build new BytesIO
                fileobj = io.BytesIO(raw_bytes)
                fileobj.seek(0)
                send_ct = mimetype or "application/octet-stream"

            # POST to PHP attach endpoint
            try:
                files_payload = {"file": (final_name, fileobj, send_ct)}
                data = {"file_name": final_name}
                ph = requests.post(PHP_FILE_ATTACH_URL, files=files_payload, data=data, timeout=60)
            finally:
                try:
                    if fileobj and hasattr(fileobj, "close"):
                        fileobj.close()
                except:
                    pass
                try:
                    if file_stream_for_send and file_stream_for_send is not fileobj:
                        file_stream_for_send.close()
                except:
                    pass
                if tmp_path:
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except:
                        pass

            if ph is None:
                res_item["error"] = "php attach endpoint not reachable"
                results.append(res_item)
                continue

            if ph.status_code != 200:
                res_item["error"] = f"php attach failed: {ph.status_code} {ph.text}"
                results.append(res_item)
                continue

            res_item["attach_api"] = _json_or_text(ph)
            results.append(res_item)

        except Exception as e:
            current_app.logger.exception("Unexpected error while processing file")
            try:
                if file_stream_for_send:
                    file_stream_for_send.close()
            except:
                pass
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except:
                pass
            res_item["error"] = str(e)
            results.append(res_item)

    return {"status": "success", "data": results}


# ---------- Upload endpoints ----------
@upload_bp.route("/api/upload", methods=["POST"])
def upload_files():
    """
    POST multipart/form-data:
      - client_id (form)
      - doc_format_id (form)
      - uploaded_by (form, optional)
      - files (one or multiple file fields; name 'files')
    """
    try:
        client_id = request.form.get("client_id")
        doc_format_id = request.form.get("doc_format_id")
        uploaded_by = request.form.get("uploaded_by", "SYSTEM")

        if not client_id or not doc_format_id:
            return jsonify({"status": "error", "message": "client_id and doc_format_id required"}), 400

        # Accept both single 'files' or repeated/multiple file inputs
        files = request.files.getlist("files")
        # also permit 'file' as singular key for convenience
        if not files:
            one = request.files.get("file")
            if one:
                files = [one]

        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        # process files
        try:
            client_i = int(client_id)
            doc_fmt_i = int(doc_format_id)
        except Exception:
            return jsonify({"status": "error", "message": "client_id/doc_format_id must be integers"}), 400

        result = _process_and_upload_files(client_i, doc_fmt_i, uploaded_by, files)
        return jsonify(result), 200 if result.get("status") == "success" else 500

    except Exception as e:
        current_app.logger.exception("Upload Error")
        return jsonify({"status": "error", "message": "Server error", "detail": str(e)}), 500


@upload_bp.route("/api/upload_direct", methods=["POST"])
def upload_direct():
    """
    Shortcut endpoint for quick tests / integrations.
    Uses configured UPLOAD_DIRECT_CLIENT_ID and UPLOAD_DIRECT_DOC_FORMAT_ID.
    Accepts 'file' (single) or 'files' (multiple).
    """
    try:
        uploaded_by = request.form.get("uploaded_by", "SYSTEM")

        files = request.files.getlist("files")
        if not files:
            one = request.files.get("file")
            if one:
                files = [one]

        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        result = _process_and_upload_files(UPLOAD_DIRECT_CLIENT_ID, UPLOAD_DIRECT_DOC_FORMAT_ID, uploaded_by, files)
        return jsonify(result), 200 if result.get("status") == "success" else 500

    except Exception as e:
        current_app.logger.exception("upload_direct Error")
        return jsonify({"status": "error", "message": "Server error", "detail": str(e)}), 500
