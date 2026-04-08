# routes/login_route.py
from flask import Blueprint, request, jsonify
from config.db_config import get_db_cursor
import bcrypt

login_bp = Blueprint("login_bp", __name__)

def _is_probably_bcrypt(value: str) -> bool:
    """
    Best-effort check whether a stored password looks like a bcrypt hash.
    """
    return isinstance(value, str) and (
        value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")
    )

@login_bp.route("/api/login", methods=["POST"])
def login():
    """
    POST /api/login
    Body: { "email": "...", "password": "..." }

    Success (200):
    { "status": "success", "user": { "id": int, "email": str, "name": str } }

    Failure (400/401/500):
    { "status": "error", "message": "..." }
    """
    try:
        # 1) Parse inputs
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        password = (data.get("password") or "")

        if not email or not password:
            return jsonify({"status": "error", "message": "Missing email or password"}), 400

        # 2) Fetch user by email (case-insensitive)
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT id, email, name, password
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1;
                """,
                (email,),
            )
            row = cur.fetchone()

        if not row:
            # Email not found
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401

        user_id, user_email, user_name, stored_password = row

        # 3) Verify password
        if stored_password and _is_probably_bcrypt(stored_password):
            try:
                valid = bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8"))
            except Exception:
                valid = False
        else:
            # Plaintext fallback (for legacy rows)
            valid = (stored_password == password)

        if not valid:
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401

        # 4) Optional: upgrade legacy plaintext passwords to bcrypt (one-time on success)
        #    Uncomment this block if you want to migrate silently.
        #
        # if stored_password and not _is_probably_bcrypt(stored_password):
        #     try:
        #         new_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        #         with get_db_cursor(commit=True) as cur:
        #             cur.execute(
        #                 "UPDATE public.users SET password = %s WHERE id = %s;",
        #                 (new_hash, user_id)
        #             )
        #     except Exception:
        #         # If hashing fails, continue without blocking login
        #         pass

        # 5) Insert login log with IST time (Asia/Kolkata)
        #    Your users_logs schema: id, user_id, name, email, logged_at (timestamptz)
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO users_logs (user_id, name, email, logged_at)
                SELECT id, name, email, (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')
                FROM users
                WHERE id = %s;
                """,
                (user_id,),
            )

        # 6) Return user payload for the client (React stores it if needed)
        return jsonify({
            "status": "success",
            "user": {
                "id": user_id,
                "email": user_email,
                "name": user_name
            }
        }), 200

    except Exception as e:
        # Log server-side for debugging; keep client message generic
        print("❌ Login API Error:", str(e))
        return jsonify({"status": "error", "message": "Server error"}), 500
