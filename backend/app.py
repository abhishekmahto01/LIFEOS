from flask import Flask
from flask_cors import CORS
from config import Config
from database.db import init_db

from routes.auth_routes import auth_blueprint
from routes.user_routes import user_blueprint
from routes.dashboard_routes import dashboard_bp
from routes.job_routes import job_blueprint
from routes.discipline_routes import discipline_blueprint

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

# Ensure database tables/columns are verified on startup
init_db()

# Register Blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(user_blueprint)
app.register_blueprint(dashboard_bp)
app.register_blueprint(job_blueprint)
app.register_blueprint(discipline_blueprint)

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)