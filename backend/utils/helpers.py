import functools
import bcrypt
import jwt
from flask import request, jsonify
from database.db import get_connection
from utils.jwt_handler import decode_token

def is_bcrypt_hash(value: str) -> bool:
    """Check if a string is a valid bcrypt hash."""
    if not value or not isinstance(value, str):
        return False
    return value.startswith("$2b$") or value.startswith("$2a$") or value.startswith("$2y$")

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with a generated salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")

def check_password(plain_password: str, stored_hash_or_plain: str) -> bool:
    """
    Check password against stored value.
    Supports bcrypt hash verification and transparent legacy plaintext fallback.
    """
    if not plain_password or not stored_hash_or_plain:
        return False

    if is_bcrypt_hash(stored_hash_or_plain):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                stored_hash_or_plain.encode("utf-8")
            )
        except Exception:
            return False
    else:
        # Legacy plaintext comparison
        return plain_password == stored_hash_or_plain

def token_required(f):
    """
    Authentication decorator for private API routes.
    Extracts Bearer token from 'Authorization' header, verifies JWT,
    and injects 'current_user' into request context and kwargs.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)

        if not auth_header:
            return jsonify({
                "success": False,
                "message": "Authentication token is missing. Please provide Authorization: Bearer <token>."
            }), 401

        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "success": False,
                "message": "Invalid Authorization header format. Expected 'Bearer <token>'."
            }), 401

        token = parts[1]

        try:
            payload = decode_token(token)
            user_id = payload.get("user_id")

            # Verify user exists and is active in database
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, user_name, is_active FROM user_master WHERE user_id = %s;",
                (user_id,)
            )
            user = cur.fetchone()
            cur.close()
            conn.close()

            if not user:
                return jsonify({
                    "success": False,
                    "message": "User associated with this token no longer exists."
                }), 401

            if not user[2]:  # is_active
                return jsonify({
                    "success": False,
                    "message": "Account is inactive. Please contact administrator."
                }), 403

            current_user = {
                "user_id": user[0],
                "username": user[1],
                "is_active": user[2]
            }

            # Attach to flask request context
            request.current_user = current_user

            # If function accepts current_user parameter, pass it; else call standard
            import inspect
            sig = inspect.signature(f)
            if "current_user" in sig.parameters:
                return f(*args, current_user=current_user, **kwargs)
            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "message": "Authentication token has expired. Please log in again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid authentication token."
            }), 401
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Authentication verification error: {str(e)}"
            }), 500

    return decorated
