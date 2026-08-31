"""
LifeOS — Social Media Hub Route Handlers (Thin Layer)
Responsible only for:
- JWT Authentication & Ownership validation
- Strict input parsing and validation
- Delegating to domain service functions
- Returning sanitized JSON responses with HTTP status codes
"""

import os
import json
import datetime
import urllib.parse
from flask import Blueprint, request, jsonify, redirect, send_file

from config import Config
from database.db import get_connection
from utils.helpers import token_required
from services.upload_service import (
    validate_and_save_upload,
    create_social_content_record,
    cleanup_content_media,
    cleanup_expired_and_orphan_files,
    safe_delete_temp_file,
    get_safe_temp_path,
    parse_strict_bool
)
from services.youtube_oauth_service import (
    get_youtube_authorization_url,
    handle_youtube_oauth_callback,
    get_user_social_accounts,
    disconnect_social_account
)
from services.instagram_oauth_service import (
    get_instagram_authorization_url,
    handle_instagram_oauth_callback
)
from services.youtube_publish_service import (
    start_youtube_publish_task
)
from services.instagram_publish_service import (
    publish_instagram_reel
)
from services.social_publish_service import (
    publish_content_to_platforms
)
from services.social_post_service import (
    get_user_post_history,
    get_user_dashboard_summary,
    get_content_status_detail
)

social_blueprint = Blueprint("social", __name__, url_prefix="/api/social-media")

VALID_PRIVACIES = {"PRIVATE", "UNLISTED", "PUBLIC"}


# =============================================================================
# 1. YouTube OAuth 2.0 Connection Routes
# =============================================================================

@social_blueprint.route("/connect/youtube", methods=["GET"])
@token_required
def connect_youtube_endpoint(current_user):
    """
    Generate Google OAuth 2.0 authorization URL for YouTube connection.
    - Generates and stores single-use state tied to current_user.
    """
    user_id = current_user.get("user_id")
    try:
        res = get_youtube_authorization_url(user_id=user_id)
        return jsonify({
            "success": True,
            "authorization_url": res["authorization_url"]
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "Failed to initialize Google OAuth connection."}), 500


@social_blueprint.route("/oauth/youtube/callback", methods=["GET"])
def youtube_oauth_callback_endpoint():
    """
    Google OAuth 2.0 callback endpoint.
    - Verifies user identity exclusively from validated single-use state.
    - Redirects browser to Config.FRONTEND_URL with sanitized status parameters.
    """
    state = request.args.get("state")
    code = request.args.get("code")
    error = request.args.get("error")

    frontend_accounts_url = f"{Config.FRONTEND_URL}/social-media/accounts"

    try:
        status_code, data = handle_youtube_oauth_callback(raw_state=state, code=code, error=error)
        if status_code == "success" and data:
            channel_name = urllib.parse.quote(data.get("channel_title", "YouTube Channel"))
            return redirect(f"{frontend_accounts_url}?status=success&platform=youtube&channel={channel_name}")
        else:
            return redirect(f"{frontend_accounts_url}?status=error&code={status_code}")
    except Exception:
        return redirect(f"{frontend_accounts_url}?status=error&code=oauth_failed")


# =============================================================================
# 1B. Instagram & Meta OAuth 2.0 Connection Routes (Stage 6B)
# =============================================================================

@social_blueprint.route("/connect/instagram", methods=["GET"])
@token_required
def connect_instagram_endpoint(current_user):
    """
    Generate Meta OAuth 2.0 authorization URL for Instagram connection.
    - Generates and stores single-use state tied to current_user.
    """
    user_id = current_user.get("user_id")
    try:
        res = get_instagram_authorization_url(user_id=user_id)
        return jsonify({
            "success": True,
            "authorization_url": res["authorization_url"]
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "Failed to initialize Instagram OAuth connection."}), 500


@social_blueprint.route("/oauth/instagram/callback", methods=["GET"])
def instagram_oauth_callback_endpoint():
    """
    Meta OAuth 2.0 callback endpoint for Instagram.
    - Verifies user identity exclusively from validated single-use state.
    - Redirects browser to Config.FRONTEND_URL with sanitized status parameters.
    """
    state = request.args.get("state")
    code = request.args.get("code")
    error = request.args.get("error") or request.args.get("error_reason")

    frontend_accounts_url = f"{Config.FRONTEND_URL}/social-media/accounts"

    try:
        status_code, data = handle_instagram_oauth_callback(raw_state=state, code=code, error=error)
        if status_code == "success" and data:
            username = urllib.parse.quote(data.get("username", data.get("name", "Instagram Account")))
            return redirect(f"{frontend_accounts_url}?status=success&platform=instagram&channel={username}&instagram=connected")
        else:
            return redirect(f"{frontend_accounts_url}?status=error&code={status_code}&platform=instagram&instagram=error")
    except Exception:
        return redirect(f"{frontend_accounts_url}?status=error&code=oauth_failed&platform=instagram&instagram=error")



# =============================================================================
# 2. Social Accounts Management Routes
# =============================================================================

@social_blueprint.route("/accounts", methods=["GET"])
@token_required
def list_accounts_endpoint(current_user):
    """
    List connected social media accounts for the authenticated user.
    """
    user_id = current_user.get("user_id")
    try:
        accounts = get_user_social_accounts(user_id=user_id)
        return jsonify({
            "success": True,
            "accounts": accounts
        }), 200
    except Exception:
        return jsonify({"success": False, "error": "Failed to retrieve connected accounts."}), 500


@social_blueprint.route("/accounts/<int:account_id>", methods=["DELETE"])
@token_required
def disconnect_account_endpoint(current_user, account_id):
    """
    Disconnect a connected social media account.
    """
    user_id = current_user.get("user_id")
    try:
        res = disconnect_social_account(account_id=account_id, user_id=user_id)
        status_code = res.get("status_code", 200)
        return jsonify({
            "success": res.get("success", False),
            "message": res.get("message", "")
        }), status_code
    except Exception:
        return jsonify({"success": False, "error": "Failed to disconnect account."}), 500


# =============================================================================
# 3. Create Post & Resumable YouTube Publishing Routes
# =============================================================================

@social_blueprint.route("/upload", methods=["POST"])
@token_required
def upload_video_endpoint(current_user):
    """
    Secure temporary upload and post creation endpoint.
    - Validates file, MIME, signature, and metadata constraints.
    - If publish_now=true, automatically triggers background YouTube publishing task.
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

    if len(title) > 100:
        return jsonify({"success": False, "error": f"Post title exceeds YouTube limit of 100 characters (length: {len(title)})."}), 400

    common_caption = request.form.get("common_caption", "")
    if len(common_caption) > 5000:
        return jsonify({"success": False, "error": "Post description exceeds YouTube limit of 5000 characters."}), 400

    hashtags = request.form.get("hashtags", "")
    original_timezone = request.form.get("original_timezone", "UTC")

    privacy_raw = request.form.get("privacy_status", "PRIVATE").strip().upper()
    if privacy_raw not in VALID_PRIVACIES:
        return jsonify({"success": False, "error": f"Invalid privacy status '{privacy_raw}'. Allowed: PRIVATE, UNLISTED, PUBLIC."}), 400
    privacy_status = privacy_raw

    made_for_kids = parse_strict_bool(request.form.get("made_for_kids", False))
    publish_now = parse_strict_bool(request.form.get("publish_now", True))
    category_id = request.form.get("category_id", "22").strip()

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

        # 3. Persist database record
        content_record = create_social_content_record(
            user_id=user_id,
            title=title,
            common_caption=common_caption,
            hashtags=hashtags,
            media_meta=media_meta,
            thumbnail_meta=thumbnail_meta,
            platforms=platforms,
            original_timezone=original_timezone,
            privacy_status=privacy_status,
            made_for_kids=made_for_kids,
            category_id=category_id
        )

        content_id = content_record["content_id"]

        # 4. If publish_now requested and YouTube target exists, launch background publishing task
        has_youtube = any(p.get("platform") == "YOUTUBE" for p in content_record.get("platforms", []))
        if publish_now and has_youtube:
            start_youtube_publish_task(content_id=content_id, user_id=user_id)

        return jsonify({
            "success": True,
            "message": "Video temporarily uploaded successfully.",
            "data": content_record
        }), 201

    except ValueError as e:
        if media_meta and media_meta.get("media_filename"):
            safe_delete_temp_file(media_meta["media_filename"])
        if thumbnail_meta and thumbnail_meta.get("media_filename"):
            safe_delete_temp_file(thumbnail_meta["media_filename"])
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        if media_meta and media_meta.get("media_filename"):
            safe_delete_temp_file(media_meta["media_filename"])
        if thumbnail_meta and thumbnail_meta.get("media_filename"):
            safe_delete_temp_file(thumbnail_meta["media_filename"])
        return jsonify({"success": False, "error": "Failed to process upload. Please check your file and try again."}), 500


@social_blueprint.route("/content/<int:content_id>/publish/youtube", methods=["POST"])
@token_required
def trigger_youtube_publish_endpoint(current_user, content_id):
    """
    Explicitly trigger or restart YouTube resumable publication for a content record.
    """
    user_id = current_user.get("user_id")
    status_detail = get_content_status_detail(content_id=content_id, user_id=user_id)
    if not status_detail.get("success"):
        return jsonify(status_detail), status_detail.get("status_code", 400)

    start_youtube_publish_task(content_id=content_id, user_id=user_id)
    return jsonify({
        "success": True,
        "message": "YouTube publication task started.",
        "content_id": content_id
    }), 200


@social_blueprint.route("/content/<int:content_id>/status", methods=["GET"])
@token_required
def get_content_status_endpoint(current_user, content_id):
    """
    Retrieve real-time publication progress and processing state for a post.
    """
    user_id = current_user.get("user_id")
    status_detail = get_content_status_detail(content_id=content_id, user_id=user_id)
    status_code = status_detail.pop("status_code", 200)
    return jsonify(status_detail), status_code


@social_blueprint.route("/content/<int:content_id>/retry/youtube", methods=["POST"])
@token_required
def retry_youtube_publish_endpoint(current_user, content_id):
    """
    Retry a failed YouTube publication. Resumes from offset or restarts session safely.
    Checks temp file expiration before re-queuing.
    """
    user_id = current_user.get("user_id")
    status_detail = get_content_status_detail(content_id=content_id, user_id=user_id)
    if not status_detail.get("success"):
        return jsonify(status_detail), status_detail.get("status_code", 400)

    if not status_detail.get("media_valid_for_retry"):
        return jsonify({
            "success": False,
            "error": "MEDIA_EXPIRED",
            "message": "Temporary video media has expired or been purged. Please re-upload the video."
        }), 410

    start_youtube_publish_task(content_id=content_id, user_id=user_id)
    return jsonify({
        "success": True,
        "message": "YouTube publication retry initiated.",
        "content_id": content_id,
        "retry_type": status_detail.get("retry_type", "FULL_VIDEO")
    }), 200


# =============================================================================
# 3B. Unified Multi-Platform Publishing Routes (Stage 8)
# =============================================================================

@social_blueprint.route("/publish", methods=["POST"])
@token_required
def unified_publish_endpoint(current_user):
    """
    Unified multi-platform publishing endpoint (Stage 8).
    Accepts JSON body:
    {
        "content_id": 123,
        "targets": [
            {"platform": "YOUTUBE", "account_id": 10, "options": {"privacy_status": "PUBLIC"}},
            {"platform": "INSTAGRAM", "account_id": 12}
        ]
    }
    """
    user_id = current_user.get("user_id")
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    targets = data.get("targets")
    if targets is None:
        targets = data.get("platform_targets")

    if content_id is None:
        return jsonify({"success": False, "error": "content_id is required."}), 400
    if not isinstance(content_id, int) or content_id <= 0:
        return jsonify({"success": False, "error": "content_id must be a positive integer."}), 400

    if targets is None:
        return jsonify({"success": False, "error": "targets list is required."}), 400
    if not isinstance(targets, list) or len(targets) == 0:
        return jsonify({"success": False, "error": "targets list cannot be empty."}), 400

    res = publish_content_to_platforms(
        user_id=user_id,
        content_id=content_id,
        platform_targets=targets
    )
    status_code = res.pop("status_code", 200 if res.get("success") else 400)
    return jsonify(res), status_code


# =============================================================================
# 3C. Instagram Reel Publishing Routes (Stage 7A & 7B)
# =============================================================================

@social_blueprint.route("/publish/instagram", methods=["POST"])
@token_required
def publish_instagram_endpoint(current_user):
    """
    Publish an uploaded video to Instagram as a Reel.
    Requires JSON body: {"content_id": 123, "account_id": 45}
    """
    user_id = current_user.get("user_id")
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    account_id = data.get("account_id")
    custom_video_url = data.get("video_url") or data.get("custom_video_url")

    if content_id is None:
        return jsonify({"success": False, "error": "content_id is required."}), 400
    if not isinstance(content_id, int) or content_id <= 0:
        return jsonify({"success": False, "error": "content_id must be a positive integer."}), 400

    if account_id is None:
        return jsonify({"success": False, "error": "account_id is required."}), 400
    if not isinstance(account_id, int) or account_id <= 0:
        return jsonify({"success": False, "error": "account_id must be a positive integer."}), 400

    res = publish_instagram_reel(
        user_id=user_id,
        content_id=content_id,
        account_id=account_id,
        custom_video_url=custom_video_url
    )
    status_code = res.pop("status_code", 200 if res.get("success") else 400)
    return jsonify(res), status_code


@social_blueprint.route("/content/<int:content_id>/publish/instagram", methods=["POST"])
@token_required
def publish_instagram_content_endpoint(current_user, content_id):
    """
    Publish a specific content record to Instagram.
    Requires JSON body: {"account_id": 45}
    """
    user_id = current_user.get("user_id")
    data = request.get_json(silent=True) or {}
    account_id = data.get("account_id")
    custom_video_url = data.get("video_url") or data.get("custom_video_url")

    if account_id is None:
        return jsonify({"success": False, "error": "account_id is required."}), 400
    if not isinstance(account_id, int) or account_id <= 0:
        return jsonify({"success": False, "error": "account_id must be a positive integer."}), 400

    res = publish_instagram_reel(
        user_id=user_id,
        content_id=content_id,
        account_id=account_id,
        custom_video_url=custom_video_url
    )
    status_code = res.pop("status_code", 200 if res.get("success") else 400)
    return jsonify(res), status_code


@social_blueprint.route("/content/<int:content_id>/retry/instagram", methods=["POST"])
@token_required
def retry_instagram_publish_endpoint(current_user, content_id):
    """
    Retry a failed Instagram publication.
    Validates user ownership and temp media validity before re-trying.
    """
    user_id = current_user.get("user_id")
    data = request.get_json(silent=True) or {}
    account_id = data.get("account_id")
    custom_video_url = data.get("video_url") or data.get("custom_video_url")

    # If account_id not provided, find from existing social_content_platforms row
    if not account_id:
        conn = None
        cur = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT account_id, platform_status
                FROM social_content_platforms
                WHERE content_id = %s AND platform = 'INSTAGRAM';
            """, (content_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"success": False, "error": "No Instagram publication target found for this content."}), 404
            account_id = row[0]
            p_status = row[1]
            if p_status == "PUBLISHED":
                return jsonify({"success": True, "message": "Instagram post is already published.", "already_published": True}), 200
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    status_detail = get_content_status_detail(content_id=content_id, user_id=user_id)
    if not status_detail.get("success"):
        return jsonify(status_detail), status_detail.get("status_code", 400)

    if not status_detail.get("media_valid_for_retry"):
        return jsonify({
            "success": False,
            "error": "MEDIA_EXPIRED",
            "message": "Temporary video media has expired or been purged. Please re-upload the video."
        }), 410

    res = publish_instagram_reel(
        user_id=user_id,
        content_id=content_id,
        account_id=account_id,
        custom_video_url=custom_video_url,
        is_retry=True
    )
    status_code = res.pop("status_code", 200 if res.get("success") else 400)
    return jsonify(res), status_code



@social_blueprint.route("/public-media/<int:content_id>/<filename>", methods=["GET"])
def stream_public_media_endpoint(content_id, filename):
    """
    Public media streaming endpoint for Meta Instagram Reel ingestion.
    Validates content_id, filename, unexpired TTL, and streams file with range headers.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT temp_media_path, temp_file_deleted, temp_file_expires_at
            FROM social_content
            WHERE id = %s;
        """, (content_id,))
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Media not found."}), 404

        temp_media_path, temp_deleted, expires_at = row

        if temp_deleted or not temp_media_path:
            return jsonify({"error": "Media file has been deleted or purged."}), 410

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return jsonify({"error": "Media file has expired."}), 410

        expected_filename = os.path.basename(temp_media_path)
        if filename != expected_filename:
            return jsonify({"error": "Invalid media filename."}), 404

        safe_path = get_safe_temp_path(temp_media_path)
        if not safe_path or not os.path.exists(safe_path):
            return jsonify({"error": "Media file not found on disk."}), 404

        return send_file(safe_path, mimetype="video/mp4", conditional=True)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# =============================================================================
# 4. Post History & Dashboard Routes
# =============================================================================

@social_blueprint.route("/history", methods=["GET"])
@token_required
def get_post_history_endpoint(current_user):
    """
    Retrieve user post history with platform details, video IDs, statuses, and watch URLs.
    """
    user_id = current_user.get("user_id")
    status_filter = request.args.get("status")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    result = get_user_post_history(user_id=user_id, status_filter=status_filter, page=page, limit=limit)
    return jsonify(result), 200


@social_blueprint.route("/dashboard", methods=["GET"])
@token_required
def get_dashboard_summary_endpoint(current_user):
    """
    Retrieve real KPI metrics and recent post summaries for the authenticated user.
    """
    user_id = current_user.get("user_id")
    result = get_user_dashboard_summary(user_id=user_id)
    return jsonify(result), 200


# =============================================================================
# 5. Cleanup & Maintenance Routes
# =============================================================================

@social_blueprint.route("/cleanup/<int:content_id>", methods=["POST"])
@token_required
def cleanup_media_endpoint(current_user, content_id):
    """
    Secure manual/platform cleanup endpoint.
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
    """
    username = current_user.get("username", "")
    user_id = current_user.get("user_id")

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
