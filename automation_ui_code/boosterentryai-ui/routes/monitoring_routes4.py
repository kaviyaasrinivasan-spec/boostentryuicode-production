# routes/monitoring_routes.py
from flask import Blueprint, request, jsonify, send_file
from config.db_config import get_connection, release_connection
from datetime import datetime
import json
import traceback
import io
import time
import os
from flask import Response, stream_with_context

# PDF storage path (same path inside and outside Docker via -v /root/boostentry_pdf:/root/boostentry_pdf)
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/root/boostentry_pdf")

monitoring_bp = Blueprint("monitoring_bp", __name__)

# ----------------------------
# helpers
# ----------------------------
def _parse_json(txt):
    """Safely parse a JSON string to a Python object. Returns {} on failure or if txt is falsy."""
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        return {}

def _unwrap_final_data(payload: dict):
    """If payload is {"final_data": {...}}, return that inner dict. Else return payload or {}."""
    if isinstance(payload, dict) and "final_data" in payload and isinstance(payload["final_data"], dict):
        return payload["final_data"]
    return payload if isinstance(payload, dict) else {}
def _calculate_time_consumed(start_time, end_time):
    """Calculate time consumed in minutes between two timestamps"""
    if not start_time or not end_time:
        return None
    try:
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        delta = end_time - start_time
        minutes = delta.total_seconds() / 60
        return round(minutes, 1)
    except Exception:
        return None

def _format_time_only(timestamp):
    """Format timestamp to show only time (HH:MM AM/PM)"""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return timestamp.strftime("%I:%M %p")
    except Exception:
        return None

def _normalize_key(s):
    """Normalize key for fuzzy comparison: lowercase and remove non-alphanumeric characters."""
    if s is None:
        return ""
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()

def _find_field_value(data_dict, target_key):
    """Find a value in data_dict by normalizing keys."""
    if not isinstance(data_dict, dict):
        return None
    norm_target = _normalize_key(target_key)
    for k, v in data_dict.items():
        if _normalize_key(k) == norm_target:
            return v
    return None
# ==========================================================
# ✅ API 1: Fetch Monitoring Table Data
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
                d.doc_id,
                c.client_name,
                f.doc_type,
                d.doc_file_name,
                d.uploaded_on,
                d.updated_at,
                d.overall_status,
                d.data_extraction_status,
                d.erp_entry_status,
                d.vehicle_hire_status,
                d.extracted_json,
                d.data_extraction_start_time,
                d.data_extraction_end_time,
                d.erp_entry_start_time,
                d.erp_entry_end_time
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            WHERE 1=1
        """

        filters = []
        params = []

        if client_id:
            filters.append("d.client_id = %s")
            params.append(client_id)

        if status:
            filters.append("d.overall_status ILIKE %s")
            params.append(f"%{status}%")

        if from_date and to_date:
            filters.append("DATE(d.uploaded_on) BETWEEN %s AND %s")
            params.extend([from_date, to_date])

        if filters:
            base_query += " AND " + " AND ".join(filters)

        base_query += " ORDER BY d.uploaded_on DESC;"

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()

        data = []
        for r in rows:
            (
                doc_id,
                client_name,
                doc_type,
                file_name,
                up_on,
                upd_on,
                overall_status,
                de_status,
                erp_status,
                vh_status,
                extracted_json,
                de_start,
                de_end,
                erp_start,
                erp_end,
            ) = r

            uploaded_on = (
                up_on.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(up_on, datetime)
                else str(up_on)
            )

            updated_at = (
                upd_on.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(upd_on, datetime)
                else str(upd_on) if upd_on else ""
            )

            raw = _unwrap_final_data(_parse_json(extracted_json))
            invoice_no = (
                raw.get("Invoice No")
                or raw.get("InvoiceNo")
                or raw.get("Invoice_Number")
                or raw.get("Invoice Number")
                or raw.get("Invoice")
                or ""
            )
            if invoice_no is None:
                invoice_no = ""
            invoice_no = str(invoice_no)

            data.append(
                {
                    "id": doc_id,
                    "client_name": client_name,
                    "doc_type": doc_type,
                    "file_name": file_name,
                    "uploaded_on": uploaded_on,
                    "updated_at": updated_at,
                    "overall_status": overall_status,
                    "data_extraction_status": de_status,
                    "erp_entry_status": erp_status,
                    "vehicle_hire_status": vh_status,
                    "invoice_no": invoice_no,
                    "extracted_json": extracted_json,
                    "data_extraction_start_time": _format_time_only(de_start),
                    "data_extraction_end_time": _format_time_only(de_end),
                    "data_extraction_time_consumed": _calculate_time_consumed(de_start, de_end),
                    "erp_entry_start_time": _format_time_only(erp_start),
                    "erp_entry_end_time": _format_time_only(erp_end),
                    "erp_entry_time_consumed": _calculate_time_consumed(erp_start, erp_end),
                }
            )

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print("❌ Monitoring Data Error:", str(e))
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
    
    finally:
        # ALWAYS release connection, even if exception occurred
        if conn:
            release_connection(conn)


# ==========================================================
# ✅ API 2: Stream PDF from Filesystem (with DB fallback)
#    URL: GET /api/monitoring/<doc_id>/file
#    Reads: saved_path (filesystem) first, then file_data (DB) as fallback
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>/file", methods=["GET"])
def stream_doc_file(doc_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT saved_path, file_data, COALESCE(file_mime, 'application/pdf'), doc_file_name
            FROM doc_processing_log
            WHERE doc_id = %s
            """,
            (doc_id,),
        )
        row = cur.fetchone()
        release_connection(conn)
        conn = None

        if not row:
            return jsonify({"status": "error", "message": "Document not found"}), 404

        saved_path, file_data, file_mime, file_name = row
        
        # Try to serve from filesystem first
        if saved_path:
            file_full_path = os.path.join(PDF_STORAGE_PATH, saved_path)
            if os.path.exists(file_full_path):
                return send_file(
                    file_full_path,
                    mimetype=file_mime or "application/pdf",
                    as_attachment=False,
                    download_name=file_name or f"document_{doc_id}.pdf",
                    max_age=0,
                )
            else:
                print(f"⚠️ File not found at {file_full_path}, falling back to DB")
        
        # Fallback to DB (for legacy records)
        if not file_data:
            return jsonify({"status": "error", "message": "No file stored for this document"}), 404

        # Stream bytes from DB
        bio = io.BytesIO(bytes(file_data))
        return send_file(
            bio,
            mimetype=file_mime or "application/pdf",
            as_attachment=False,
            download_name=file_name or f"document_{doc_id}.pdf",
            max_age=0,
        )
    except Exception as e:
        print("❌ Stream File Error:", str(e))
        traceback.print_exc()
        if conn:
            release_connection(conn)
        return jsonify({"status": "error", "message": "Failed to stream file"}), 500


# ==========================================================
# ✅ API 3: Fetch Single Document Details
#    - Sets file_url to our new /api/monitoring/<id>/file (DB stream)
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>", methods=["GET"])
def get_monitoring_doc_details(doc_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT 
                d.doc_id,
                c.client_name,
                f.doc_type,
                d.doc_file_name,
                d.extracted_json,
                d.corrected_json,
                d.uploaded_on,
                d.data_extraction_status,
                d.erp_entry_status
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            WHERE d.doc_id = %s
        """
        cur.execute(query, (doc_id,))
        row = cur.fetchone()

        if not row:
            release_connection(conn)
            return jsonify({"status": "error", "message": "Document not found"}), 404

        (
            r_doc_id,
            client_name,
            doc_type,
            file_name,
            extracted_json,
            corrected_json,
            uploaded_on,
            data_extraction_status,
            erp_entry_status,
        ) = row

        # Prefer corrected_json for the detail view; fallback to extracted_json if corrected is empty
        display_corrected = _unwrap_final_data(_parse_json(corrected_json))
        display_extracted = _unwrap_final_data(_parse_json(extracted_json))
        
        display_raw = display_corrected if display_corrected else display_extracted

        ordered_fields = [
            "Branch",
            "Date",
            "ConsignmentNo",
            "Source",
            "Destination",
            "Vehicle",
            "EWayBillNo",
            "Consignor",
            "Consignee",
            "GSTType",
            "Delivery Address",
            "Invoice No",
            "ContentName",
            "ActualWeight",
            "E-WayBill ValidUpto",
            "Invoice Date",
            "E-Way Bill Date",
            "Get Rate",
            "GoodsType",
            "Delivery Address State",
        ]

        if isinstance(display_raw, dict):
            display_raw.pop("ValidationStatus", None)
            if "E-Way Bill NO" in display_raw and "EWayBillNo" in display_raw:
                display_raw.pop("E-Way Bill NO", None)

        ordered_data = []
        seen_keys = set()
        
        if isinstance(display_raw, dict):
            # 1. First add fields from ordered_fields (in order)
            for key in ordered_fields:
                import re as _re
                norm_target = _re.sub(r'[^a-z0-9]', '', key.lower())
                
                matching_raw_key = None
                for k in display_raw.keys():
                    if _re.sub(r'[^a-z0-9]', '', str(k).lower()) == norm_target:
                        matching_raw_key = k
                        break
                
                if matching_raw_key is not None:
                    ordered_data.append({"field": key, "value": display_raw[matching_raw_key] if display_raw[matching_raw_key] is not None else ""})
                    seen_keys.add(matching_raw_key)
                elif key == "Delivery Address State":
                    # Force include this field even if missing in raw data
                    ordered_data.append({"field": key, "value": ""})

            # 2. Add any remaining fields that weren't in the preferred list (Dynamic)
            for k, v in display_raw.items():
                if k not in seen_keys:
                    ordered_data.append({"field": k, "value": v if v is not None else ""})
                    seen_keys.add(k)

        # 🔁 NEW: stream PDF from DB, not filesystem
        # Build absolute URL to our streaming endpoint so it works in iframe
        # Use X-Forwarded-Proto header to detect if request came via HTTPS (Nginx proxy)
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)
        base_url = f"{scheme}://{host}"
        file_url = f"{base_url}/api/monitoring/{r_doc_id}/file"

        release_connection(conn)
        return jsonify(
            {
                "status": "success",
                "data": {
                    "doc": {
                        "id": r_doc_id,
                        "client_name": client_name,
                        "doc_type": doc_type,
                        "uploaded_on": str(uploaded_on),
                        "file_url": file_url,  # ⬅ iframe will load from DB
                        "data_extraction_status": data_extraction_status,
                        "erp_entry_status": erp_entry_status,
                    },
                    "extracted_data": ordered_data,
                },
            }
        ), 200

    except Exception as e:
        print("❌ Monitoring Doc Fetch Error:", str(e))
        traceback.print_exc()
        if conn:
            release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================================
# ✅ API 4: Update Duplicate Consignment Number & Reset ERP Status
#    URL: POST /api/monitoring/<doc_id>/update-duplicate
#    Body: { "consignment_no": "NEW_CONSIGNMENT_NUMBER" }
#    Purpose: Update consignment number in corrected_json (like fix_review_routes)
#             and reset erp_entry_status from 'Duplicate' to 'Not Started'
# ==========================================================
@monitoring_bp.route("/api/monitoring/<int:doc_id>/update-duplicate", methods=["POST"])
def update_duplicate_consignment(doc_id):
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        new_consignment_no = data.get("consignment_no", "").strip()
        
        if not new_consignment_no:
            return jsonify({"status": "error", "message": "Consignment number is required"}), 400
        
        conn = get_connection()
        cur = conn.cursor()
        
        # First, fetch the current extracted_json, corrected_json and erp_entry_status
        cur.execute(
            """
            SELECT extracted_json, corrected_json, erp_entry_status
            FROM doc_processing_log
            WHERE doc_id = %s
            """,
            (doc_id,),
        )
        row = cur.fetchone()
        
        if not row:
            release_connection(conn)
            return jsonify({"status": "error", "message": "Document not found"}), 404
        
        extracted_json, corrected_json, erp_status = row
        
        # Check if the status is actually "Duplicate"
        if not erp_status or "duplicate" not in erp_status.lower():
            release_connection(conn)
            return jsonify({"status": "error", "message": "Document is not in Duplicate status"}), 400
        
        # Use corrected_json if exists, otherwise start from extracted_json (like fix_review_routes)
        base_json = _parse_json(corrected_json) if corrected_json else _parse_json(extracted_json) if extracted_json else {}
        
        # Get the final_data to update
        if "final_data" in base_json and isinstance(base_json["final_data"], dict):
            final_data = base_json["final_data"].copy()
        else:
            final_data = base_json.copy() if isinstance(base_json, dict) else {}
        
        # Update the consignment number in final_data
        final_data["ConsignmentNo"] = new_consignment_no
        # Also update other common key variants if they exist
        if "Consignment No" in final_data:
            final_data["Consignment No"] = new_consignment_no
        if "consignment_no" in final_data:
            final_data["consignment_no"] = new_consignment_no
        
        # Build the corrected_json with final_data structure (like fix_review_routes)
        corrected_json_data = json.dumps({"final_data": final_data}, ensure_ascii=False)
        
        # Update the database: set corrected_json, reset erp_entry_status to 'Not Started',
        # and clear erp_entry_start_time and erp_entry_end_time
        cur.execute(
            """
            UPDATE doc_processing_log
            SET corrected_json = %s,
                erp_entry_status = 'Fixed',
                erp_entry_start_time = NULL,
                erp_entry_end_time = NULL,
                updated_at = NOW()
            WHERE doc_id = %s
            """,
            (corrected_json_data, doc_id),
        )
        
        conn.commit()
        release_connection(conn)
        conn = None
        
        print(f"✅ Updated duplicate doc_id={doc_id}: new consignment_no='{new_consignment_no}', saved to corrected_json, erp_status set to 'Fixed'")
        
        return jsonify({
            "status": "success",
            "message": "Consignment number updated and ERP status set to 'Fixed'",
            "doc_id": doc_id,
            "new_consignment_no": new_consignment_no
        }), 200
        
    except Exception as e:
        print("❌ Update Duplicate Error:", str(e))
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
            release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500


# NOTE: SSE streaming endpoint removed to reduce DB load.
# Monitoring page now uses manual refresh only.
