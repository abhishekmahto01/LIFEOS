"""
LifeOS — Facebook Page Video Publishing Service

Publishes an uploaded social_content video to a connected Facebook Page.

Unlike Instagram (which must download the video from a public URL), Facebook
accepts a direct multipart upload, so no tunnel / INSTAGRAM_MEDIA_BASE_URL is
needed. Slot claiming, retry limits, audit attempts and status recording reuse
the shared Meta machinery in instagram_publish_service.
"""

import os
import re
import time
import datetime
import requests

from config import Config
from services.upload_service import get_safe_temp_path
from services.instagram_publish_service import (
    claim_instagram_publish_slot,
    format_instagram_caption,
    _record_publish_success,
    _record_publish_failure,
    _update_platform_processing_status,
)

FACEBOOK_VIDEO_TITLE_MAX = 255
_TOKEN_PATTERN = re.compile(r"(access_token|EAA)[a-zA-Z0-9_=-]+")


def _graph_video_base() -> str:
    # Video uploads go to the graph-video host; everything else to graph.facebook.com.
    return Config.META_GRAPH_API_BASE_URL.replace("://graph.", "://graph-video.", 1)


def _meta_error_message(resp) -> str:
    try:
        err = resp.json().get("error", {})
        msg = err.get("error_user_msg") or err.get("message") or f"HTTP {resp.status_code}"
    except Exception:
        msg = f"HTTP {resp.status_code}"
    return _TOKEN_PATTERN.sub("[REDACTED]", str(msg))


def upload_facebook_page_video(page_id: str, access_token: str, file_path: str,
                               title: str = "", description: str = "") -> str:
    """Upload a video file to a Facebook Page. Returns the new video ID or raises RuntimeError."""
    endpoint = f"{_graph_video_base()}/{Config.META_GRAPH_API_VERSION}/{page_id}/videos"
    data = {
        "access_token": access_token,
        "title": (title or "")[:FACEBOOK_VIDEO_TITLE_MAX],
        "description": description or "",
        "published": "true",
    }
    with open(file_path, "rb") as fh:
        files = {"source": (os.path.basename(file_path), fh, "video/mp4")}
        resp = requests.post(endpoint, data=data, files=files, timeout=(15, 600))

    if resp.status_code != 200:
        raise RuntimeError(f"Facebook video upload failed: {_meta_error_message(resp)}")

    video_id = (resp.json() or {}).get("id")
    if not video_id:
        raise RuntimeError("Facebook video upload returned no video ID.")
    return str(video_id)


def get_facebook_video_permalink(page_id: str, video_id: str, access_token: str) -> str:
    """Best-effort permalink lookup; falls back to the canonical Page video URL."""
    fallback = f"https://www.facebook.com/{page_id}/videos/{video_id}/"
    try:
        resp = requests.get(
            f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/{video_id}",
            params={"fields": "permalink_url", "access_token": access_token},
            timeout=15,
        )
        if resp.status_code == 200:
            link = (resp.json() or {}).get("permalink_url")
            if link:
                return link if link.startswith("http") else f"https://www.facebook.com{link}"
    except Exception:
        pass
    return fallback


def publish_facebook_video(user_id: int, content_id: int, account_id: int, is_retry: bool = False) -> dict:
    """
    Publish a content record's video to a connected Facebook Page with the same
    idempotency guarantees as Instagram: already-published returns the existing
    post, an active attempt returns 409, and retries are capped.
    """
    if not user_id:
        return {"success": False, "error": "User authentication required.", "status_code": 401}
    if not content_id or not isinstance(content_id, int) or content_id <= 0:
        return {"success": False, "error": "Valid content ID is required.", "status_code": 400}
    if not account_id or not isinstance(account_id, int) or account_id <= 0:
        return {"success": False, "error": "Valid Facebook Page account ID is required.", "status_code": 400}

    claim = claim_instagram_publish_slot(
        user_id=user_id,
        content_id=content_id,
        account_id=account_id,
        is_retry=is_retry,
        platform="FACEBOOK",
    )
    if not claim.get("claimed"):
        return claim

    scp_id = claim["scp_id"]
    attempt_id = claim["attempt_id"]
    page_id = claim["ig_user_id"]  # platform_account_id of the FACEBOOK row = Page ID
    access_token = claim["access_token"]
    start_time = time.time()

    safe_path = get_safe_temp_path(claim["temp_media_path"])
    if not safe_path or not os.path.exists(safe_path):
        _record_publish_failure(scp_id, attempt_id, content_id,
                                "Local temporary video media not found on disk. Please re-upload.", start_time)
        return {"success": False, "error": "Local temporary video media not found on disk. Please re-upload.",
                "publish_status": "FAILED", "status_code": 410}

    description = format_instagram_caption(
        title="", description=claim.get("description") or "", hashtags=claim.get("tags") or ""
    )

    try:
        _update_platform_processing_status(scp_id, "UPLOADING")
        video_id = upload_facebook_page_video(
            page_id=page_id,
            access_token=access_token,
            file_path=safe_path,
            title=claim.get("title") or "",
            description=description,
        )
    except Exception as e:
        clean_err = _TOKEN_PATTERN.sub("[REDACTED]", str(e))
        _record_publish_failure(scp_id, attempt_id, content_id, clean_err, start_time)
        return {"success": False, "error": clean_err, "publish_status": "FAILED", "status_code": 400}

    permalink = get_facebook_video_permalink(page_id, video_id, access_token)
    duration_ms = int((time.time() - start_time) * 1000)
    _record_publish_success(scp_id, attempt_id, content_id, video_id, permalink, duration_ms)

    return {
        "success": True,
        "platform": "FACEBOOK",
        "content_id": content_id,
        "account_id": account_id,
        "publish_status": "PUBLISHED",
        "publish_id": video_id,
        "publish_url": permalink,
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status_code": 200,
    }
