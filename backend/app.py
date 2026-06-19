from flask import Flask, request, jsonify
from flask_cors import CORS
from database.db import get_connection

from routes.user_routes import user_blueprint
from routes.dashboard_routes import dashboard_bp

app = Flask(__name__)
CORS(app)

# Blueprints
app.register_blueprint(user_blueprint)
app.register_blueprint(dashboard_bp)


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Username/password required"
        }), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            user_id,
            user_name,
            password,
            is_active
        FROM user_master
        WHERE user_name = %s
        """,
        (username,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    if user is None:
        return jsonify({
            "success": False,
            "message": "Invalid username or password"
        }), 401

    user_id, db_username, db_password, is_active = user

    if not is_active:
        return jsonify({
            "success": False,
            "message": "Account inactive"
        }), 403

    if password != db_password:
        return jsonify({
            "success": False,
            "message": "Invalid username or password"
        }), 401

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "user_id": user_id,
            "username": db_username
        }
    }), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)