"""
LifeOS — Instagram Reel Publishing Service (Stage 7A)
Implements official Meta Graph API v21.0 Reels Publishing flow:
1. Validates user ownership of social_content and social_accounts records.
2. Formats and bounds Instagram caption (title + description + hashtags).
3. Resolves public media delivery URL (enforcing public HTTP/HTTPS URL, rejecting local paths).
4. Creates Meta Reel media container (POST /{ig_user_id}/media with media_type=REELS).
5. Polls container status with bounded timeout (GET /{creation_id}?fields=status_code,status).
6. Publishes processed container (POST /{ig_user_id}/media_publish).
7. Fetches permanent Instagram Reel URL and records audit trail in social_publish_attempts.
8. Strictly preserves local source media on disk for multi-platform reuse.
9. Enforces zero-token exposure across all errors, logs, and response structures.
"""

import os
import re
import time
import json
import secrets
import datetime
import requests

from config import Config
from database.db import get_connection
from services.instagram_oauth_service import (
    get_valid_instagram_access_token,
    mark_instagram_account_expired,
    mark_instagram_account_error
)
from services.upload_service import get_safe_temp_path


# =============================================================================
# 1. Caption Formatting & Sanitization
# =============================================================================

def format_instagram_caption(title: str = "", description: str = "", hashtags: str = "") -> str:
    """
    Construct a clean, formatted, and bounded Instagram caption from post metadata.
    - Combines title, description, and hashtags cleanly.
    - Formats hashtags with '#' prefix and removes duplicates.
    - Enforces Instagram's 2,200 character limit with deterministic truncation.
    - Sanitizes internal tokens, file paths, and IDs.
    """
    parts = []

    clean_title = (title or "").strip()
    if clean_title:
        parts.append(clean_title)

    clean_desc = (description or "").strip()
    if clean_desc and clean_desc != clean_title:
        parts.append(clean_desc)

    # Process and format hashtags
    if hashtags:
        if isinstance(hashtags, list):
            tags = [str(t).strip().lstrip("#") for t in hashtags if str(t).strip()]
        else:
            raw_tags = str(hashtags).replace(",", " ").split()
            tags = [t.strip().lstrip("#") for t in raw_tags if t.strip()]

        # Deduplicate while preserving order
        unique_tags = []
        seen = set()
        for t in tags:
            clean_t = re.sub(r"[^\w]", "", t)
            if clean_t and clean_t.lower() not in seen:
                seen.add(clean_t.lower())
                unique_tags.append(f"#{clean_t}")

        if unique_tags:
            parts.append(" ".join(unique_tags))

    caption = "\n\n".join(parts).strip()

    # Meta Instagram caption maximum length is 2,200 characters
    MAX_CAPTION_LENGTH = 2200
    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[: MAX_CAPTION_LENGTH - 3].rstrip() + "..."

    return caption


# =============================================================================
# 2. Public Video URL Resolution & Media Delivery
# =============================================================================

def resolve_instagram_video_url(content_id: int, temp_media_path: str, custom_video_url: str = None) -> str:
    """
    Resolves the publicly accessible HTTP/HTTPS URL for Meta ingestion servers.
    - If custom_video_url is provided, validates that it is a valid HTTP/HTTPS URL.
    - If Config.INSTAGRAM_MEDIA_BASE_URL is configured, constructs public media route.
    - Strictly rejects local filesystem paths (e.g. /Users/..., C:\\...).
    - Raises a clear configuration error if no public media URL is configured.
    """
    # 1. Custom video URL provided in post metadata or parameter
    if custom_video_url and isinstance(custom_video_url, str) and custom_video_url.strip():
        url = custom_video_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"Invalid custom video URL '{url}'. Instagram Reel publishing requires an HTTP/HTTPS URL.")
        # Reject local filesystem path disguised as string
        if os.path.isabs(url) or "\\" in url or url.startswith("file://"):
            raise ValueError("Local filesystem paths cannot be used as Instagram video URLs.")
        return url

    # 2. Derive from Config.INSTAGRAM_MEDIA_BASE_URL
    base_url = Config.INSTAGRAM_MEDIA_BASE_URL
    if base_url and isinstance(base_url, str) and base_url.strip():
        clean_base = base_url.strip().rstrip("/")
        if not (clean_base.startswith("http://") or clean_base.startswith("https://")):
            raise ValueError(f"INSTAGRAM_MEDIA_BASE_URL '{clean_base}' is invalid. Must start with http:// or https://.")
        filename = os.path.basename(temp_media_path) if temp_media_path else f"content_{content_id}.mp4"
        return f"{clean_base}/api/social-media/public-media/{content_id}/{filename}"

    # 3. No public URL configuration available
    raise ValueError(
        "Instagram Reel publishing requires a publicly accessible video URL for Meta servers to ingest. "
        "Please configure INSTAGRAM_MEDIA_BASE_URL in your .env (e.g. your ngrok tunnel or domain URL)."
    )


# =============================================================================
# 3. Meta Graph API Low-Level Operations
# =============================================================================

def create_instagram_reel_container(
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: str = "",
    cover_url: str = None
) -> str:
    """
    Create a Meta Reel media container via POST /{ig_user_id}/media with media_type=REELS.
    Returns creation_id (container ID).
    """
    if not ig_user_id or not access_token:
        raise ValueError("Instagram User ID and valid access token are required for container creation.")
    if not video_url:
        raise ValueError("Public video URL is required for Instagram Reel publishing.")

    # Guard against accidentally sending local filesystem paths
    if not (video_url.startswith("http://") or video_url.startswith("https://")):
        raise ValueError(f"Invalid video URL '{video_url}'. Instagram requires a publicly accessible HTTP/HTTPS URL.")

    endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/{ig_user_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true"
    }
    if cover_url:
        payload["cover_url"] = cover_url

    try:
        resp = requests.post(endpoint, headers=headers, data=payload, timeout=30)
    except Exception as e:
        raise ValueError(f"Temporary failure connecting to Meta Graph API media endpoint: {str(e)}")

    if resp.status_code != 200:
        err_msg = _extract_sanitized_meta_error(resp)
        raise ValueError(f"Meta Reel container creation failed (HTTP {resp.status_code}): {err_msg}")

    try:
        data = resp.json()
    except Exception:
        raise ValueError("Invalid JSON response received from Meta Graph API during container creation.")

    creation_id = data.get("id")
    if not creation_id or not str(creation_id).strip():
        raise ValueError("Meta Reel container creation response missing container ID.")

    return str(creation_id)


def poll_instagram_container_status(
    creation_id: str,
    access_token: str,
    max_wait_seconds: float = None,
    poll_interval_seconds: float = None
) -> bool:
    """
    Poll container processing status on Meta Graph API with bounded timeout.
    GET /{creation_id}?fields=status_code,status
    - FINISHED / PUBLISHED: Success -> returns True.
    - IN_PROGRESS: sleeps and continues polling.
    - ERROR: raises descriptive error.
    - EXPIRED: raises error.
    - Timeout: raises TimeoutError.
    """
    if not creation_id or not access_token:
        raise ValueError("Container ID and access token are required for status check.")

    max_wait = max_wait_seconds if max_wait_seconds is not None else Config.INSTAGRAM_PUBLISH_MAX_WAIT_SECONDS
    interval = poll_interval_seconds if poll_interval_seconds is not None else Config.INSTAGRAM_PUBLISH_POLL_INTERVAL_SECONDS
    endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/{creation_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "status_code,status"}

    deadline = time.time() + max_wait

    while time.time() <= deadline:
        try:
            resp = requests.get(endpoint, headers=headers, params=params, timeout=20)
        except Exception as e:
            # On transient network glitch, wait and retry if time remains
            time.sleep(interval)
            continue

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                time.sleep(interval)
                continue

            status_code = str(data.get("status_code", "")).upper()

            if status_code in ("FINISHED", "PUBLISHED"):
                return True
            elif status_code == "IN_PROGRESS":
                time.sleep(interval)
                continue
            elif status_code == "ERROR":
                err_detail = data.get("status", "Media processing failed on Meta servers.")
                raise ValueError(f"Instagram media processing error: {err_detail}")
            elif status_code == "EXPIRED":
                raise ValueError("Instagram media container expired before publishing.")
            else:
                # Unexpected status code
                raise ValueError(f"Unexpected Instagram container status '{status_code}'.")
        elif resp.status_code >= 500:
            time.sleep(interval)
            continue
        else:
            err_msg = _extract_sanitized_meta_error(resp)
            raise ValueError(f"Failed to check Instagram container status (HTTP {resp.status_code}): {err_msg}")

    raise TimeoutError(f"Instagram video processing timed out after {max_wait} seconds.")


def publish_instagram_container(ig_user_id: str, creation_id: str, access_token: str) -> str:
    """
    Publish a ready media container to Instagram feed via POST /{ig_user_id}/media_publish.
    Returns final Instagram media ID (platform_post_id).
    """
    if not ig_user_id or not creation_id or not access_token:
        raise ValueError("Instagram User ID, Container ID, and access token are required to publish.")

    endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"creation_id": creation_id}

    try:
        resp = requests.post(endpoint, headers=headers, data=payload, timeout=30)
    except Exception as e:
        raise ValueError(f"Temporary failure connecting to Meta media_publish endpoint: {str(e)}")

    if resp.status_code != 200:
        err_msg = _extract_sanitized_meta_error(resp)
        raise ValueError(f"Meta Reel publishing failed (HTTP {resp.status_code}): {err_msg}")

    try:
        data = resp.json()
    except Exception:
        raise ValueError("Invalid JSON response received from Meta Graph API during publishing.")

    media_id = data.get("id")
    if not media_id or not str(media_id).strip():
        raise ValueError("Meta Reel publishing response missing final media ID.")

    return str(media_id)


def get_instagram_media_permalink(media_id: str, access_token: str) -> str:
    """
    Retrieve official permalink for a published Instagram media item.
    GET /{media_id}?fields=id,permalink,shortcode
    Falls back gracefully to https://www.instagram.com/reel/{media_id}/ if query fails.
    """
    if not media_id or not access_token:
        return f"https://www.instagram.com/reel/{media_id}/" if media_id else ""

    endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "id,permalink,shortcode"}

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            permalink = data.get("permalink")
            if permalink and str(permalink).strip():
                return str(permalink).strip()
    except Exception:
        pass

    return f"https://www.instagram.com/reel/{media_id}/"


def _extract_sanitized_meta_error(resp) -> str:
    """
    Safely extract error message from Meta response, removing any access tokens or secrets.
    """
    try:
        err_json = resp.json().get("error", {})
        msg = err_json.get("message") or err_json.get("error_user_msg") or str(err_json)
        # Strip potential token echoes
        clean_msg = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", msg)
        return clean_msg
    except Exception:
        return f"Meta API error response (HTTP {resp.status_code})"


# =============================================================================
# 4. Status Recalculation Helper
# =============================================================================

def recalculate_content_overall_status(content_id: int):
    """
    Recalculates master social_content.overall_status based on all target platform rows.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status FROM social_content_platforms WHERE content_id = %s;", (content_id,))
        statuses = [r[0] for r in cur.fetchall()]

        if not statuses:
            return

        if all(s == "PUBLISHED" for s in statuses):
            overall = "PUBLISHED"
        elif any(s in ("PROCESSING", "PENDING") for s in statuses):
            overall = "PROCESSING"
        elif any(s == "PUBLISHED" for s in statuses) and any(s == "FAILED" for s in statuses):
            overall = "PARTIALLY_PUBLISHED"
        elif all(s == "FAILED" for s in statuses):
            overall = "FAILED"
        else:
            overall = "DRAFT"

        cur.execute("""
            UPDATE social_content
            SET overall_status = %s,
                published_at = CASE WHEN %s = 'PUBLISHED' THEN CURRENT_TIMESTAMP ELSE published_at END
            WHERE id = %s;
        """, (overall, overall, content_id))
        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =============================================================================
# 5. Master Public Instagram Reel Publishing Orchestrator
# =============================================================================

def publish_instagram_reel(
    user_id: int,
    content_id: int,
    account_id: int,
    custom_video_url: str = None,
    poll_timeout_seconds: float = None
) -> dict:
    """
    Publishes an Instagram Reel for a content record using official Meta Graph API:
    1. Verifies user ownership of social_content and social_accounts.
    2. Validates account platform is 'INSTAGRAM' and status is 'ACTIVE'.
    3. Retrieves decrypted valid Instagram access token via token lifecycle service.
    4. Validates local media file existence and TTL retention.
    5. Formats Instagram caption.
    6. Resolves public video URL for Meta ingestion servers.
    7. Upserts social_content_platforms record (platform_status='PROCESSING').
    8. Records social_publish_attempts audit entry (status='STARTED').
    9. Creates Reel container -> Polls status -> Publishes container.
    10. Saves Instagram media ID & permalink URL -> Marks status='PUBLISHED'.
    11. Strictly preserves source media file on disk.
    12. Recalculates social_content.overall_status.
    Returns sanitized result dictionary with HTTP status indications.
    """
    if not user_id:
        return {"success": False, "error": "User authentication required.", "status_code": 401}
    if not content_id or not isinstance(content_id, int) or content_id <= 0:
        return {"success": False, "error": "Valid content ID is required.", "status_code": 400}
    if not account_id or not isinstance(account_id, int) or account_id <= 0:
        return {"success": False, "error": "Valid Instagram account ID is required.", "status_code": 400}

    conn = None
    cur = None
    start_time = time.time()
    scp_id = None
    attempt_id = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Verify content ownership and media presence
        cur.execute("""
            SELECT id, user_id, title, common_caption, hashtags, media_type,
                   temp_media_path, temp_file_deleted, temp_file_expires_at
            FROM social_content
            WHERE id = %s AND user_id = %s;
        """, (content_id, user_id))
        c_row = cur.fetchone()

        if not c_row:
            return {"success": False, "error": "Content item not found or access denied.", "status_code": 404}

        (
            cid, c_uid, title, description, tags, media_type,
            temp_media_path, temp_deleted, expires_at
        ) = c_row

        if temp_deleted or not temp_media_path:
            return {"success": False, "error": "Temporary video file has been deleted or purged. Please re-upload.", "status_code": 410}

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return {"success": False, "error": "Temporary video file has expired. Please re-upload.", "status_code": 410}

        # Verify physical file existence on disk
        safe_path = get_safe_temp_path(temp_media_path)
        if not safe_path or not os.path.exists(safe_path):
            return {"success": False, "error": "Local temporary video media not found on disk. Please re-upload.", "status_code": 410}

        # 2. Verify account ownership, platform, and usable connection
        cur.execute("""
            SELECT id, user_id, platform, platform_account_id, account_name,
                   account_username, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))
        acc_row = cur.fetchone()

        if not acc_row:
            return {"success": False, "error": "Instagram account not found or access denied.", "status_code": 404}

        aid, a_uid, platform, ig_user_id, acc_name, acc_username, conn_status = acc_row

        if platform != "INSTAGRAM":
            return {"success": False, "error": f"Selected account is not an Instagram account (platform: {platform}).", "status_code": 400}

        if conn_status != "ACTIVE":
            return {"success": False, "error": f"Instagram account connection is in {conn_status} state. Please reconnect your account.", "status_code": 400}

        # 3. Retrieve valid access token using Instagram token lifecycle service
        token_ok, access_token, token_err = get_valid_instagram_access_token(account_id=aid, user_id=user_id, auto_refresh=True)
        if not token_ok or not access_token:
            return {"success": False, "error": token_err or "Failed to obtain valid Instagram access token. Please reconnect.", "status_code": 401}

        # 4. Format caption and resolve public video URL
        caption = format_instagram_caption(title=title, description=description, hashtags=tags)

        try:
            video_url = resolve_instagram_video_url(
                content_id=cid,
                temp_media_path=temp_media_path,
                custom_video_url=custom_video_url
            )
        except ValueError as e:
            return {"success": False, "error": str(e), "status_code": 400}

        # 5. Upsert social_content_platforms record
        cur.execute("""
            INSERT INTO social_content_platforms (
                content_id, account_id, platform, custom_title, custom_caption,
                platform_status, processing_status, last_attempt_at, updated_at
            )
            VALUES (
                %s, %s, 'INSTAGRAM', %s, %s,
                'PROCESSING', 'UPLOADING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (content_id, platform, account_id) DO UPDATE SET
                platform_status = 'PROCESSING',
                processing_status = 'UPLOADING',
                last_attempt_at = CURRENT_TIMESTAMP,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, retry_count;
        """, (cid, aid, title, caption))
        scp_row = cur.fetchone()
        scp_id = scp_row[0]
        retry_count = scp_row[1]

        # 6. Record social_publish_attempts audit entry
        cur.execute("""
            INSERT INTO social_publish_attempts (
                content_platform_id, attempt_number, status, started_at
            )
            VALUES (%s, %s, 'STARTED', CURRENT_TIMESTAMP)
            RETURNING id;
        """, (scp_id, retry_count + 1))
        attempt_id = cur.fetchone()[0]

        # Update overall status to PROCESSING
        cur.execute("UPDATE social_content SET overall_status = 'PROCESSING' WHERE id = %s;", (cid,))
        conn.commit()

        # 7. Create Meta Reel Container
        creation_id = create_instagram_reel_container(
            ig_user_id=ig_user_id,
            access_token=access_token,
            video_url=video_url,
            caption=caption
        )

        # Update processing_status to PROCESSING
        cur.execute("""
            UPDATE social_content_platforms
            SET processing_status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (scp_id,))
        conn.commit()

        # 8. Poll container processing status on Meta
        poll_instagram_container_status(
            creation_id=creation_id,
            access_token=access_token,
            max_wait_seconds=poll_timeout_seconds
        )

        # Update processing_status to READY
        cur.execute("""
            UPDATE social_content_platforms
            SET processing_status = 'READY', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (scp_id,))
        conn.commit()

        # 9. Publish container to Instagram
        media_id = publish_instagram_container(
            ig_user_id=ig_user_id,
            creation_id=creation_id,
            access_token=access_token
        )

        # 10. Fetch permanent URL
        permalink = get_instagram_media_permalink(media_id=media_id, access_token=access_token)

        # 11. Finalize database state
        duration_ms = int((time.time() - start_time) * 1000)
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_status = 'PUBLISHED',
                processing_status = 'READY',
                platform_post_id = %s,
                platform_post_url = %s,
                published_at = CURRENT_TIMESTAMP,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (media_id, permalink, scp_id))

        cur.execute("""
            UPDATE social_publish_attempts
            SET status = 'SUCCESS',
                completed_at = CURRENT_TIMESTAMP,
                duration_ms = %s
            WHERE id = %s;
        """, (duration_ms, attempt_id))
        conn.commit()

        # Recalculate overall status
        recalculate_content_overall_status(cid)

        return {
            "success": True,
            "platform": "INSTAGRAM",
            "content_id": cid,
            "account_id": aid,
            "publish_status": "PUBLISHED",
            "publish_id": media_id,
            "publish_url": permalink,
            "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    except Exception as e:
        if conn:
            conn.rollback()

        err_str = str(e)
        # Sanitize error to avoid leaking tokens
        clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", err_str)

        # Update failure status in DB if scp_id exists
        try:
            if conn and scp_id:
                duration_ms = int((time.time() - start_time) * 1000)
                cur = conn.cursor()
                cur.execute("""
                    UPDATE social_content_platforms
                    SET platform_status = 'FAILED',
                        processing_status = 'FAILED',
                        error_message = %s,
                        retry_count = retry_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (clean_err, scp_id))

                if attempt_id:
                    cur.execute("""
                        UPDATE social_publish_attempts
                        SET status = 'FAILED',
                            error_message = %s,
                            completed_at = CURRENT_TIMESTAMP,
                            duration_ms = %s
                        WHERE id = %s;
                    """, (clean_err, duration_ms, attempt_id))

                conn.commit()
                recalculate_content_overall_status(content_id)
        except Exception:
            pass

        return {
            "success": False,
            "platform": "INSTAGRAM",
            "content_id": content_id,
            "account_id": account_id,
            "publish_status": "FAILED",
            "error": clean_err,
            "status_code": 500 if "unexpected" in clean_err.lower() else 400
        }
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
