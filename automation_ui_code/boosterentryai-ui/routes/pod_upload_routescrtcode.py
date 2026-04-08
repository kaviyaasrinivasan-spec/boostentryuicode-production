from flask import Blueprint, request, jsonify
import os
import datetime
import uuid
from werkzeug.utils import secure_filename

pod_upload_bp = Blueprint("pod_upload_bp", __name__)

# Directory where your AI Extractor is watching for files!
POD_SAVE_DIR = "/root/wbai_doc_extractor_engine-maincopy/pod_pdfs"

# Ensure directory exists
if not os.path.exists(POD_SAVE_DIR):
    os.makedirs(POD_SAVE_DIR, exist_ok=True)

@pod_upload_bp.route("/api/pod-upload", methods=["POST"])
def upload_pod():
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"status": "error", "message": "No files received"}), 400

        saved_files = []
        for f in files:
            orig_name = secure_filename(f.filename or "pod.pdf")
            
            # Save file directly to the EXTRACTOR's WATCH FOLDER
            # WE DO NOT INSERT INTO DB HERE - The Extractor will do it!
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            short_uuid = uuid.uuid4().hex[:8]
            new_filename = f"{ts}_{short_uuid}_{orig_name}"
            save_path = os.path.join(POD_SAVE_DIR, new_filename)
            f.save(save_path)

            saved_files.append({"name": orig_name, "path": save_path})
            print(f"? Saved POD for Extractor: {save_path}")

        return jsonify({"status": "success", "message": "Sent to AI Engine", "saved": saved_files}), 200

    except Exception as e:
        print(f"? POD Upload Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@pod_upload_bp.route("/api/pod-monitoring", methods=["GET"])
def get_pod_monitoring():
    from config.db_config import get_connection, release_connection
    conn = None
    try:
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Select all columns we saw in your pgAdmin
        query = "SELECT id, COALESCE(di_no, '') as di_no, client_erp_entry, created_at FROM pod_upload WHERE 1=1"
        params = []
        
        if from_date and to_date:
            query += " AND DATE(created_at) BETWEEN %s AND %s"
            params.extend([from_date, to_date])
            
        query += " ORDER BY created_at DESC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        release_connection(conn)
        conn = None

        data = []
        for r in rows:
            val = str(r[2]).strip().lower() if r[2] else 'true'
            # Derive status
            status = "Completed" if val == 'false' else "In Progress"
            if val == 'already existed': status = "Already Existed"
            if val == 'failed': status = "Failed"
            
            data.append({
                "id": r[0],
                "di_no": r[1],
                "status": status,
                "created_at": r[3].strftime("%Y-%m-%d %H:%M:%S") if r[3] else None
            })
            
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        if conn: release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500
