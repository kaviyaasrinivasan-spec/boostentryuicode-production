# routes/report_routes.py
"""
Invoice Processing Report API
Provides counts of invoices by processing status, filterable by branch and date range.
"""
from flask import Blueprint, request, jsonify
from config.db_config import get_connection, release_connection
from datetime import datetime, date, timedelta
import traceback

report_bp = Blueprint("report_bp", __name__)


# ─────────────────────────────────────────────────────────────
# Helper: build date range from shortcut names
# ─────────────────────────────────────────────────────────────
def _resolve_date_range(period: str, from_date_str: str, to_date_str: str):
    """
    Returns (from_date, to_date) as datetime.date objects.
    period can be: today | yesterday | this_week | this_month | custom
    For 'custom', from_date_str and to_date_str are used (YYYY-MM-DD).
    """
    today = date.today()
    if period == "today":
        return today, today
    elif period == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    elif period == "this_week":
        # Mon–Sun week
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "this_month":
        start = today.replace(day=1)
        return start, today
    else:
        # custom or default all-time
        try:
            fd = datetime.strptime(from_date_str, "%Y-%m-%d").date() if from_date_str else None
            td = datetime.strptime(to_date_str,   "%Y-%m-%d").date() if to_date_str   else None
        except ValueError:
            fd, td = None, None
        return fd, td


# ─────────────────────────────────────────────────────────────
# API 1: GET /api/report/invoice-processing
#   Query params:
#     client_id  – integer; omit or "all" for all branches
#     period     – today | yesterday | this_week | this_month | custom
#     from_date  – YYYY-MM-DD  (only when period=custom)
#     to_date    – YYYY-MM-DD  (only when period=custom)
# ─────────────────────────────────────────────────────────────
@report_bp.route("/api/report/invoice-processing", methods=["GET"])
def invoice_processing_report():
    conn = None
    try:
        client_id   = request.args.get("client_id")      # "all" or int string
        period      = request.args.get("period", "today")
        from_date_s = request.args.get("from_date", "")
        to_date_s   = request.args.get("to_date", "")

        from_date, to_date = _resolve_date_range(period, from_date_s, to_date_s)

        conn = get_connection()
        cur  = conn.cursor()

        # ── Build date filter ──────────────────────────────────
        date_cond  = ""
        date_params = []
        if from_date and to_date:
            date_cond = "AND DATE(d.uploaded_on) BETWEEN %s AND %s"
            date_params = [str(from_date), str(to_date)]
        elif from_date:
            date_cond = "AND DATE(d.uploaded_on) >= %s"
            date_params = [str(from_date)]
        elif to_date:
            date_cond = "AND DATE(d.uploaded_on) <= %s"
            date_params = [str(to_date)]

        # ── Build client filter ────────────────────────────────
        client_cond  = ""
        client_params = []
        if client_id and client_id.lower() != "all":
            client_cond = "AND d.client_id = %s"
            client_params = [client_id]

        # ── Main counts query ──────────────────────────────────
        count_query = f"""
            SELECT
                COUNT(*)                                                          AS total,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed')     AS completed,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed AHR') AS completed_ahr,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Failed')        AS failed
            FROM doc_processing_log d
            WHERE 1=1
            {date_cond}
            {client_cond}
        """
        cur.execute(count_query, tuple(date_params + client_params))
        row = cur.fetchone()
        total, completed, completed_ahr, failed = row

        # ── Per-branch breakdown ───────────────────────────────
        branch_query = f"""
            SELECT
                c.client_id,
                c.client_name,
                COUNT(*)                                                          AS total,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed')     AS completed,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed AHR') AS completed_ahr,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Failed')        AS failed
            FROM doc_processing_log d
            LEFT JOIN clients c ON d.client_id = c.client_id
            WHERE 1=1
            {date_cond}
            {client_cond}
            GROUP BY c.client_id, c.client_name
            ORDER BY c.client_name
        """
        cur.execute(branch_query, tuple(date_params + client_params))
        branch_rows = cur.fetchall()

        branches = [
            {
                "client_id":     br[0],
                "client_name":   br[1] or "Unknown",
                "total":         br[2],
                "completed":     br[3],
                "completed_ahr": br[4],
                "failed":        br[5],
            }
            for br in branch_rows
        ]

        # ── Daily trend (last 7 or selected range) ─────────────
        trend_query = f"""
            SELECT
                DATE(d.uploaded_on)                                               AS day,
                COUNT(*)                                                          AS total,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed')     AS completed,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Completed AHR') AS completed_ahr,
                COUNT(*) FILTER (WHERE d.erp_entry_status ILIKE 'Failed')        AS failed
            FROM doc_processing_log d
            WHERE 1=1
            {date_cond}
            {client_cond}
            GROUP BY DATE(d.uploaded_on)
            ORDER BY day DESC
            LIMIT 30
        """
        cur.execute(trend_query, tuple(date_params + client_params))
        trend_rows = cur.fetchall()

        trend = [
            {
                "date":          str(tr[0]),
                "total":         tr[1],
                "completed":     tr[2],
                "completed_ahr": tr[3],
                "failed":        tr[4],
            }
            for tr in trend_rows
        ]
        trend.reverse()  # oldest → newest for chart

        release_connection(conn)
        conn = None

        return jsonify({
            "status": "success",
            "data": {
                "summary": {
                    "total":         int(total         or 0),
                    "completed":     int(completed     or 0),
                    "completed_ahr": int(completed_ahr or 0),
                    "failed":        int(failed        or 0),
                },
                "branches": branches,
                "trend":    trend,
                "filters": {
                    "client_id":  client_id or "all",
                    "period":     period,
                    "from_date":  str(from_date) if from_date else None,
                    "to_date":    str(to_date)   if to_date   else None,
                },
            }
        }), 200

    except Exception as e:
        print("❌ Report Error:", str(e))
        traceback.print_exc()
        if conn:
            release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API 2: GET /api/report/branches  –  list of clients/branches
# ─────────────────────────────────────────────────────────────
@report_bp.route("/api/report/branches", methods=["GET"])
def get_branches():
    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT client_id, client_name FROM clients ORDER BY client_name")
        rows = cur.fetchall()
        release_connection(conn)
        conn = None
        branches = [{"client_id": r[0], "client_name": r[1]} for r in rows]
        return jsonify({"status": "success", "data": branches}), 200
    except Exception as e:
        if conn:
            release_connection(conn)
        return jsonify({"status": "error", "message": str(e)}), 500
