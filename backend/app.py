from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from database.db import init_db

from routes.auth_routes import auth_blueprint
from routes.user_routes import user_blueprint
from routes.dashboard_routes import dashboard_bp
from routes.job_routes import job_blueprint
from routes.discipline_routes import discipline_blueprint
from routes.social_routes import social_blueprint
from services.upload_service import cleanup_expired_and_orphan_files

app = Flask(__name__)
app.config.from_object(Config)

# Configure CORS with origins restricted by environment configuration
CORS(
    app,
    resources={r"/api/*": {"origins": Config.CORS_ALLOWED_ORIGINS}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
)

# Global 413 Payload Too Large handler
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "success": False,
        "error": "Uploaded payload exceeds maximum allowed size limit."
    }), 413

# Ensure database tables/columns are verified on startup
init_db()

# Run safe startup cleanup for stale/orphan temporary files
try:
    cleanup_expired_and_orphan_files()
except Exception as e:
    print("Warning: Startup temporary file cleanup error:", e)

# Register Blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(user_blueprint)
app.register_blueprint(dashboard_bp)
app.register_blueprint(job_blueprint)
app.register_blueprint(discipline_blueprint)
app.register_blueprint(social_blueprint)

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)
