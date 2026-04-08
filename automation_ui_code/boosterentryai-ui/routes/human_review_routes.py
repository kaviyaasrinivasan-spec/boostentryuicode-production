# routes/human_review_routes.py
from flask import Blueprint, request, jsonify
from config.db_config import get_connection, release_connection
from datetime import datetime
import traceback
import json

human_review_bp = Blueprint("human_review_bp", __name__)

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

def _unwrap_final_data(payload):
    """
    If payload is {"final_data": {...}}, return that inner dict.
    Else return payload or {}.
    """
    if isinstance(payload, dict) and "final_data" in payload and isinstance(payload["final_data"], dict):
        return payload["final_data"]
    return payload if isinstance(payload, dict) else {}

def _find_invoice_no(payload):
    """
    Look for invoice number in payload dict using common key names, case-insensitive.
    Returns string ('' if not found).
    """
    if not isinstance(payload, dict):
        return ""
    # Normalize keys to map of lowercase-without-spaces -> original value
    norm = {}
    for k, v in payload.items():
        if k is None:
            continue
        key_norm = str(k).lower().replace(" ", "").replace("_", "").replace("-", "")
        norm[key_norm] = v

    candidates = [
        "invoiceno",
        "invoicenumber",
        "invoicenumberno",
        "invoiceno",     # duplicated intentionally safe
        "invoicenumber",
        "invoicenumberno",
        "invoicenumber",
        "invoicenumber",
        "invoicenumber",
        "invoicenumber",
        "invoice",
        "invno",
        "invnumber",
        "invoicenumber",
        "invoicenumber",
        "invoiceno",
        "invoicenumber",
    ]
    # also accept some common exact spellings with spaces/underscore in the original (normalized above)
    for cand in candidates:
        c = cand.lower().replace(" ", "").replace("_", "").replace("-", "")
        if c in norm and norm[c] not in (None, "") and str(norm[c]).strip() != "":
            return str(norm[c]).strip()

    # fallback: try some original keys with capitalization (legacy)
    for alt in ["Invoice No", "InvoiceNo", "Invoice_Number", "Invoice Number", "Invoice"]:
        if alt in payload and payload[alt] not in (None, "") and str(payload[alt]).strip() != "":
            return str(payload[alt]).strip()

    return ""

# ==========================================================
# ✅ API: Human Review list (now returns invoice_no)
# ==========================================================
@human_review_bp.route("/api/human_review", methods=["GET"])
def get_human_review():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        client_id = request.args.get("client_id")
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")

        # Select extracted_json so we can parse invoice_no
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
                d.extracted_json
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            WHERE (d.data_extraction_status ILIKE 'Completed%%' OR d.data_extraction_status ILIKE 'Success%%')
              AND (d.erp_entry_status ILIKE 'Failed%%' OR d.erp_entry_status ILIKE 'Error%%' OR d.erp_entry_status ILIKE 'File Missing%%')
        """

        filters = []
        params = []

        # Optional client filter
        if client_id:
            filters.append("d.client_id = %s")
            params.append(client_id)

        # Date filtering logic
        if from_date and to_date:
            filters.append("DATE(d.uploaded_on) BETWEEN %s AND %s")
            params.extend([from_date, to_date])
        elif from_date:
            filters.append("DATE(d.uploaded_on) >= %s")
            params.append(from_date)
        elif to_date:
            filters.append("DATE(d.uploaded_on) <= %s")
            params.append(to_date)

        # Add dynamic filters if any
        if filters:
            base_query += " AND " + " AND ".join(filters)

        base_query += " ORDER BY d.uploaded_on DESC;"

        # Debug logging
        print("\n🟡 [HUMAN_REVIEW DEBUG]")
        print("🔹 SQL:", base_query)
        print("🔹 Params:", params)

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()

        # Column debug
        colnames = [desc[0] for desc in cur.description]
        print("🟢 Columns Returned:", colnames)
        print("🟢 Row Count:", len(rows))

        # Prepare structured JSON data
        data = []
        for r in rows:
            # r layout matches SELECT above
            # 0: doc_id, 1: client_name, 2: doc_type, 3: doc_file_name, 4: uploaded_on,
            # 5: updated_at, 6: overall_status, 7: data_extraction_status, 8: erp_entry_status, 9: extracted_json
            uploaded_on_str = (
                r[4].strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(r[4], datetime)
                else str(r[4]) if r[4] else None
            )

            updated_at_str = (
                r[5].strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(r[5], datetime)
                else str(r[5]) if r[5] else ""
            )

            extracted_json = r[9] if len(r) > 9 else None
            raw = _unwrap_final_data(_parse_json(extracted_json))
            invoice_no = _find_invoice_no(raw) or ""

            data.append({
                "id": r[0],
                "client_name": r[1],
                "doc_type": r[2],
                "file_name": r[3],
                "uploaded_on": uploaded_on_str,
                "updated_at": updated_at_str,
                "overall_status": r[6],
                "data_extraction_status": r[7],
                "erp_entry_status": r[8],
                "invoice_no": invoice_no,
                "extracted_json": extracted_json,
            })

        release_connection(conn)
        print(f"✅ Returned {len(data)} rows.")
        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print("❌ Human Review API Error:", str(e))
        traceback.print_exc()

        # Attempt to safely release connection
        if conn:
            try:
                release_connection(conn)
            except Exception as ex:
                print("⚠️ DB Release Error:", str(ex))

        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500
