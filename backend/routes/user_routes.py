from flask import Blueprint, request, jsonify
from database.db import get_connection

user_blueprint = Blueprint('users', __name__)

@user_blueprint.route('/api/admin/users', methods=['GET'])
def get_all_users():
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
def create_user():
    data = request.get_json()
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
        cur.execute("INSERT INTO user_master (user_name, password, is_active) VALUES (%s, %s, %s) RETURNING user_id",
            (user_name, user_name, is_active))
        new_id = cur.fetchone()[0]
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": f"User '{user_name}' created. Default password is same as username.", "user_id": new_id}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_blueprint.route('/api/admin/users/<int:user_id>/toggle', methods=['PATCH'])
def toggle_user_status(user_id):
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

@user_blueprint.route('/api/change-password', methods=['POST'])
def change_password():
    data = request.get_json()
    user_id = data.get('user_id')
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()
    if not all([user_id, old_password, new_password]):
        return jsonify({"success": False, "message": "All fields required"}), 400
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM user_master WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "User not found"}), 404
        if row[0] != old_password:
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Current password is incorrect"}), 401
        cur.execute("UPDATE user_master SET password = %s WHERE user_id = %s", (new_password, user_id))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": "Password changed successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500