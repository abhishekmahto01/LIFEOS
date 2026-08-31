"""
LifeOS — Unified Multi-Platform Publishing Orchestrator (Stage 8)
Coordinates publishing of a single social_content record across multiple platforms (YouTube, Instagram).
Key Principles:
1. Modular platform dispatchers delegating to dedicated domain publishing services.
2. Independent failure isolation: one platform's failure never aborts or rolls back another.
3. Shared temporary media retention: source video is preserved on disk for all targets.
4. Idempotency & already-published protection: re-invoking skips published platforms and retries failed ones.
5. Strict target validation: rejects duplicate targets, unknown platforms, and cross-user accounts.
6. Overall status aggregation: updates social_content.overall_status accurately.
7. Zero-token and zero-secret exposure across all responses and logs.
"""

import os
import datetime
from config import Config
from database.db import get_connection
from services.upload_service import get_safe_temp_path
from services.youtube_publish_service import publish_youtube
from services.instagram_publish_service import (
    publish_instagram_reel,
    recalculate_content_overall_status
)

SUPPORTED_PLATFORMS = {"YOUTUBE", "INSTAGRAM"}
MAX_PLATFORM_TARGETS = 5


# =============================================================================
# 1. Platform Dispatchers
# =============================================================================

def _dispatch_youtube_publish(user_id: int, content_id: int, account_id: int, options: dict = None) -> dict:
    """
    Dispatches publishing to YouTube domain publisher.
    """
    try:
        res = publish_youtube(
            user_id=user_id,
            content_id=content_id,
            account_id=account_id,
            options=options or {},
            defer_media_cleanup=True
        )
        return {
            "platform": "YOUTUBE",
            "account_id": account_id,
            "success": res.get("success", False),
            "publish_status": res.get("publish_status", "FAILED"),
            "publish_id": res.get("publish_id"),
            "publish_url": res.get("publish_url"),
            "already_published": res.get("already_published", False),
            "error": res.get("error")
        }
    except Exception as e:
        return {
            "platform": "YOUTUBE",
            "account_id": account_id,
            "success": False,
            "publish_status": "FAILED",
            "already_published": False,
            "error": str(e)
        }


def _dispatch_instagram_publish(user_id: int, content_id: int, account_id: int, options: dict = None) -> dict:
    """
    Dispatches publishing to Instagram domain publisher.
    """
    try:
        custom_video_url = options.get("video_url") or options.get("custom_video_url") if options else None
        res = publish_instagram_reel(
            user_id=user_id,
            content_id=content_id,
            account_id=account_id,
            custom_video_url=custom_video_url
        )
        return {
            "platform": "INSTAGRAM",
            "account_id": account_id,
            "success": res.get("success", False),
            "publish_status": res.get("publish_status", "FAILED"),
            "publish_id": res.get("publish_id"),
            "publish_url": res.get("publish_url"),
            "already_published": res.get("already_published", False),
            "retry_allowed": res.get("retry_allowed", True),
            "error": res.get("error")
        }
    except Exception as e:
        return {
            "platform": "INSTAGRAM",
            "account_id": account_id,
            "success": False,
            "publish_status": "FAILED",
            "already_published": False,
            "error": str(e)
        }


PLATFORM_DISPATCHERS = {
    "YOUTUBE": _dispatch_youtube_publish,
    "INSTAGRAM": _dispatch_instagram_publish,
}


# =============================================================================
# 2. Master Unified Publishing Orchestrator
# =============================================================================

def publish_content_to_platforms(
    user_id: int,
    content_id: int,
    platform_targets: list
) -> dict:
    """
    Orchestrates multi-platform publishing for a content item:
    1. Validates content existence, ownership, and unexpired media.
    2. Validates targets structure, bounds, supported platforms, and account ownership.
    3. Sequentially dispatches to platform publishers with failure isolation.
    4. Recalculates master overall_status.
    5. Returns unified sanitized response.
    """
    # 1. Basic user and content ID validation
    if not user_id:
        return {"success": False, "error": "User authentication required.", "status_code": 401}
    if not content_id or not isinstance(content_id, int) or content_id <= 0:
        return {"success": False, "error": "Valid content ID is required.", "status_code": 400}

    # 2. Targets structure validation
    if not platform_targets or not isinstance(platform_targets, list):
        return {"success": False, "error": "Targets list is required and cannot be empty.", "status_code": 400}
    if len(platform_targets) > MAX_PLATFORM_TARGETS:
        return {"success": False, "error": f"Maximum of {MAX_PLATFORM_TARGETS} targets allowed per request.", "status_code": 400}

    # 3. Global content ownership & media verification
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, user_id, temp_media_path, temp_file_deleted, temp_file_expires_at
            FROM social_content
            WHERE id = %s AND user_id = %s;
        """, (content_id, user_id))
        c_row = cur.fetchone()

        if not c_row:
            return {"success": False, "error": "Content item not found or access denied.", "status_code": 404}

        cid, c_uid, temp_media_path, temp_deleted, expires_at = c_row

        if temp_deleted or not temp_media_path:
            return {"success": False, "error": "Temporary video file has been deleted or purged. Please re-upload.", "status_code": 410}

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return {"success": False, "error": "Temporary video file has expired. Please re-upload.", "status_code": 410}

        safe_path = get_safe_temp_path(temp_media_path)
        if not safe_path or not os.path.exists(safe_path):
            return {"success": False, "error": "Local temporary video media not found on disk. Please re-upload.", "status_code": 410}

        # 4. Target Items Validation & Account Ownership Checks
        validated_targets = []
        seen_targets = set()

        for idx, t in enumerate(platform_targets):
            if not isinstance(t, dict):
                return {"success": False, "error": f"Target at index {idx} must be a JSON object.", "status_code": 400}

            raw_plat = t.get("platform")
            if not raw_plat or not isinstance(raw_plat, str):
                return {"success": False, "error": f"Platform is required for target at index {idx}.", "status_code": 400}

            platform = raw_plat.strip().upper()
            if platform not in SUPPORTED_PLATFORMS:
                return {
                    "success": False,
                    "error": f"Unsupported platform '{platform}'. Supported platforms: {', '.join(sorted(SUPPORTED_PLATFORMS))}.",
                    "status_code": 400
                }

            acc_id = t.get("account_id")
            if acc_id is None or not isinstance(acc_id, int) or acc_id <= 0:
                return {"success": False, "error": f"Valid account_id required for target at index {idx}.", "status_code": 400}

            # Deduplication: Reject exact duplicate (platform, account_id) in same request
            target_key = (platform, acc_id)
            if target_key in seen_targets:
                return {"success": False, "error": f"Duplicate target specified for {platform} account {acc_id}.", "status_code": 400}
            seen_targets.add(target_key)

            # Validate account ownership and platform match
            cur.execute("""
                SELECT id, user_id, platform, connection_status
                FROM social_accounts
                WHERE id = %s AND user_id = %s;
            """, (acc_id, user_id))
            acc_row = cur.fetchone()

            if not acc_row:
                return {"success": False, "error": f"Account ID {acc_id} not found or access denied.", "status_code": 404}

            aid, a_uid, acc_plat, conn_status = acc_row
            if acc_plat != platform:
                return {
                    "success": False,
                    "error": f"Account ID {acc_id} is for {acc_plat}, but target requested {platform}.",
                    "status_code": 400
                }

            options = t.get("options") or {}
            validated_targets.append({
                "platform": platform,
                "account_id": acc_id,
                "options": options
            })

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # 5. Independent Sequential Platform Dispatching (Failure Isolation)
    results = []

    for target in validated_targets:
        plat = target["platform"]
        acc_id = target["account_id"]
        options = target["options"]

        dispatcher = PLATFORM_DISPATCHERS.get(plat)
        if dispatcher:
            res = dispatcher(user_id=user_id, content_id=content_id, account_id=acc_id, options=options)
            results.append(res)
        else:
            results.append({
                "platform": plat,
                "account_id": acc_id,
                "success": False,
                "publish_status": "FAILED",
                "error": f"No dispatcher found for platform {plat}."
            })

    # 6. Recalculate Master Content Overall Status
    recalculate_content_overall_status(content_id)

    # 7. Query fresh master overall status
    overall_status = "FAILED"
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT overall_status FROM social_content WHERE id = %s;", (content_id,))
        row = cur.fetchone()
        if row:
            overall_status = row[0]
    except Exception:
        pass
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Determine unified success
    all_success = all(r.get("publish_status") == "PUBLISHED" for r in results)

    return {
        "success": all_success,
        "content_id": content_id,
        "overall_status": overall_status,
        "results": results,
        "status_code": 200
    }
