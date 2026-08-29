from database.db import get_connection
from utils.helpers import hash_password, check_password, is_bcrypt_hash
from utils.jwt_handler import generate_token

def authenticate_user(username: str, password: str) -> tuple[dict, int]:
    """
    Authenticate user by username and password.
    Supports transparent migration of plaintext passwords to bcrypt upon successful login.
    Returns (response_dict, status_code).
    """
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        return {
            "success": False,
            "message": "Username and password are required."
        }, 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, user_name, password, is_active
        FROM user_master
        WHERE user_name = %s;
        """,
        (username,)
    )
    user = cur.fetchone()

    if user is None:
        cur.close()
        conn.close()
        return {
            "success": False,
            "message": "Invalid username or password."
        }, 401

    user_id, db_username, db_password, is_active = user

    if not is_active:
        cur.close()
        conn.close()
        return {
            "success": False,
            "message": "Account is inactive. Please contact administrator."
        }, 403

    if not check_password(password, db_password):
        cur.close()
        conn.close()
        return {
            "success": False,
            "message": "Invalid username or password."
        }, 401

    # Safe Transparent Migration: If password was in plaintext, hash and update now
    if not is_bcrypt_hash(db_password):
        new_hash = hash_password(password)
        cur.execute(
            "UPDATE user_master SET password = %s WHERE user_id = %s;",
            (new_hash, user_id)
        )
        conn.commit()

    cur.close()
    conn.close()

    # Generate JWT token
    token = generate_token(user_id=user_id, username=db_username)

    return {
        "success": True,
        "message": "Login successful.",
        "token": token,
        "user": {
            "user_id": user_id,
            "username": db_username
        }
    }, 200

def change_user_password(user_id: int, old_password: str, new_password: str) -> tuple[dict, int]:
    """
    Change user password after verifying the old password.
    Stores new password securely as a bcrypt hash.
    """
    old_password = (old_password or "").strip()
    new_password = (new_password or "").strip()

    if not old_password or not new_password:
        return {
            "success": False,
            "message": "Current password and new password are required."
        }, 400

    if len(new_password) < 4:
        return {
            "success": False,
            "message": "New password must be at least 4 characters long."
        }, 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT password FROM user_master WHERE user_id = %s;",
        (user_id,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return {
            "success": False,
            "message": "User not found."
        }, 404

    stored_password = row[0]

    if not check_password(old_password, stored_password):
        cur.close()
        conn.close()
        return {
            "success": False,
            "message": "Current password is incorrect."
        }, 401

    # Hash new password with bcrypt
    hashed_new_password = hash_password(new_password)

    cur.execute(
        "UPDATE user_master SET password = %s WHERE user_id = %s;",
        (hashed_new_password, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "success": True,
        "message": "Password changed successfully."
    }, 200

def migrate_all_plaintext_passwords() -> dict:
    """
    One-time database migration helper to convert all legacy plaintext passwords
    in user_master to secure bcrypt hashes.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, user_name, password FROM user_master;")
    users = cur.fetchall()

    migrated_count = 0
    already_hashed_count = 0

    for uid, uname, pwd in users:
        if pwd and not is_bcrypt_hash(pwd):
            hashed = hash_password(pwd)
            cur.execute(
                "UPDATE user_master SET password = %s WHERE user_id = %s;",
                (hashed, uid)
            )
            migrated_count += 1
        else:
            already_hashed_count += 1

    conn.commit()
    cur.close()
    conn.close()

    return {
        "total_users": len(users),
        "migrated_count": migrated_count,
        "already_hashed_count": already_hashed_count
    }
