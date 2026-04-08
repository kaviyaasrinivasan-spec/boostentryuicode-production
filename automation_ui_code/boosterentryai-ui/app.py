# app.py
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os

# ─────────────────────────────────────────────────────────────
# ✅ Load environment variables early
# ─────────────────────────────────────────────────────────────
load_dotenv()

# ─────────────────────────────────────────────────────────────
# ✅ Initialize Flask
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Allow up to 100MB uploads

# CORS: allow your React app to call this API.
# If you know your frontend origin (e.g., https://boostentryai.com),
# replace origins=["*"] with that exact origin for stricter security.
CORS(
    app,
    resources={r"/api/*": {"origins": [
    "*",
    "https://kssroadways.boostentryai.com",
    "http://kssroadways.boostentryai.com",
    ]}},
    supports_credentials=False,
)

# ─────────────────────────────────────────────────────────────
# ✅ Import & register blueprints (routes)
# ─────────────────────────────────────────────────────────────
from routes.upload_routes import upload_bp
from routes.human_review_routes import human_review_bp
from routes.dashboard_routes import dashboard_bp
from routes.fix_review_routes import fix_review_bp
from routes.monitoring_routes import monitoring_bp
from routes.login_route import login_bp
from routes.users_logs_route import users_logs_bp
from routes.data_transformation_routes import data_transformation_bp
from routes.vehicle_hire_routes import vehicle_hire_bp
from routes.whatsapp_routes import whatsapp_bp  # ← NEW: WhatsApp webhook API
from routes.pod_upload_routes import pod_upload_bp  # ← POD Upload (save to folder only)
from routes.report_routes import report_bp          # ← Invoice Processing Reports

app.register_blueprint(upload_bp)
app.register_blueprint(monitoring_bp)
app.register_blueprint(human_review_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(fix_review_bp)
app.register_blueprint(login_bp)
app.register_blueprint(users_logs_bp)
app.register_blueprint(data_transformation_bp)
app.register_blueprint(vehicle_hire_bp)
app.register_blueprint(whatsapp_bp)  # ← register WhatsApp blueprint
app.register_blueprint(pod_upload_bp)  # ← POD Upload (standalone, folder save only)
app.register_blueprint(report_bp)      # ← Invoice Processing Reports

# ─────────────────────────────────────────────────────────────
# ✅ Environment / Paths (for debugging + file serving)
# ─────────────────────────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "LOCAL")
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_FOLDER", "uploaded_docs"))

print(f"✅ Environment: {ENVIRONMENT}")
print(f"✅ Upload folder: {UPLOAD_FOLDER}")

# Serve PDF/images uploaded by the app
@app.route("/uploaded_docs/<path:filename>")
def serve_uploaded_docs(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ─────────────────────────────────────────────────────────────
# ✅ Simple health check
# ─────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "environment": ENVIRONMENT,
        "upload_folder": UPLOAD_FOLDER,
    }), 200

# ─────────────────────────────────────────────────────────────
# ✅ Error handlers (nice JSON for common cases)
# ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(err):
    return jsonify({"status": "error", "message": "Not found"}), 404

@app.errorhandler(500)
def server_error(err):
    return jsonify({"status": "error", "message": "Server error"}), 500

# ─────────────────────────────────────────────────────────────
# ✅ Entrypoint
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start WhatsApp reminder scheduler
    try:
        from whatsapp_reminder import start_reminder_scheduler
        start_reminder_scheduler()
    except Exception as e:
        print(f"⚠️ Could not start WhatsApp reminder scheduler: {e}")
    
    # Start Auto Timestamp Updater (checks every 4 seconds)
    try:
        from auto_timestamp_updater import start_auto_updater
        start_auto_updater()
        print("✅ Auto Timestamp Updater started (every 4 seconds)")
    except Exception as e:
        print(f"⚠️ Could not start Auto Timestamp Updater: {e}")
    
    print("\n📱 WhatsApp integration is active!")
    print("   - Webhook: /api/whatsapp/webhook")
    print("   - Reminders: Every 3 hours for pending sessions")
    print("\n⏱️ Auto Timestamp Tracking is active!")
    print("   - Checks: Every 4 seconds")
    print("   - Updates: Data Extraction & Consignment Entry times\n")
    
    # 0.0.0.0 exposes the server to the network (Docker friendly),
    # port 30010 matches your existing mapping.
    app.run(host="0.0.0.0", port=30010, debug=True, use_reloader=False)


