from flask import Blueprint, request, jsonify
from config.db_config import get_db_cursor

users_logs_bp = Blueprint("users_logs_bp", __name__)

@users_logs_bp.route("/api/users-logs", methods=["GET"])
def list_users_logs():
    search = (request.args.get("search") or "").strip()
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 10)), 1), 100)
    offset = (page - 1) * page_size

    where = ""
    params = []
    if search:
        where = "WHERE (name ILIKE %s OR email ILIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])

    with get_db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM users_logs {where};", params)
        total = cur.fetchone()[0]

    with get_db_cursor() as cur:
        cur.execute(
            f"""
            SELECT id, user_id, name, email, logged_at
            FROM users_logs
            {where}
            ORDER BY id DESC
            LIMIT %s OFFSET %s;
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    items = [
        {
            "id": r[0],
            "user_id": r[1],
            "name": r[2],
            "email": r[3],
            "logged_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]

    return jsonify({
        "status": "success",
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items
    }), 200
