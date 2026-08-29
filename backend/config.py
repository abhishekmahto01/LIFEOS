import os
import math
from dotenv import load_dotenv

# Load .env from backend folder or current working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()


def _parse_int_config(name: str, default: int, min_val: int = None, max_val: int = None, multiple_of: int = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        val = default
    else:
        try:
            val = int(raw)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid configuration for {name}: expected an integer, got '{raw}'.")

    if min_val is not None and val < min_val:
        raise ValueError(f"Invalid configuration for {name}: value {val} is below minimum {min_val}.")
    if max_val is not None and val > max_val:
        raise ValueError(f"Invalid configuration for {name}: value {val} exceeds maximum {max_val}.")
    if multiple_of is not None and (val <= 0 or val % multiple_of != 0):
        raise ValueError(f"Invalid configuration for {name}: value {val} must be a positive multiple of {multiple_of}.")
    return val


def _parse_float_config(name: str, default: float, min_val: float = None, max_val: float = None) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        val = default
    else:
        try:
            val = float(raw)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid configuration for {name}: expected a float, got '{raw}'.")

    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"Invalid configuration for {name}: non-finite float value '{raw}' is not allowed.")
    if min_val is not None and val < min_val:
        raise ValueError(f"Invalid configuration for {name}: value {val} is below minimum {min_val}.")
    if max_val is not None and val > max_val:
        raise ValueError(f"Invalid configuration for {name}: value {val} exceeds maximum {max_val}.")
    return val


def _parse_bool_config(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    clean = str(raw).strip().lower()
    if clean in ("true", "1", "yes", "t", "y"):
        return True
    if clean in ("false", "0", "no", "f", "n"):
        return False
    raise ValueError(f"Invalid configuration for {name}: expected a boolean, got '{raw}'.")


class Config:
    # Server & Environment Settings
    PORT = _parse_int_config("PORT", 5000, min_val=1, max_val=65535)
    DEBUG = _parse_bool_config("FLASK_DEBUG", True)
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # Flask Security
    SECRET_KEY = os.getenv("SECRET_KEY", "lifeos-secret-key-change-in-env-32-chars-min")

    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "lifeos-jwt-signing-secret-key-32-chars")
    JWT_ACCESS_TOKEN_EXPIRES = _parse_int_config("JWT_ACCESS_TOKEN_EXPIRES", 86400, min_val=60, max_val=2592000)

    # Fernet Authenticated Encryption Key for OAuth Tokens at Rest
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # Frontend URL & CORS Settings
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
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
    TEST_DB_NAME = os.getenv("TEST_DB_NAME", "lifeos_test")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Temporary Video Upload Pipeline Settings
    TEMP_UPLOAD_DIR = os.path.join(backend_dir, os.getenv("TEMP_UPLOAD_DIR", "temp_uploads"))
    MAX_VIDEO_SIZE_MB = _parse_int_config("MAX_VIDEO_SIZE_MB", 500, min_val=1, max_val=4096)
    MAX_THUMBNAIL_SIZE_MB = _parse_int_config("MAX_THUMBNAIL_SIZE_MB", 10, min_val=1, max_val=50)
    MAX_CONTENT_LENGTH = (MAX_VIDEO_SIZE_MB + MAX_THUMBNAIL_SIZE_MB + 10) * 1024 * 1024

    # Maximum Temporary File Retention (Strictly capped between 1 and 24 hours)
    raw_ttl = os.getenv("TEMP_FILE_TTL_HOURS", os.getenv("TEMP_FILE_RETENTION_HOURS", "24"))
    TEMP_FILE_TTL_HOURS = _parse_int_config("TEMP_FILE_TTL_HOURS", int(raw_ttl) if str(raw_ttl).isdigit() else 24, min_val=1, max_val=24)
    TEMP_FILE_RETENTION_HOURS = TEMP_FILE_TTL_HOURS

    # Google / YouTube OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/social-media/oauth/youtube/callback")

    # YouTube Resumable Publishing Configuration (Phase 6)
    YOUTUBE_UPLOAD_CHUNK_SIZE_KB = _parse_int_config("YOUTUBE_UPLOAD_CHUNK_SIZE_KB", 1024, min_val=256, max_val=32768, multiple_of=256)
    YOUTUBE_UPLOAD_CHUNK_SIZE_BYTES = YOUTUBE_UPLOAD_CHUNK_SIZE_KB * 1024

    YOUTUBE_UPLOAD_MAX_RETRIES = _parse_int_config("YOUTUBE_UPLOAD_MAX_RETRIES", 5, min_val=1, max_val=10)
    YOUTUBE_UPLOAD_INITIAL_BACKOFF_SECONDS = _parse_float_config("YOUTUBE_UPLOAD_INITIAL_BACKOFF_SECONDS", 1.0, min_val=0.1, max_val=10.0)
    YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS = _parse_int_config("YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS", 15, min_val=5, max_val=60)
    YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS = _parse_int_config("YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS", 60, min_val=15, max_val=300)
    YOUTUBE_PROCESSING_POLL_INTERVAL_SECONDS = _parse_float_config("YOUTUBE_PROCESSING_POLL_INTERVAL_SECONDS", 3.0, min_val=0.5, max_val=60.0)
    YOUTUBE_PROCESSING_MAX_POLLS_PER_RUN = _parse_int_config("YOUTUBE_PROCESSING_MAX_POLLS_PER_RUN", 10, min_val=1, max_val=100)
    YOUTUBE_PUBLISH_MAX_WORKERS = _parse_int_config("YOUTUBE_PUBLISH_MAX_WORKERS", 3, min_val=1, max_val=20)
    YOUTUBE_PUBLISH_LEASE_SECONDS = _parse_int_config("YOUTUBE_PUBLISH_LEASE_SECONDS", 300, min_val=60, max_val=3600)
    ENABLE_YOUTUBE_PUBLISH_WORKER = _parse_bool_config("ENABLE_YOUTUBE_PUBLISH_WORKER", True)

    # Meta Graph API (Facebook / Instagram)
    META_APP_ID = os.getenv("META_APP_ID", "")
    META_APP_SECRET = os.getenv("META_APP_SECRET", "")
    META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:5000/api/social-media/oauth/meta/callback")
