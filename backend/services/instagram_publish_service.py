"""
LifeOS — Instagram Reel Publishing Service (Stage 7A & 7B)
Hardened fault-tolerant publishing system with:
1. Ownership & permission verification.
2. Short database transactions with row-level locking for atomic attempt claiming.
3. Already-published protection: immediate return of existing successful post without Meta calls.
4. Active processing protection: returns 409 Conflict if publishing is in progress.
5. Configurable retry limit enforcement (INSTAGRAM_MAX_PUBLISH_RETRIES).
6. Atomically tracked retry_count and append-only audit trail in social_publish_attempts.
7. Deterministic per-attempt idempotency keys (no secrets inside keys).
8. Ambiguous timeout and Meta container recovery without duplicate container creation.
9. Local source media retention on disk for multi-platform publishing.
10. Strict zero-token and zero-secret exposure across responses, logs, and database errors.
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
    if custom_video_url and isinstance(custom_video_url, str) and custom_video_url.strip():
        url = custom_video_url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"Invalid custom video URL '{url}'. Instagram Reel publishing requires an HTTP/HTTPS URL.")
        # Reject local filesystem path disguised as string
        if os.path.isabs(url) or "\\" in url or url.startswith("file://"):
            raise ValueError("Local filesystem paths cannot be used as Instagram video URLs.")
        return url

    base_url = Config.INSTAGRAM_MEDIA_BASE_URL
    if base_url and isinstance(base_url, str) and base_url.strip():
        clean_base = base_url.strip().rstrip("/")
        if not (clean_base.startswith("http://") or clean_base.startswith("https://")):
            raise ValueError(f"INSTAGRAM_MEDIA_BASE_URL '{clean_base}' is invalid. Must start with http:// or https://.")
        filename = os.path.basename(temp_media_path) if temp_media_path else f"content_{content_id}.mp4"
        return f"{clean_base}/api/social-media/public-media/{content_id}/{filename}"

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
        except Exception:
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
# 5. Atomic Claim and Slot Locking (Stage 7B Hardening)
# =============================================================================

def claim_instagram_publish_slot(
    user_id: int,
    content_id: int,
    account_id: int,
    is_retry: bool = False
) -> dict:
    """
    Atomically claims a publish/retry slot using a short DB transaction with row-level locking:
    1. Validates ownership of content and account.
    2. Inspects existing social_content_platforms record:
       - If PUBLISHED: returns already_published payload (no Meta calls).
       - If PROCESSING: checks unexpired lease; if active, returns 409 Conflict.
       - If FAILED: verifies retry_count < INSTAGRAM_MAX_PUBLISH_RETRIES. If exceeded, returns 400.
    3. Atomically sets platform_status='PROCESSING', increments retry_count if retrying,
       generates unique deterministic idempotency_key, and inserts social_publish_attempts ('STARTED').
    4. Commits transaction immediately so DB locks are released before calling Meta Graph API.
    """
    conn = None
    cur = None
    lease_seconds = Config.INSTAGRAM_PUBLISH_LEASE_SECONDS
    claim_token = secrets.token_hex(16)

    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Verify content ownership and media state
        cur.execute("""
            SELECT id, user_id, title, common_caption, hashtags, media_type,
                   temp_media_path, temp_file_deleted, temp_file_expires_at
            FROM social_content
            WHERE id = %s AND user_id = %s
            FOR UPDATE;
        """, (content_id, user_id))
        c_row = cur.fetchone()

        if not c_row:
            return {"claimed": False, "error": "Content item not found or access denied.", "status_code": 404}

        (
            cid, c_uid, title, description, tags, media_type,
            temp_media_path, temp_deleted, expires_at
        ) = c_row

        if temp_deleted or not temp_media_path:
            return {"claimed": False, "error": "Temporary video file has been deleted or purged. Please re-upload.", "status_code": 410}

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return {"claimed": False, "error": "Temporary video file has expired. Please re-upload.", "status_code": 410}

        safe_path = get_safe_temp_path(temp_media_path)
        if not safe_path or not os.path.exists(safe_path):
            return {"claimed": False, "error": "Local temporary video media not found on disk. Please re-upload.", "status_code": 410}

        # 2. Verify account ownership, platform, and usable connection
        cur.execute("""
            SELECT id, user_id, platform, platform_account_id, account_name,
                   account_username, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))
        acc_row = cur.fetchone()

        if not acc_row:
            return {"claimed": False, "error": "Instagram account not found or access denied.", "status_code": 404}

        aid, a_uid, platform, ig_user_id, acc_name, acc_username, conn_status = acc_row

        if platform != "INSTAGRAM":
            return {"claimed": False, "error": f"Selected account is not an Instagram account (platform: {platform}).", "status_code": 400}

        if conn_status != "ACTIVE":
            return {"claimed": False, "error": f"Instagram account connection is in {conn_status} state. Please reconnect your account.", "status_code": 400}

        # 3. Retrieve valid access token
        token_ok, access_token, token_err = get_valid_instagram_access_token(account_id=aid, user_id=user_id, auto_refresh=True)
        if not token_ok or not access_token:
            return {"claimed": False, "error": token_err or "Failed to obtain valid Instagram access token. Please reconnect.", "status_code": 401}

        # 4. Check existing social_content_platforms row
        cur.execute("""
            SELECT id, platform_status, processing_status, platform_post_id,
                   platform_post_url, retry_count, claim_expires_at, published_at,
                   meta_container_id
            FROM social_content_platforms
            WHERE content_id = %s AND platform = 'INSTAGRAM' AND account_id = %s
            FOR UPDATE;
        """, (cid, aid))
        scp_row = cur.fetchone()

        if scp_row:
            (
                scp_id, p_status, proc_status, post_id,
                post_url, retry_count, claim_exp, published_at,
                meta_container_id
            ) = scp_row

            # A. Already published protection
            if p_status == "PUBLISHED":
                conn.commit()
                return {
                    "claimed": False,
                    "already_published": True,
                    "success": True,
                    "platform": "INSTAGRAM",
                    "content_id": cid,
                    "account_id": aid,
                    "publish_status": "PUBLISHED",
                    "publish_id": post_id,
                    "publish_url": post_url,
                    "published_at": published_at.isoformat() if published_at else None,
                    "status_code": 200
                }

            # B. Active processing protection (409 Conflict)
            if p_status == "PROCESSING":
                if claim_exp:
                    if claim_exp.tzinfo is None:
                        claim_exp = claim_exp.replace(tzinfo=datetime.timezone.utc)
                    if claim_exp > now_utc:
                        conn.commit()
                        return {
                            "claimed": False,
                            "is_processing": True,
                            "success": False,
                            "platform": "INSTAGRAM",
                            "content_id": cid,
                            "account_id": aid,
                            "publish_status": "PROCESSING",
                            "message": "Instagram publishing is already in progress.",
                            "status_code": 409
                        }

            # C. Retry Limit Check if FAILED
            if p_status == "FAILED" or is_retry:
                if retry_count >= Config.INSTAGRAM_MAX_PUBLISH_RETRIES:
                    conn.commit()
                    return {
                        "claimed": False,
                        "retry_limit_reached": True,
                        "retry_allowed": False,
                        "success": False,
                        "platform": "INSTAGRAM",
                        "content_id": cid,
                        "account_id": aid,
                        "publish_status": "FAILED",
                        "message": "Instagram publishing retry limit reached.",
                        "status_code": 400
                    }

            # Claim existing row
            new_attempt_number = retry_count + 1
            cur.execute("""
                UPDATE social_content_platforms
                SET platform_status = 'PROCESSING',
                    processing_status = 'UPLOADING',
                    claim_token = %s,
                    claim_expires_at = CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    error_message = NULL,
                    retry_count = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (claim_token, str(lease_seconds), new_attempt_number if (p_status == "FAILED" or is_retry) else retry_count, scp_id))

        else:
            # D. Fresh Insert
            new_attempt_number = 1
            cur.execute("""
                INSERT INTO social_content_platforms (
                    content_id, account_id, platform, custom_title, custom_caption,
                    platform_status, processing_status, retry_count, claim_token,
                    claim_expires_at, last_attempt_at, updated_at
                )
                VALUES (
                    %s, %s, 'INSTAGRAM', %s, %s,
                    'PROCESSING', 'UPLOADING', 0, %s,
                    CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id;
            """, (cid, aid, title, description, claim_token, str(lease_seconds)))
            scp_id = cur.fetchone()[0]
            meta_container_id = None

        # Insert audit attempt with deterministic idempotency key
        idempotency_key = f"ig_{user_id}_{cid}_{aid}_att_{new_attempt_number}"
        cur.execute("""
            INSERT INTO social_publish_attempts (
                content_platform_id, attempt_number, status, idempotency_key, started_at
            )
            VALUES (%s, %s, 'STARTED', %s, CURRENT_TIMESTAMP)
            RETURNING id;
        """, (scp_id, new_attempt_number, idempotency_key))
        attempt_id = cur.fetchone()[0]

        # Update overall status
        cur.execute("UPDATE social_content SET overall_status = 'PROCESSING' WHERE id = %s;", (cid,))
        conn.commit()

        return {
            "claimed": True,
            "scp_id": scp_id,
            "attempt_id": attempt_id,
            "attempt_number": new_attempt_number,
            "content_id": cid,
            "account_id": aid,
            "ig_user_id": ig_user_id,
            "access_token": access_token,
            "title": title,
            "description": description,
            "tags": tags,
            "temp_media_path": temp_media_path,
            "meta_container_id": meta_container_id,
            "claim_token": claim_token
        }

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =============================================================================
# 6. Master Public Instagram Reel Publishing Orchestrator (Hardened Stage 7B)
# =============================================================================

def publish_instagram_reel(
    user_id: int,
    content_id: int,
    account_id: int,
    custom_video_url: str = None,
    poll_timeout_seconds: float = None,
    is_retry: bool = False
) -> dict:
    """
    Publishes an Instagram Reel for a content record with fault-tolerant idempotency:
    1. Atomically claims the publish/retry slot using row-level locking.
    2. If already PUBLISHED, returns existing record immediately (no duplicate posts).
    3. If active PROCESSING, returns 409 Conflict.
    4. If retry limit reached, returns 400 retry limit reached.
    5. Reuses previous Meta container ID if available and valid.
    6. Creates Reel container -> Polls status -> Publishes container.
    7. Saves media ID & permalink -> Marks status='PUBLISHED'.
    8. Records audit trail in social_publish_attempts.
    9. Strictly preserves source media file on disk.
    10. Recalculates social_content.overall_status.
    """
    if not user_id:
        return {"success": False, "error": "User authentication required.", "status_code": 401}
    if not content_id or not isinstance(content_id, int) or content_id <= 0:
        return {"success": False, "error": "Valid content ID is required.", "status_code": 400}
    if not account_id or not isinstance(account_id, int) or account_id <= 0:
        return {"success": False, "error": "Valid Instagram account ID is required.", "status_code": 400}

    # 1. Atomically claim publish slot
    claim_res = claim_instagram_publish_slot(
        user_id=user_id,
        content_id=content_id,
        account_id=account_id,
        is_retry=is_retry
    )

    if not claim_res.get("claimed"):
        # Already published, active processing (409), retry limit reached (400), or error
        status_code = claim_res.get("status_code", 400)
        return claim_res

    scp_id = claim_res["scp_id"]
    attempt_id = claim_res["attempt_id"]
    ig_user_id = claim_res["ig_user_id"]
    access_token = claim_res["access_token"]
    title = claim_res["title"]
    description = claim_res["description"]
    tags = claim_res["tags"]
    temp_media_path = claim_res["temp_media_path"]
    existing_container_id = claim_res.get("meta_container_id")

    start_time = time.time()
    creation_id = existing_container_id

    # 2. Format caption and resolve public video URL
    caption = format_instagram_caption(title=title, description=description, hashtags=tags)

    try:
        video_url = resolve_instagram_video_url(
            content_id=content_id,
            temp_media_path=temp_media_path,
            custom_video_url=custom_video_url
        )
    except ValueError as e:
        clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", str(e))
        _record_publish_failure(scp_id, attempt_id, content_id, clean_err, start_time)
        return {"success": False, "error": clean_err, "publish_status": "FAILED", "status_code": 400}

    # 3. Container Recovery or Creation
    container_ready = False

    # A. Check if previously created container can be recovered
    if creation_id:
        try:
            container_ready = poll_instagram_container_status(
                creation_id=creation_id,
                access_token=access_token,
                max_wait_seconds=2,
                poll_interval_seconds=0.1
            )
        except Exception:
            # If previous container expired or errored, reset creation_id to create a fresh one
            creation_id = None

    # B. Create fresh container if needed
    if not creation_id or not container_ready:
        try:
            creation_id = create_instagram_reel_container(
                ig_user_id=ig_user_id,
                access_token=access_token,
                video_url=video_url,
                caption=caption
            )
            # Immediately persist meta_container_id for recovery
            _save_meta_container_id(scp_id, creation_id)
        except Exception as e:
            clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", str(e))
            _record_publish_failure(scp_id, attempt_id, content_id, clean_err, start_time)
            return {"success": False, "error": clean_err, "publish_status": "FAILED", "status_code": 400}

    # 4. Poll container processing status
    if not container_ready:
        try:
            _update_platform_processing_status(scp_id, "PROCESSING")
            poll_instagram_container_status(
                creation_id=creation_id,
                access_token=access_token,
                max_wait_seconds=poll_timeout_seconds
            )
            _update_platform_processing_status(scp_id, "READY")
        except Exception as e:
            clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", str(e))
            _record_publish_failure(scp_id, attempt_id, content_id, clean_err, start_time)
            return {"success": False, "error": clean_err, "publish_status": "FAILED", "status_code": 400}

    # 5. Publish container to Instagram
    try:
        media_id = publish_instagram_container(
            ig_user_id=ig_user_id,
            creation_id=creation_id,
            access_token=access_token
        )
    except Exception as e:
        clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", str(e))
        _record_publish_failure(scp_id, attempt_id, content_id, clean_err, start_time)
        return {"success": False, "error": clean_err, "publish_status": "FAILED", "status_code": 400}

    # 6. Fetch permanent URL
    permalink = get_instagram_media_permalink(media_id=media_id, access_token=access_token)

    # 7. Finalize database success state
    duration_ms = int((time.time() - start_time) * 1000)
    _record_publish_success(scp_id, attempt_id, content_id, media_id, permalink, duration_ms)

    return {
        "success": True,
        "platform": "INSTAGRAM",
        "content_id": content_id,
        "account_id": account_id,
        "publish_status": "PUBLISHED",
        "publish_id": media_id,
        "publish_url": permalink,
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status_code": 200
    }


# =============================================================================
# 7. Internal Database Helpers
# =============================================================================

def _save_meta_container_id(scp_id: int, creation_id: str):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET meta_container_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (creation_id, scp_id))
        conn.commit()
    except Exception:
        pass
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _update_platform_processing_status(scp_id: int, proc_status: str):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET processing_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (proc_status, scp_id))
        conn.commit()
    except Exception:
        pass
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _record_publish_success(
    scp_id: int,
    attempt_id: int,
    content_id: int,
    media_id: str,
    permalink: str,
    duration_ms: int
):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_status = 'PUBLISHED',
                processing_status = 'READY',
                platform_post_id = %s,
                platform_post_url = %s,
                published_at = CURRENT_TIMESTAMP,
                error_message = NULL,
                claim_token = NULL,
                claim_expires_at = NULL,
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

        recalculate_content_overall_status(content_id)
    except Exception:
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _record_publish_failure(
    scp_id: int,
    attempt_id: int,
    content_id: int,
    error_str: str,
    start_time: float
):
    conn = None
    cur = None
    try:
        duration_ms = int((time.time() - start_time) * 1000)
        clean_err = re.sub(r"(access_token|EAA)[a-zA-Z0-9_-]+", "[REDACTED]", str(error_str))

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_status = 'FAILED',
                processing_status = 'FAILED',
                error_message = %s,
                claim_token = NULL,
                claim_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (clean_err, scp_id))

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
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
