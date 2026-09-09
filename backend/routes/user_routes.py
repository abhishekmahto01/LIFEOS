from flask import Blueprint, request, jsonify
from database.db import get_connection
from utils.helpers import token_required, admin_required, hash_password, check_password

user_blueprint = Blueprint('users', __name__)

@user_blueprint.route('/api/admin/users', methods=['GET'])
@admin_required
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
@admin_required
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
@admin_required
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

@user_blueprint.route('/api/admin/modules', methods=['GET'])
@admin_required
def get_admin_modules(current_user):
    """
    Get list of all active modules available for permission assignment.
    The 'admin' module is strictly excluded from assignment.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, module_name, module_code, route, sequence_no
            FROM module_master
            WHERE is_active = TRUE
              AND COALESCE(module_code, '') != 'admin'
              AND LOWER(module_name) != 'admin'
            ORDER BY sequence_no ASC, id ASC;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        modules = [{
            "id": r[0],
            "module_id": r[0],
            "module_name": r[1],
            "module_code": r[2] or r[1].lower().replace(" ", "_"),
            "route": r[3],
            "sequence_no": r[4]
        } for r in rows]

        return jsonify({"success": True, "modules": modules}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_blueprint.route('/api/admin/users/<int:user_id>/modules', methods=['GET'])
@admin_required
def get_user_module_permissions(user_id, current_user):
    """
    Get assigned active module IDs for a specific user.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Ensure user exists
        cur.execute("SELECT user_id, user_name FROM user_master WHERE user_id = %s;", (user_id,))
        target_user = cur.fetchone()
        if not target_user:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "User not found"}), 404

        cur.execute("""
            SELECT p.module_id
            FROM user_module_permission p
            JOIN module_master m ON p.module_id = m.id
            WHERE p.user_id = %s
              AND m.is_active = TRUE
              AND COALESCE(m.module_code, '') != 'admin'
              AND LOWER(m.module_name) != 'admin';
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        assigned_ids = [r[0] for r in rows]
        return jsonify({
            "success": True,
            "user_id": user_id,
            "username": target_user[1],
            "assigned_module_ids": assigned_ids
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_blueprint.route('/api/admin/users/<int:user_id>/modules', methods=['PUT'])
@admin_required
def update_user_module_permissions(user_id, current_user):
    """
    Set or update the module permissions for a user.
    Payload: {"module_ids": [1, 2]}
    Atomic replace inside transaction.
    """
    data = request.get_json() or {}
    raw_module_ids = data.get("module_ids", [])
    if not isinstance(raw_module_ids, list):
        return jsonify({"success": False, "error": "module_ids must be a list of integers"}), 400

    # Deduplicate and convert to integer
    clean_module_ids = []
    for mid in raw_module_ids:
        try:
            clean_module_ids.append(int(mid))
        except (ValueError, TypeError):
            pass
    clean_module_ids = list(set(clean_module_ids))

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Ensure user exists
        cur.execute("SELECT user_id, user_name FROM user_master WHERE user_id = %s;", (user_id,))
        target_user = cur.fetchone()
        if not target_user:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "User not found"}), 404

        # Validate that module_ids exist, are active, and are NOT the admin module
        valid_module_ids = []
        if clean_module_ids:
            cur.execute("""
                SELECT id FROM module_master
                WHERE id = ANY(%s)
                  AND is_active = TRUE
                  AND COALESCE(module_code, '') != 'admin'
                  AND LOWER(module_name) != 'admin';
            """, (clean_module_ids,))
            valid_module_ids = [r[0] for r in cur.fetchall()]

        # Clear existing permissions for this user
        cur.execute("DELETE FROM user_module_permission WHERE user_id = %s;", (user_id,))

        # Insert new allowed permissions
        for mid in valid_module_ids:
            cur.execute("""
                INSERT INTO user_module_permission (user_id, module_id, created_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, module_id) DO NOTHING;
            """, (user_id, mid))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Permissions updated successfully for user '{target_user[1]}'.",
            "user_id": user_id,
            "assigned_module_ids": valid_module_ids
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500