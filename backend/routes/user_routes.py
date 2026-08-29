from flask import Blueprint, request, jsonify
from database.db import get_connection
from utils.helpers import token_required, hash_password, check_password

user_blueprint = Blueprint('users', __name__)

@user_blueprint.route('/api/admin/users', methods=['GET'])
@token_required
def get_all_users(current_user):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, user_name, is_active, created_at FROM user_master ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        users = [{"user_id": r[0], "user_name": r[1], "is_active": r[2], "created_at": str(r[3]) if r[3] else None} for r in rows]
        return jsonify({"success": True, "users": users}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_blueprint.route('/api/admin/users', methods=['POST'])
@token_required
def create_user(current_user):
    data = request.get_json() or {}
    user_name = data.get('user_name', '').strip()
    is_active = data.get('is_active', True)
    if not user_name:
        return jsonify({"success": False, "message": "user_name is required"}), 400
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM user_master WHERE user_name = %s", (user_name,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Username already exists"}), 409

        # Secure default password hashed with bcrypt
        hashed_default_pwd = hash_password(user_name)

        cur.execute(
            "INSERT INTO user_master (user_name, password, is_active) VALUES (%s, %s, %s) RETURNING user_id",
            (user_name, hashed_default_pwd, is_active)
        )
        new_id = cur.fetchone()[0]
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": f"User '{user_name}' created securely. Default password is same as username.", "user_id": new_id}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_blueprint.route('/api/admin/users/<int:user_id>/toggle', methods=['PATCH'])
@token_required
def toggle_user_status(user_id, current_user):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE user_master SET is_active = NOT is_active WHERE user_id = %s RETURNING is_active", (user_id,))
        result = cur.fetchone()
        if not result:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "User not found"}), 404
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "is_active": result[0]}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500