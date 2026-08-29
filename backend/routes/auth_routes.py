from flask import Blueprint, request, jsonify
from services.auth_service import authenticate_user, change_user_password
from utils.helpers import token_required

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/api/auth/login', methods=['POST'])
@auth_blueprint.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')

    response, status = authenticate_user(username, password)
    return jsonify(response), status

@auth_blueprint.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user_profile(current_user):
    return jsonify({
        "success": True,
        "user": current_user
    }), 200

@auth_blueprint.route('/api/auth/change-password', methods=['POST'])
@auth_blueprint.route('/api/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    # Always use the authenticated user's ID from the verified JWT
    user_id = current_user['user_id']

    response, status = change_user_password(user_id, old_password, new_password)
    return jsonify(response), status
