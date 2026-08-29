import os
from dotenv import load_dotenv

# Load .env from backend folder or current working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

class Config:
    # Server & Environment Settings
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # Flask Security
    SECRET_KEY = os.getenv("SECRET_KEY", "lifeos-secret-key-change-in-env-32-chars-min")

    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "lifeos-jwt-signing-secret-key-32-chars")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 86400))  # 24 hours in seconds

    # Fernet Authenticated Encryption Key for OAuth Tokens at Rest
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # CORS Settings
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000"
        ).split(",") if origin.strip()
    ]

    # Database Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "lifeos")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Temporary Video Upload Pipeline Settings
    TEMP_UPLOAD_DIR = os.path.join(backend_dir, os.getenv("TEMP_UPLOAD_DIR", "temp_uploads"))
    MAX_VIDEO_SIZE_MB = max(1, int(os.getenv("MAX_VIDEO_SIZE_MB", "500")))
    MAX_THUMBNAIL_SIZE_MB = max(1, int(os.getenv("MAX_THUMBNAIL_SIZE_MB", "10")))
    # Flask Request Size Protection (in bytes)
    MAX_CONTENT_LENGTH = (MAX_VIDEO_SIZE_MB + MAX_THUMBNAIL_SIZE_MB + 10) * 1024 * 1024

    # Maximum Temporary File Retention (Strictly capped between 1 and 24 hours)
    raw_ttl = int(os.getenv("TEMP_FILE_TTL_HOURS", os.getenv("TEMP_FILE_RETENTION_HOURS", "24")))
    TEMP_FILE_TTL_HOURS = min(max(raw_ttl, 1), 24)
    TEMP_FILE_RETENTION_HOURS = TEMP_FILE_TTL_HOURS

    # Google / YouTube OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/social-media/oauth/youtube/callback")

    # Meta Graph API (Facebook / Instagram)
    META_APP_ID = os.getenv("META_APP_ID", "")
    META_APP_SECRET = os.getenv("META_APP_SECRET", "")
    META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:5000/api/social-media/oauth/meta/callback")
