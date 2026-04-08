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
from PIL import Image, UnidentifiedImageError
import io
import os
import math
import datetime
import requests
import tempfile
from typing import Tuple, Optional, List, Dict, Any

upload_bp = Blueprint("upload_bp", __name__)

# ---------- Configuration (via env) ----------
# Prefer an endpoint that accepts multipart file + doc_name (insert_with_file)
FASTAPI_INSERT_URL = os.getenv("PROCESSOR_INSERT_URL", "http://103.14.123.44:30011/insert_with_file")
# Legacy PHP attach endpoint (fallback)
PHP_FILE_ATTACH_URL = os.getenv("PHP_FILE_ATTACH_URL", "http://103.14.123.44:30015/api.php")

# Image extension set (lower-case)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# Safety & compression tuning
MAX_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", 178_956_970))       # user-specified pixel cap
TARGET_MAX_BYTES = int(os.getenv("TARGET_MAX_PDF_BYTES", 2 * 1024 * 1024))  # aim for <= 2MB PDF
MIN_SCALE = float(os.getenv("MIN_SCALE_FACTOR", 0.15))            # do not scale below this factor

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


def convert_image_to_pdf_bytes(raw_bytes: bytes,
                               max_pixels: int = MAX_PIXELS,
                               target_bytes: int = TARGET_MAX_BYTES,
                               min_scale: float = MIN_SCALE) -> Tuple[bytes, str]:
    """
    Convert raw image bytes -> single-page PDF bytes using LibreOffice.
    Falls back to PIL if LibreOffice fails.

    Returns: (pdf_bytes, 'application/pdf')
    Raises UnidentifiedImageError / ValueError on invalid input.
    """
    import subprocess
    import uuid
    import shutil

    if not raw_bytes:
        raise ValueError("empty image bytes")

    # Try LibreOffice first
    try:
        # Create a temp directory for conversion
        temp_dir = tempfile.mkdtemp(prefix="libreoffice_convert_")
        
        # Detect image type and save to temp file
        from PIL import Image
        bio = io.BytesIO(raw_bytes)
        img = Image.open(bio)
        img_format = img.format or "JPEG"
        ext = {"JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp", "TIFF": ".tiff", "WEBP": ".webp"}.get(img_format, ".jpg")
        
        # Save original image to temp file
        temp_image_path = os.path.join(temp_dir, f"input{ext}")
        with open(temp_image_path, "wb") as f:
            f.write(raw_bytes)
        
        # Run LibreOffice conversion
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp_dir, temp_image_path],
            capture_output=True,
            timeout=60,
            check=False
        )
        
        # Find the output PDF
        pdf_path = os.path.join(temp_dir, "input.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            if len(pdf_bytes) > 0:
                return pdf_bytes, "application/pdf"
        
        # Cleanup on failure
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise Exception("LibreOffice conversion failed")
        
    except Exception as libreoffice_err:
        # Fallback to PIL-based conversion
        current_app.logger.warning(f"LibreOffice conversion failed: {libreoffice_err}, falling back to PIL")
        
        from PIL import Image

        # Temporarily allow very large images to open
        orig_max = getattr(Image, "MAX_IMAGE_PIXELS", None)
        try:
            Image.MAX_IMAGE_PIXELS = None
        except Exception:
            orig_max = None

        try:
            bio = io.BytesIO(raw_bytes)
            bio.seek(0)
            img = Image.open(bio)
            img.load()

            w, h = img.size
            pixels = w * h
            current_scale = 1.0

            if pixels > max_pixels:
                scale = math.sqrt(max_pixels / float(pixels))
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)
                current_scale = scale

            if img.mode != "RGB":
                img = img.convert("RGB")

            def save_pdf(image_obj, resolution: float = 72.0) -> bytes:
                out = io.BytesIO()
                try:
                    image_obj.save(out, "PDF", resolution=resolution)
                except Exception:
                    tmp = io.BytesIO()
                    image_obj.save(tmp, "JPEG", quality=80, optimize=True)
                    tmp.seek(0)
                    jimg = Image.open(tmp)
                    out = io.BytesIO()
                    jimg.save(out, "PDF", resolution=resolution)
                return out.getvalue()

            pdf_bytes = save_pdf(img)

            if target_bytes and len(pdf_bytes) > target_bytes:
                attempt_img = img
                attempt_scale = current_scale
                while len(pdf_bytes) > target_bytes and attempt_scale > min_scale:
                    step_factor = max(0.5, min(0.9, math.sqrt(target_bytes / len(pdf_bytes))))
                    attempt_scale = attempt_scale * step_factor
                    new_w = max(1, int(attempt_img.width * step_factor))
                    new_h = max(1, int(attempt_img.height * step_factor))
                    try:
                        attempt_img = attempt_img.resize((new_w, new_h), Image.LANCZOS)
                        pdf_bytes = save_pdf(attempt_img)
                    except Exception:
                        break
                    if attempt_scale <= min_scale:
                        break

            return pdf_bytes, "application/pdf"

        finally:
            try:
                if orig_max is not None:
                    Image.MAX_IMAGE_PIXELS = orig_max
            except Exception:
                pass


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

            # build final_name
            ts_date = now.strftime("%Y%m%d")
            ts_time = now.strftime("%H%M%S_%f")
            base = f"{client_name}_{doc_type}_{ts_date}_{ts_time}"
            final_name = base + (".pdf" if (ext in IMAGE_EXTS or ext == "") else ext)
            res_item["final_name"] = final_name

            # If image -> convert to PDF bytes safely
            if ext in IMAGE_EXTS or (mimetype and mimetype.startswith("image/") and not final_name.lower().endswith(".pdf")):
                try:
                    pdf_bytes, pdf_mime = convert_image_to_pdf_bytes(raw_bytes, max_pixels=MAX_PIXELS, target_bytes=TARGET_MAX_BYTES)
                    file_stream_for_send = io.BytesIO(pdf_bytes)
                    send_content_type = pdf_mime
                except UnidentifiedImageError:
                    current_app.logger.exception("PIL cannot identify image; sending original bytes")
                    file_stream_for_send = io.BytesIO(raw_bytes)
                    file_stream_for_send.seek(0)
                    send_content_type = mimetype
                except Exception as conv_err:
                    current_app.logger.exception("image conversion failed")
                    res_item["error"] = f"image conversion error: {conv_err}"
                    if file_stream_for_send:
                        try:
                            file_stream_for_send.close()
                        except:
                            pass
                    results.append(res_item)
                    continue
            else:
                # not an image; send raw bytes
                file_stream_for_send = io.BytesIO(raw_bytes)
                file_stream_for_send.seek(0)
                send_content_type = mimetype or "application/octet-stream"

            # --- Preferred: try multipart POST to FastAPI insert endpoint (file + doc_name) ---
            fastapi_resp = None
            try:
                files_payload = {"file": (final_name, file_stream_for_send, send_content_type)}
                # send uploaded_on as ISO 8601 with timezone (e.g. 2025-11-21T15:33:00+05:30)
                data = {
                    "doc_name": final_name, 
                    "uploaded_on": now.isoformat(),
                    "client_id": client_id,
                    "doc_format_id": doc_format_id
                }
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
                form_payload = {
                    "doc_name": final_name, 
                    "uploaded_on": now.isoformat(),
                    "client_id": client_id,
                    "doc_format_id": doc_format_id
                }
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
