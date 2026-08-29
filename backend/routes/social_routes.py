import json
from flask import Blueprint, request, jsonify
from utils.helpers import token_required
from services.upload_service import (
    validate_and_save_upload,
    create_social_content_record,
    cleanup_content_media,
    cleanup_expired_and_orphan_files,
    safe_delete_temp_file,
    parse_strict_bool
)

social_blueprint = Blueprint("social", __name__, url_prefix="/api/social-media")

@social_blueprint.route("/upload", methods=["POST"])
@token_required
def upload_video_endpoint(current_user):
    """
    Secure temporary upload endpoint:
    - JWT-protected; extracts user_id strictly from verified token.
    - Streams video into temp_uploads, validates magic bytes, MIME, and container structure.
    - Atomically cleans up files on any validation or database error.
    - Returns sanitized metadata without exposing internal filesystem details.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    if "video" not in request.files:
        return jsonify({"success": False, "error": "No video file provided in request."}), 400
    
    video_file = request.files["video"]
    if not video_file.filename:
        return jsonify({"success": False, "error": "Selected video file is empty."}), 400
    
    title = request.form.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "error": "Post title is required."}), 400
    
    common_caption = request.form.get("common_caption", "")
    hashtags = request.form.get("hashtags", "")
    original_timezone = request.form.get("original_timezone", "UTC")
    
    # Parse platforms if provided
    platforms_raw = request.form.get("platforms")
    platforms = []
    if platforms_raw:
        try:
            platforms = json.loads(platforms_raw)
            if not isinstance(platforms, list):
                return jsonify({"success": False, "error": "Platforms must be a JSON list of objects."}), 400
        except Exception:
            return jsonify({"success": False, "error": "Invalid platforms JSON format."}), 400
    
    media_meta = None
    thumbnail_meta = None
    try:
        # 1. Validate and save video atomically
        media_meta = validate_and_save_upload(video_file, user_id, is_thumbnail=False)
        
        # 2. Validate and save optional thumbnail if provided
        if "thumbnail" in request.files and request.files["thumbnail"].filename:
            thumbnail_meta = validate_and_save_upload(request.files["thumbnail"], user_id, is_thumbnail=True)
        
        # 3. Persist database record (rolls back and deletes files on failure)
        content_record = create_social_content_record(
            user_id=user_id,
            title=title,
            common_caption=common_caption,
            hashtags=hashtags,
            media_meta=media_meta,
            thumbnail_meta=thumbnail_meta,
            platforms=platforms,
            original_timezone=original_timezone
        )
        
        return jsonify({
            "success": True,
            "message": "Video temporarily uploaded successfully.",
            "data": content_record
        }), 201
        
    except ValueError as e:
        # Clean up any saved files if error occurred after video save
        if media_meta and media_meta.get("media_filename"):
            safe_delete_temp_file(media_meta["media_filename"])
        if thumbnail_meta and thumbnail_meta.get("media_filename"):
            safe_delete_temp_file(thumbnail_meta["media_filename"])
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        if media_meta and media_meta.get("media_filename"):
            safe_delete_temp_file(media_meta["media_filename"])
        if thumbnail_meta and thumbnail_meta.get("media_filename"):
            safe_delete_temp_file(thumbnail_meta["media_filename"])
        return jsonify({"success": False, "error": "Failed to process upload. Please check your file and try again."}), 500

@social_blueprint.route("/cleanup/<int:content_id>", methods=["POST"])
@token_required
def cleanup_media_endpoint(current_user, content_id):
    """
    Secure manual/platform cleanup endpoint:
    - JWT-protected; validates ownership before deletion.
    - Idempotent: repeated calls succeed without error.
    - Strict boolean validation for 'force'.
    - Never deletes original files from user's machine.
    """
    user_id = current_user.get("user_id")
    data = request.get_json(silent=True) or {}
    force = parse_strict_bool(data.get("force", False))
    
    result = cleanup_content_media(content_id=content_id, user_id=user_id, force=force)
    
    if not result.get("success") and "not found" in result.get("message", "").lower():
        return jsonify(result), 404
        
    return jsonify(result), 200

@social_blueprint.route("/cleanup-expired", methods=["POST"])
@token_required
def cleanup_expired_endpoint(current_user):
    """
    Admin-only sweeper endpoint to trigger expired & orphan temporary file purging.
    Non-admin authenticated users are rejected with 403 Forbidden.
    """
    username = current_user.get("username", "")
    user_id = current_user.get("user_id")
    
    # Check if user is admin (user_id == 1 or username == 'admin')
    if user_id != 1 and username.lower() != "admin":
        return jsonify({
            "success": False,
            "error": "Access denied. Admin privileges are required to trigger global maintenance cleanup."
        }), 403
    
    result = cleanup_expired_and_orphan_files()
    return jsonify({
        "success": True,
        "message": "Expired and orphan temporary file sweep completed.",
        "data": result
    }), 200
