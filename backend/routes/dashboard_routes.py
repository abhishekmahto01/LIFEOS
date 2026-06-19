from flask import Blueprint, jsonify
from database.db import get_connection

dashboard_bp = Blueprint("dashboard_bp", __name__)


@dashboard_bp.route("/api/dashboard/modules/<int:user_id>", methods=["GET"])
def get_user_modules(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            m.id,
            m.module_name,
            m.route,
            m.sequence_no
        FROM user_module_permission p
        JOIN module_master m
            ON p.module_id = m.id
        WHERE p.user_id = %s
          AND m.is_active = TRUE
        ORDER BY m.sequence_no
    """, (user_id,))

    rows = cur.fetchall()

    modules = []

    for row in rows:
        modules.append({
            "id": row[0],
            "module_name": row[1],
            "route": row[2],
            "sequence_no": row[3]
        })

    cur.close()
    conn.close()

    return jsonify(modules)