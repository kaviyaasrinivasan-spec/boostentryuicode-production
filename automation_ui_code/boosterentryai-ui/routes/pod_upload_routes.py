from flask import Blueprint, request, jsonify
import os
import datetime
import uuid
from werkzeug.utils import secure_filename
from config.db_config import get_connection, release_connection

pod_upload_bp = Blueprint("pod_upload_bp", __name__)

# Directory to save POD PDFs
POD_SAVE_DIR = "/root/wbai_doc_extractor_engine-maincopy/pod_pdfs"

# Ensure directory exists
if not os.path.exists(POD_SAVE_DIR):
    os.makedirs(POD_SAVE_DIR)


# ==============================================================
# ? API 1: Upload POD PDF — save file + insert into pod_upload
# ==============================================================
@pod_upload_bp.route("/api/pod-upload", methods=["POST"])
def upload_pod():
    """
    Save PDF to disk and insert a record into pod_upload table.
    Checks for duplicate by file name (original_file_name).
    Status starts as 'In Progress' once saved.
    """
    conn = None
    try:
        client_id = request.form.get("client_id")
        format_id = request.form.get("doc_format_id")

        files = request.files.getlist("files")
        if not files:
            one = request.files.get("file")
            if one:
                files = [one]

        if not files:
            return jsonify({"status": "error", "message": "No files received"}), 400

        saved_files = []
        duplicate_files = []

        for f in files:
            orig_name = secure_filename(f.filename or "pod.pdf")

            # -- Assign branch name based on client_id for automation credentials --
            branch_map = {"5": "Arakkonam", "7": "Tadapatri"}
            branch_name = branch_map.get(str(client_id), "Arakkonam") # Default to Arakkonam

            # -- Save file to disk (still needed for Bot) --------------
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            short_uuid = uuid.uuid4().hex[:8]
            new_filename = f"{branch_name}_{ts}_{short_uuid}_{orig_name}"
            save_path = os.path.join(POD_SAVE_DIR, new_filename)
            f.save(save_path)

            # -- NOTE: No placeholder insert into pod_upload --
            # auto_process_pod.py creates the real record with di_no after extraction.

            saved_files.append({
                "id": None,
                "original_name": orig_name,
                "saved_as": new_filename,
                "status": "In Progress",
            })
            print(f"Saved POD file: {new_filename} (branch={branch_name}) - awaiting extraction")

        # Build response
        if duplicate_files and not saved_files:
            return jsonify({
                "status": "duplicate",
                "message": f"{len(duplicate_files)} duplicate file(s) detected",
                "duplicates": duplicate_files,
            }), 200

        return jsonify({
            "status": "success",
            "message": f"Saved {len(saved_files)} file(s). Duplicates: {len(duplicate_files)}",
            "saved": saved_files,
            "duplicates": duplicate_files,
        }), 200

    except Exception as e:
        print(f"? POD Upload Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            release_connection(conn)


# ==============================================================
# ? API 2: POD Monitoring — list pod_upload rows with status
# ==============================================================
@pod_upload_bp.route("/api/pod-monitoring", methods=["GET"])
def get_pod_monitoring():
    """
    Returns records from pod_upload table with:
      - id, file_name (original_file_name), status, uploaded_at, updated_at, di_no
    Supports:
      - ?from_date=YYYY-MM-DD
      - ?to_date=YYYY-MM-DD
      - ?status=In Progress | Completed | Duplicate | Failed
    """
    conn = None
    try:
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")
        status_filter = request.args.get("status")

        conn = get_connection()
        cur = conn.cursor()

        # -- Use actual pod_upload table columns ------------------------
        # id, di_no, client_erp_entry, created_at
        # Status is DERIVED from client_erp_entry:
        #   NULL / ''    ? 'In Progress'
        #   'false'      ? 'Completed'
        #   'true'       ? 'Failed'
        query = """
            SELECT
                id,
                COALESCE(di_no, '') AS di_no,
                client_erp_entry,
                created_at
            FROM pod_upload
            WHERE 1=1
        """
        params = []

        if from_date and to_date:
            query += " AND DATE(created_at) BETWEEN %s AND %s"
            params.extend([from_date, to_date])
        elif from_date:
            query += " AND DATE(created_at) >= %s"
            params.append(from_date)
        elif to_date:
            query += " AND DATE(created_at) <= %s"
            params.append(to_date)

        query += " ORDER BY created_at DESC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        release_connection(conn)
        conn = None

        def derive_status(client_erp_entry):
            """
            Robust status mapping for pod_upload table.
            Maps actual DB values to UI-friendly strings:
              'already existed' / duplicate ? 'Already Existed'
              'false' (completed)            ? 'Completed'
              'failed' / error               ? 'Failed'
              'true' / NULL / inprogress     ? 'In Progress'
            """
            if client_erp_entry is None:
                return "In Progress"
            
            val = str(client_erp_entry).strip().lower()
            
            # Map values correctly
            if val in ["false", "f", "no", "completed", "none"]:
                return "Completed"
            if "exist" in val or "duplicate" in val:
                return "Already Existed"
            if "fail" in val or "error" in val:
                return "Failed"
            if val in ["true", "t", "yes", "in progress", "inprogress"]:
                return "In Progress"
                
            # Default fallback for everything else
            return "In Progress"

        data = []
        for r in rows:
            pod_id, di_no, client_erp_entry, created_at = r
            status = derive_status(client_erp_entry)

            # Apply status filter after derive
            if status_filter and status_filter.lower() not in status.lower():
                continue

            data.append({
                "id": pod_id,
                "di_no": di_no or "",
                "status": status,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else None,
            })

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"? POD Monitoring Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            release_connection(conn)


# ==============================================================
# ? API 3: POD Portal Automation START ? set status = 'In Progress'
#    Called by automation script when portal processing begins.
#    URL: POST /api/pod-status/start
#    Body: { "di_no": "DI/2024/001" }
#       OR { "saved_file_name": "20240101_abc123_pod.pdf" }
# ==============================================================
@pod_upload_bp.route("/api/pod-status/start", methods=["POST"])
def pod_status_start():
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        di_no = (data.get("di_no") or "").strip()
        saved_file_name = (data.get("saved_file_name") or "").strip()

        if not di_no and not saved_file_name:
            return jsonify({"status": "error", "message": "di_no or saved_file_name required"}), 400

        conn = get_connection()
        cur = conn.cursor()

        if di_no:
            cur.execute(
                """
                UPDATE pod_upload
                SET status = 'In Progress', updated_at = NOW()
                WHERE di_no = %s
                """,
                (di_no,),
            )
        else:
            cur.execute(
                """
                UPDATE pod_upload
                SET status = 'In Progress', updated_at = NOW()
                WHERE saved_file_name = %s
                """,
                (saved_file_name,),
            )

        conn.commit()
        release_connection(conn)
        conn = None

        print(f"? POD Status -> In Progress | di_no={di_no or saved_file_name}")
        return jsonify({"status": "success", "message": "Status set to In Progress"}), 200

    except Exception as e:
        print(f"? POD Status Start Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            release_connection(conn)


# ==============================================================
# ? API 4: POD Portal Automation COMPLETE ? check client_erp_entry
#    Called by automation script AFTER portal automation finishes.
#
#    Logic:
#      client_erp_entry = False  ->  status = 'Completed'
#      client_erp_entry = True   ->  status = 'Failed'
#
#    URL: POST /api/pod-status/complete
#    Body: { "di_no": "DI/2024/001" }
#       OR { "saved_file_name": "20240101_abc123_pod.pdf" }
# ==============================================================
@pod_upload_bp.route("/api/pod-status/complete", methods=["POST"])
def pod_status_complete():
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        di_no = (data.get("di_no") or "").strip()
        saved_file_name = (data.get("saved_file_name") or "").strip()

        if not di_no and not saved_file_name:
            return jsonify({"status": "error", "message": "di_no or saved_file_name required"}), 400

        conn = get_connection()
        cur = conn.cursor()

        # Step 1: Fetch client_erp_entry from pod_upload table
        if di_no:
            cur.execute(
                "SELECT id, client_erp_entry FROM pod_upload WHERE di_no = %s ORDER BY uploaded_at DESC LIMIT 1",
                (di_no,),
            )
        else:
            cur.execute(
                "SELECT id, client_erp_entry FROM pod_upload WHERE saved_file_name = %s ORDER BY uploaded_at DESC LIMIT 1",
                (saved_file_name,),
            )

        row = cur.fetchone()
        if not row:
            release_connection(conn)
            return jsonify({"status": "error", "message": "No matching POD record found"}), 404

        pod_id, client_erp_entry = row

        # Step 2: Decide status based on client_erp_entry
        # client_erp_entry = False (or NULL) -> Completed
        # client_erp_entry = True            -> Failed
        if client_erp_entry is True:
            new_status = "Failed"
        else:
            new_status = "Completed"

        # Step 3: Update pod_upload status
        cur.execute(
            """
            UPDATE pod_upload
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_status, pod_id),
        )
        conn.commit()
        release_connection(conn)
        conn = None

        print(f"? POD Status -> {new_status} | di_no={di_no or saved_file_name} | client_erp_entry={client_erp_entry}")
        return jsonify({
            "status": "success",
            "message": f"Status updated to {new_status}",
            "pod_id": pod_id,
            "new_status": new_status,
            "client_erp_entry": client_erp_entry,
        }), 200

    except Exception as e:
        print(f"? POD Status Complete Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            release_connection(conn)
