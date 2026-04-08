# routes/dashboard_routes.py
from flask import Blueprint, request, jsonify
from config.db_config import get_connection, release_connection
from datetime import datetime, timedelta

dashboard_bp = Blueprint("dashboard_bp", __name__)

@dashboard_bp.route("/api/dashboard_summary", methods=["GET"])
def dashboard_summary():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # --- Optional Filters ---
        client_id = request.args.get("client_id")
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")

        filters = []
        params = []

        if client_id:
            filters.append("d.client_id = %s")
            params.append(client_id)

        if from_date and to_date:
            filters.append("DATE(d.uploaded_on) BETWEEN %s AND %s")
            params.extend([from_date, to_date])
        elif from_date:
            filters.append("DATE(d.uploaded_on) >= %s")
            params.append(from_date)
        elif to_date:
            filters.append("DATE(d.uploaded_on) <= %s")
            params.append(to_date)

        where_clause = "WHERE " + " AND ".join(filters) if filters else ""

        # --- 1️⃣ Summary counts ---
        summary_query = f"""
            SELECT 
                COUNT(*) AS total_docs,
                COUNT(*) FILTER (WHERE d.overall_status ILIKE 'In Progress%%') AS in_progress,
                COUNT(*) FILTER (WHERE d.overall_status ILIKE 'Completed%%') AS completed,
                -- Keep legacy 'failed' bucket (overall_status) but exclude explicit Duplicate labels
                COUNT(*) FILTER (
                    WHERE (d.overall_status ILIKE 'Failed%%' OR d.overall_status ILIKE 'Error%%')
                    AND NOT (d.overall_status ILIKE 'Duplicate%%')
                ) AS failed,
                -- Count duplicate occurrences reported either by overall_status OR by ERP columns
                -- use trimmed ERP status to match values like 'Duplicate ' with trailing spaces
                COUNT(*) FILTER (
                    WHERE (
                        d.overall_status ILIKE 'Duplicate%%'
                        OR TRIM(COALESCE(d.erp_entry_status::text, '')) ILIKE 'Duplicate%%'
                    )
                ) AS duplicate,
                COUNT(*) FILTER (
                    WHERE (d.data_extraction_status ILIKE 'Completed%%' OR d.data_extraction_status ILIKE 'Success%%')
                    AND (d.erp_entry_status ILIKE 'Failed%%' OR d.erp_entry_status ILIKE 'Error%%')
                ) AS human_review
            FROM doc_processing_log d
            {where_clause};
        """
        cur.execute(summary_query, tuple(params))
        summary_row = cur.fetchone()

        summary = {
            "total_docs": summary_row[0] or 0,
            "in_progress": summary_row[1] or 0,
            "completed": summary_row[2] or 0,
            "failed": summary_row[3] or 0,
            "duplicate": summary_row[4] or 0,
            "human_review": summary_row[5] or 0,
        }

        # --- 2️⃣ Trend chart: docs per day (last 7 or filtered) ---
        trend_query = f"""
            SELECT TO_CHAR(DATE(d.uploaded_on), 'Mon DD') AS day_label,
                   COUNT(*) AS documents
            FROM doc_processing_log d
            {where_clause}
            GROUP BY day_label
            ORDER BY MIN(DATE(d.uploaded_on));
        """
        cur.execute(trend_query, tuple(params))
        trend_rows = cur.fetchall()
        trend_data = [{"date": r[0], "documents": r[1]} for r in trend_rows]

        # --- 3️⃣ Recent uploads (last 5) ---
        recent_query = f"""
            SELECT 
                c.client_name,
                f.doc_type,
                d.doc_file_name,
                d.uploaded_on,
                d.overall_status,
                d.erp_entry_status
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN doc_formats f ON d.doc_format_id = f.doc_format_id
            {where_clause}
            ORDER BY d.uploaded_on DESC
            LIMIT 5;
        """
        cur.execute(recent_query, tuple(params))
        recent_rows = cur.fetchall()

        recent_docs = []
        for r in recent_rows:
            client_name = r[0]
            doc_type = r[1]
            file_name = r[2]
            uploaded_on = r[3].strftime("%Y-%m-%d %H:%M:%S") if r[3] else None
            overall_status = r[4]
            erp_status1 = r[5]

            # prefer trimmed overall_status; then check erp_entry (alternate column), then erp_entry_status
            chosen_status = None
            if overall_status and str(overall_status).strip() != "":
                chosen_status = str(overall_status).strip()
            else:
                # check alternate ERP columns
                for cand in (erp_status1,):
                    if cand and str(cand).strip() != "":
                        chosen_status = str(cand).strip()
                        break

            recent_docs.append({
                "client": client_name,
                "doc_type": doc_type,
                "file_name": file_name,
                "uploaded_on": uploaded_on,
                "status": chosen_status,
            })

        release_connection(conn)
        return jsonify({
            "status": "success",
            "summary": summary,
            "trend": trend_data,
            "recent": recent_docs
        }), 200

    except Exception as e:
        print("❌ Dashboard Summary API Error:", str(e))
        if conn:
            try:
                release_connection(conn)
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500
