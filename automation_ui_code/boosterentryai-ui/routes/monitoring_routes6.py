# routes/monitoring_routes.py
from flask import Blueprint, request, jsonify, send_file
from config.db_config import get_connection, release_connection
from datetime import datetime
import json
import traceback
import io
import time
import os
import re as _re
from flask import Response, stream_with_context

# PDF storage path
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/root/boostentry_pdf")

monitoring_bp = Blueprint("monitoring_bp", __name__)

# ----------------------------
# helpers
# ----------------------------
def _normalize(s):
    """Clean string for matching: lowercase and alphanumeric only."""
    return _re.sub(r'[^a-z0-9]', '', str(s or "").lower())

def _parse_json(txt):
    if not txt:
        return {}
    if isinstance(txt, dict):
        return txt
    try:
        return json.loads(txt)
    except Exception:
        return {}

def _unwrap_final_data(payload: dict):
    if isinstance(payload, dict) and "final_data" in payload and isinstance(payload["final_data"], dict):
        return payload["final_data"]
    return payload if isinstance(payload, dict) else {}

def _calculate_time_consumed(start_time, end_time):
    if not start_time or not end_time:
        return None
    try:
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        delta = end_time - start_time
        return round(delta.total_seconds() / 60, 1)
    except Exception:
        return None

def _format_time_only(timestamp):
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return timestamp.strftime("%I:%M %p")
    except Exception:
        return None

# ==========================================================
# ? API 1: Fetch Monitoring Table Data
# ==========================================================
@monitoring_bp.route("/api/monitoring", methods=["GET"])
def get_monitoring_data():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        client_id = request.args.get("client_id")
        status = request.args.get("status")
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")

        base_query = """
            SELECT 
                d.doc_id, c.client_name, f.doc_type, d.doc_file_name,
                d.uploaded_on, d.updated_at, d.overall_status,
                d.data_extraction_status, d.erp_entry_status, d.vehicle_hire_status,
                d.extracted_json, d.data_extraction_start_time, d.data_extraction_end_time,
                d.erp_entry_start_time, d.erp_entry_end_time
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            WHERE 1=1
        """
        params = []
        if client_id and client_id != "undefined":
            base_query += " AND d.client_id = %s"
            params.append(client_id)
        if status:
            base_query += " AND d.overall_status ILIKE %s"
            params.append(f"%{status}%")
        if from_date and to_date:
            base_query += " AND DATE(d.uploaded_on) BETWEEN %s AND %s"
            params.extend([from_date, to_date])
        base_query += " ORDER BY d.uploaded_on DESC;"

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()

        data = []
        for r in rows:
            raw = _unwrap_final_data(_parse_json(r[10]))
            invoice_no = str(raw.get("Invoice No") or raw.get("InvoiceNo") or "")
            data.append({
                "id": r[0], "client_name": r[1], "doc_type": r[2], "file_name": r[3],
                "uploaded_on": str(r[4]), "updated_at": str(r[5]) if r[5] else "",
                "overall_status": r[6], "data_extraction_status": r[7], "erp_entry_status": r[8],
                "vehicle_hire_status": r[9], "invoice_no": invoice_no,
                "data_extraction_time_consumed": _calculate_time_consumed(r[11], r[12]),
                "erp_entry_time_consumed": _calculate_time_consumed(r[13], r[14]),
            })
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: release_connection(conn)

# ==========================================================
# ? API 2: Stream PDF File
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>/file", methods=["GET"])
def stream_doc_file(doc_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT saved_path, file_data, COALESCE(file_mime, 'application/pdf'), doc_file_name FROM doc_processing_log WHERE doc_id = %s", (doc_id,))
        row = cur.fetchone()
        release_connection(conn)
        if not row: return jsonify({"status": "error", "message": "Not found"}), 404
        
        saved_path, file_data, file_mime, file_name = row
        if saved_path:
            full_path = os.path.join(PDF_STORAGE_PATH, saved_path)
            if os.path.exists(full_path):
                return send_file(full_path, mimetype=file_mime)
        if file_data:
            return send_file(io.BytesIO(bytes(file_data)), mimetype=file_mime)
        return jsonify({"status": "error", "message": "No file content"}), 404
    except Exception as e:
        if conn: release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================================
# ? API 3: Single Doc Details (WITH ROBUST STATE DETECTION)
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>", methods=["GET"])
def get_monitoring_doc_details(doc_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.doc_id, c.client_name, f.doc_type, d.doc_file_name, d.extracted_json, d.corrected_json, d.uploaded_on, d.data_extraction_status, d.erp_entry_status
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            WHERE d.doc_id = %s
        """, (doc_id,))
        row = cur.fetchone()
        if not row:
            release_connection(conn)
            return jsonify({"status": "error", "message": "Not found"}), 404

        (r_doc_id, client_name, doc_type, file_name, ext_j, cor_j, upl_on, de_status, erp_status) = row

        # Parse and Merge (Preferring corrected if available)
        raw_ext = _unwrap_final_data(_parse_json(ext_j))
        raw_cor = _unwrap_final_data(_parse_json(cor_j))
        display_raw = {**raw_ext, **raw_cor}

        ordered_fields = [
            "Branch", "Date", "ConsignmentNo", "Source", "Destination",
            "Vehicle", "EWayBillNo", "Consignor", "Consignee", "GSTType",
            "Delivery Address", "Invoice No", "ContentName", "ActualWeight",
            "E-WayBill ValidUpto", "Invoice Date", "E-Way Bill Date",
            "Get Rate", "GoodsType", "Delivery Address State"
        ]

        ordered_data = []
        seen_keys = set()

        if isinstance(display_raw, dict):
            display_raw.pop("ValidationStatus", None)
            
            # --- Robust Key Matching Loop ---
            for key in ordered_fields:
                norm_target = _normalize(key)
                
                # Special broad matching for State
                if "state" in norm_target:
                    alts = ["deliveryaddressstate", "deliveryaddressstatte", "deliverystate", "state", "statte", "staste", "deliveraddressstate"]
                else:
                    alts = [norm_target]

                matching_key = None
                for k in display_raw.keys():
                    if _normalize(k) in alts:
                        matching_key = k
                        break
                
                if matching_key:
                    ordered_data.append({"field": key, "value": display_raw[matching_key] or ""})
                    seen_keys.add(matching_key)
                elif key == "Delivery Address State":
                    # Absolute fallback: if no state matched, look for ANY key containing 'state'
                    found_backup = None
                    for k, v in display_raw.items():
                        if "state" in k.lower():
                            found_backup = v
                            break
                    ordered_data.append({"field": key, "value": found_backup or ""})

            # Add any other dynamic fields
            for k, v in display_raw.items():
                if k not in seen_keys and _normalize(k):
                    ordered_data.append({"field": k, "value": v or ""})
                    seen_keys.add(k)

        # Build stable file URL
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)
        file_url = f"{scheme}://{host}/api/monitoring/{r_doc_id}/file"

        release_connection(conn)
        return jsonify({
            "status": "success",
            "data": {
                "doc": {
                    "id": r_doc_id, "client_name": client_name, "doc_type": doc_type,
                    "uploaded_on": str(upl_on), "file_url": file_url,
                    "data_extraction_status": de_status, "erp_entry_status": erp_status
                },
                "extracted_data": ordered_data
            }
        }), 200
    except Exception as e:
        traceback.print_exc()
        if conn: release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================================
# ? API 4: Update Duplicate & Reset Status
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>/update-duplicate", methods=["POST"])
def update_duplicate_consignment(doc_id):
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        new_no = data.get("consignment_no", "").strip()
        if not new_no: return jsonify({"status": "error", "message": "Required"}), 400
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT extracted_json, corrected_json FROM doc_processing_log WHERE doc_id = %s", (doc_id,))
        row = cur.fetchone()
        if not row:
            release_connection(conn)
            return jsonify({"status": "error", "message": "Not found"}), 404
        
        base = _parse_json(row[1]) if row[1] else _parse_json(row[0])
        final_data = base.get("final_data", base).copy()
        final_data["ConsignmentNo"] = new_no
        
        cur.execute(
            """
            UPDATE doc_processing_log 
            SET corrected_json = %s, erp_entry_status = 'Fixed', updated_at = NOW() 
            WHERE doc_id = %s
            """,
            (json.dumps({"final_data": final_data}), doc_id)
        )
        conn.commit()
        release_connection(conn)
        return jsonify({"status": "success", "message": "Updated"}), 200
    except Exception as e:
        if conn: conn.rollback(); release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500
