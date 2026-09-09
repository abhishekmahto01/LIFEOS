from flask import Blueprint, jsonify
from utils.helpers import token_required, get_user_allowed_modules, is_admin_user

dashboard_bp = Blueprint("dashboard_bp", __name__)

@dashboard_bp.route("/api/me/modules", methods=["GET"])
@token_required
def get_current_user_modules(current_user):
    """
    Returns the list of active modules the currently authenticated user is permitted to access.
    Admin automatically receives all active modules.
    Normal users receive only explicitly assigned active modules.
    """
    modules = get_user_allowed_modules(
        user_id=current_user["user_id"],
        username=current_user.get("username")
    )
    return jsonify({
        "success": True,
        "modules": modules
    }), 200

@dashboard_bp.route("/api/dashboard/modules", methods=["GET"])
@dashboard_bp.route("/api/dashboard/modules/<int:user_id>", methods=["GET"])
@token_required
def get_user_modules(current_user, user_id=None):
    """
    Backward-compatible module listing endpoint for dashboard.
    """
    # If a specific user_id is requested, allow only if caller is admin or requesting own ID
    if user_id is not None and not is_admin_user(current_user) and user_id != current_user["user_id"]:
        return jsonify({
            "success": False,
            "error": "You do not have access to view another user's modules."
        }), 403

    target_user_id = current_user['user_id'] if user_id is None else user_id
    target_username = current_user.get('username') if user_id is None or user_id == current_user['user_id'] else None

    modules = get_user_allowed_modules(
        user_id=target_user_id,
        username=target_username
    )
    return jsonify(modules), 200