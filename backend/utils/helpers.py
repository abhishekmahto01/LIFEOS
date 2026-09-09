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
            if "current_user" in sig.parameters and "current_user" not in kwargs:
                kwargs["current_user"] = current_user
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

def is_admin_user(current_user: dict) -> bool:
    """Check if the provided user dict has administrative privileges."""
    if not current_user or not isinstance(current_user, dict):
        return False
    username = str(current_user.get("username") or "").strip().lower()
    user_id = current_user.get("user_id")
    return username == "admin" or user_id == 1

def admin_required(f):
    """
    Authorization decorator ensuring only administrators can access the endpoint.
    Automatically applies token_required if request context lacks authenticated user.
    """
    @token_required
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        current_user = getattr(request, "current_user", None) or kwargs.get("current_user")
        if not is_admin_user(current_user):
            return jsonify({
                "success": False,
                "error": "Admin access required",
                "message": "Admin privileges are required for this action."
            }), 403

        import inspect
        sig = inspect.signature(f)
        if "current_user" in sig.parameters and "current_user" not in kwargs:
            kwargs["current_user"] = current_user
        return f(*args, **kwargs)

    return decorated

def get_user_allowed_modules(user_id: int, username: str = None) -> list[dict]:
    """
    Fetch the list of allowed active modules for a given user.
    Admins automatically receive all active modules.
    Normal users receive only active modules granted in user_module_permission.
    """
    user_is_admin = (user_id == 1) or (str(username or "").strip().lower() == "admin")

    conn = get_connection()
    cur = conn.cursor()

    try:
        if user_is_admin:
            cur.execute("""
                SELECT id, module_name, module_code, route, sequence_no
                FROM module_master
                WHERE is_active = TRUE
                ORDER BY sequence_no ASC, id ASC;
            """)
        else:
            cur.execute("""
                SELECT m.id, m.module_name, m.module_code, m.route, m.sequence_no
                FROM user_module_permission p
                JOIN module_master m ON p.module_id = m.id
                WHERE p.user_id = %s
                  AND m.is_active = TRUE
                  AND COALESCE(m.module_code, '') != 'admin'
                  AND LOWER(m.module_name) != 'admin'
                ORDER BY m.sequence_no ASC, m.id ASC;
            """, (user_id,))

        rows = cur.fetchall()
        modules = []
        for r in rows:
            mod_code = r[2] or r[1].lower().replace(" ", "_")
            modules.append({
                "module_id": r[0],
                "id": r[0],
                "module_name": r[1],
                "module_code": mod_code,
                "route": r[3],
                "sequence_no": r[4]
            })
        return modules
    finally:
        cur.close()
        conn.close()

def module_required(required_module: str):
    """
    Decorator protecting endpoints based on module access permissions.
    - Admin automatically bypasses all module checks.
    - Normal users must have explicit active permission for the required module.
    Returns 403 with {"error": "You do not have access to this module"} if denied.
    """
    def decorator(f):
        @token_required
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            current_user = getattr(request, "current_user", None) or kwargs.get("current_user")
            if not current_user:
                return jsonify({
                    "success": False,
                    "error": "Authentication required."
                }), 401

            # Admin users automatically bypass all module checks
            if is_admin_user(current_user):
                import inspect
                sig = inspect.signature(f)
                if "current_user" in sig.parameters and "current_user" not in kwargs:
                    kwargs["current_user"] = current_user
                return f(*args, **kwargs)

            # Check if normal user has active permission for the target module
            allowed_modules = get_user_allowed_modules(
                current_user["user_id"],
                current_user.get("username")
            )

            target = (required_module or "").strip().lower()
            has_access = any(
                (m.get("module_code") or "").lower() == target or
                (m.get("module_name") or "").lower() == target or
                (m.get("route") or "").lower() == target or
                (m.get("route") or "").lower() == f"/{target}"
                for m in allowed_modules
            )

            if not has_access:
                return jsonify({
                    "success": False,
                    "error": "You do not have access to this module",
                    "message": f"Access denied. You do not have permission to access the '{required_module}' module."
                }), 403

            import inspect
            sig = inspect.signature(f)
            if "current_user" in sig.parameters and "current_user" not in kwargs:
                kwargs["current_user"] = current_user
            return f(*args, **kwargs)

        return decorated
    return decorator


