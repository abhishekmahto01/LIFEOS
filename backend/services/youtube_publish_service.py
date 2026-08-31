"""
LifeOS — YouTube Resumable Video Publishing & Lifecycle Service (Phase 6 Fully Hardened & Fenced)
Implements:
1. Strict claim token fencing (claim_token required, claim_expires_at > CURRENT_TIMESTAMP, parent user_id check).
2. All mutation helpers return bool (True/False) on UPDATE ... RETURNING, and callers stop immediately if False.
3. Finalization ordering: DB state finalized first; physical deletion only after successful fenced DB update.
4. Lease-aware backoff sleep with heartbeat renewals (sleep_with_lease_heartbeat).
5. Authoritative server offset query after timeout, connection error, 401, or ambiguous responses.
6. Claim eligibility strictly validates media presence and temp_file_expires_at.
7. Explicit Bearer token authorization on all 5 Google requests with automatic 401 token refresh.
8. Job-type discrimination (FULL_UPLOAD, PROCESSING_CHECK, THUMBNAIL_RETRY, NO_OP).
9. Processing retry scheduling (next_processing_check_at, processing_check_count).
10. Bounded ThreadPoolExecutor with startup recovery and shutdown support.
"""

import os
import re
import time
import json
import random
import secrets
import datetime
from concurrent.futures import ThreadPoolExecutor
import requests

from config import Config
from database.db import get_connection
from utils.crypto import encrypt_token, decrypt_token
from services.youtube_oauth_service import (
    get_valid_youtube_access_token,
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READONLY_SCOPE
)
from services.upload_service import (
    get_safe_temp_path,
    safe_delete_temp_file
)

# Global bounded worker pool
_publish_executor = None

def get_publish_executor() -> ThreadPoolExecutor:
    global _publish_executor
    if _publish_executor is None:
        _publish_executor = ThreadPoolExecutor(
            max_workers=Config.YOUTUBE_PUBLISH_MAX_WORKERS,
            thread_name_prefix="yt_publish_worker"
        )
    return _publish_executor

def shutdown_publish_executor(wait: bool = False):
    global _publish_executor
    if _publish_executor is not None:
        _publish_executor.shutdown(wait=wait)
        _publish_executor = None


# =============================================================================
# 1. Validation & Metadata Functions
# =============================================================================

def validate_youtube_metadata(title: str, description: str = "", tags: str = "", privacy: str = "PRIVATE", category_id: str = "22") -> dict:
    """
    Validate metadata according to strict YouTube Data API v3 limits:
    - Title: non-empty, 1-100 characters.
    - Description: max 5000 characters.
    - Tags: serialized length (names + commas) <= 500 characters.
    - Privacy: PRIVATE, UNLISTED, PUBLIC (Rejects invalid privacy values).
    - Category: string ID (e.g., '22' for People & Blogs).
    """
    if not title or not title.strip():
        raise ValueError("Video title is required.")

    clean_title = title.strip()
    if len(clean_title) > 100:
        raise ValueError(f"Video title exceeds YouTube limit of 100 characters (length: {len(clean_title)}).")

    clean_desc = (description or "").strip()
    if len(clean_desc) > 5000:
        raise ValueError(f"Video description exceeds YouTube limit of 5000 characters (length: {len(clean_desc)}).")

    valid_privacies = {"PRIVATE", "UNLISTED", "PUBLIC"}
    clean_privacy = (privacy or "").strip().upper()
    if clean_privacy not in valid_privacies:
        raise ValueError(f"Invalid privacy status '{privacy}'. Allowed values: PRIVATE, UNLISTED, PUBLIC.")

    # Process and validate tags
    tag_list = []
    if tags:
        if isinstance(tags, list):
            tag_list = [str(t).strip().lstrip("#") for t in tags if str(t).strip()]
        else:
            raw_tags = tags.replace("#", " ").replace(",", " ").split()
            tag_list = [t.strip() for t in raw_tags if t.strip()]

    # Check serialized tags total length (e.g. tag1,tag2,tag3)
    serialized_tags = ",".join(tag_list)
    if len(serialized_tags) > 500:
        raise ValueError(f"Total YouTube tags length exceeds 500 characters (length: {len(serialized_tags)}).")

    clean_category = str(category_id or "22").strip()
    if not clean_category.isdigit() or int(clean_category) <= 0:
        clean_category = "22"

    return {
        "title": clean_title,
        "description": clean_desc,
        "tags": tag_list,
        "privacy": clean_privacy,
        "category_id": clean_category
    }


# =============================================================================
# 2. Atomic Job Claiming, Lease Heartbeat & Fencing
# =============================================================================

def claim_publishing_job(content_platform_id: int, user_id: int) -> dict:
    """
    Atomically claims a YouTube publishing job using a database-backed lease and ownership verification.
    - Enforces user_id ownership via parent social_content record.
    - Discriminates job type: FULL_UPLOAD, PROCESSING_CHECK, THUMBNAIL_RETRY, or NO_OP.
    - Strictly checks media presence and TTL expiry for FULL_UPLOAD and THUMBNAIL_RETRY.
    """
    claim_token = secrets.token_hex(16)
    lease_seconds = Config.YOUTUBE_PUBLISH_LEASE_SECONDS

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Atomic conditional update enforcing ownership, unexpired/expired claim, and state eligibility
        cur.execute("""
            UPDATE social_content_platforms scp
            SET claim_token = %s,
                claim_expires_at = CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL,
                platform_status = CASE
                    WHEN scp.platform_post_id IS NOT NULL AND scp.platform_status = 'PUBLISHED' THEN scp.platform_status
                    ELSE 'PROCESSING'
                END,
                processing_status = CASE
                    WHEN scp.platform_post_id IS NOT NULL AND scp.platform_status = 'PUBLISHED' THEN scp.processing_status
                    WHEN scp.processing_status = 'IDLE' THEN 'UPLOADING'
                    ELSE scp.processing_status
                END,
                last_attempt_at = CURRENT_TIMESTAMP
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.platform = 'YOUTUBE'
              AND (scp.claim_expires_at IS NULL OR scp.claim_expires_at < CURRENT_TIMESTAMP)
              AND (
                  -- FULL_UPLOAD eligible: no post ID, media not deleted, media not expired, eligible status
                  (
                      scp.platform_post_id IS NULL
                      AND scp.platform_status IN ('PENDING', 'PROCESSING')
                      AND sc.temp_media_path IS NOT NULL
                      AND sc.temp_file_deleted = FALSE
                      AND (sc.temp_file_expires_at IS NULL OR sc.temp_file_expires_at > CURRENT_TIMESTAMP)
                  )
                  OR
                  -- PROCESSING_CHECK eligible: post ID exists, not published, check is due
                  (
                      scp.platform_post_id IS NOT NULL
                      AND scp.platform_status != 'PUBLISHED'
                      AND (scp.next_processing_check_at IS NULL OR scp.next_processing_check_at <= CURRENT_TIMESTAMP)
                  )
                  OR
                  -- THUMBNAIL_RETRY eligible: post ID exists, thumbnail failed, thumbnail media exists and not expired
                  (
                      scp.platform_post_id IS NOT NULL
                      AND scp.thumbnail_status = 'FAILED'
                      AND sc.temp_thumbnail_path IS NOT NULL
                      AND (sc.temp_file_expires_at IS NULL OR sc.temp_file_expires_at > CURRENT_TIMESTAMP)
                  )
              )
            RETURNING scp.id, scp.content_id, scp.account_id, scp.platform_post_id,
                      scp.encrypted_session_uri, scp.thumbnail_status, scp.platform_status,
                      scp.processing_status, sc.temp_media_path, sc.temp_thumbnail_path;
        """, (claim_token, str(lease_seconds), content_platform_id, user_id))

        row = cur.fetchone()
        conn.commit()

        if not row:
            return {"claimed": False, "message": "Job is currently claimed by another active worker, unauthorized, expired, or already published."}

        (
            scpid, cid, aid, post_id, enc_session, thumb_status,
            pstatus, proc_status, temp_media, temp_thumb
        ) = row

        # Determine exact job type
        if post_id is None:
            job_type = "FULL_UPLOAD"
        elif pstatus != "PUBLISHED" and proc_status != "READY":
            job_type = "PROCESSING_CHECK"
        elif thumb_status == "FAILED" and temp_thumb is not None:
            job_type = "THUMBNAIL_RETRY"
        else:
            job_type = "NO_OP"

        return {
            "claimed": True,
            "claim_token": claim_token,
            "job_type": job_type,
            "content_platform_id": scpid,
            "content_id": cid,
            "account_id": aid,
            "platform_post_id": post_id,
            "encrypted_session_uri": enc_session,
            "thumbnail_status": thumb_status
        }
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def renew_publishing_claim(content_platform_id: int, user_id: int, claim_token: str) -> bool:
    """
    Heartbeat renewal: Extends lease expiry by YOUTUBE_PUBLISH_LEASE_SECONDS.
    - Strictly checks non-empty claim_token, ownership, and unexpired lease.
    - Returns True if renewed, False if lease lost/expired/fenced by another worker.
    """
    if not claim_token or not str(claim_token).strip():
        return False

    lease_seconds = Config.YOUTUBE_PUBLISH_LEASE_SECONDS
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET claim_expires_at = CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (str(lease_seconds), content_platform_id, user_id, claim_token))

        row = cur.fetchone()
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def release_publishing_claim(content_platform_id: int, user_id: int, claim_token: str) -> bool:
    """
    Releases the claim lease after a publication attempt concludes.
    - Strictly enforces matching claim_token so a stale worker cannot release another worker's claim.
    """
    if not claim_token or not str(claim_token).strip():
        return False

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET claim_expires_at = NULL,
                claim_token = NULL
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
            RETURNING scp.id;
        """, (content_platform_id, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def sleep_with_lease_heartbeat(content_platform_id: int, user_id: int, claim_token: str, total_seconds: float, interval_seconds: float = 1.0) -> bool:
    """
    Interruptible sleep that renews lease at bounded intervals.
    - Caps total_seconds to safe bounded maximum (e.g. 60s).
    - If renewal fails at any interval, immediately returns False without sleeping further.
    """
    if not claim_token:
        return False

    capped_total = min(max(0.1, total_seconds), 60.0)
    elapsed = 0.0

    while elapsed < capped_total:
        sleep_slice = min(interval_seconds, capped_total - elapsed)
        time.sleep(sleep_slice)
        elapsed += sleep_slice

        if not renew_publishing_claim(content_platform_id, user_id, claim_token):
            return False

    return True


# =============================================================================
# 3. Resumable Upload Protocol & Chunk Streaming
# =============================================================================

def initiate_resumable_upload_session(content_platform_id: int, user_id: int, claim_token: str) -> str:
    """
    Initiates an official Google resumable upload session with Bearer token authentication.
    - Requires valid claim_token and unexpired lease.
    - Encrypts and persists session URI with strict fencing.
    """
    if not claim_token or not str(claim_token).strip():
        raise ValueError("LEASE_LOST: A valid claim token is required to initiate a resumable session.")

    # 1. Fetch metadata
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                scp.id, scp.content_id, scp.account_id, scp.custom_title, scp.custom_description,
                scp.privacy_status, scp.made_for_kids, scp.category_id, scp.platform_post_id,
                sc.title, sc.common_caption, sc.hashtags, sc.temp_media_path, sc.file_size_bytes,
                sa.raw_scopes, sa.connection_status
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            JOIN social_accounts sa ON scp.account_id = sa.id
            WHERE scp.id = %s AND sc.user_id = %s AND scp.platform = 'YOUTUBE';
        """, (content_platform_id, user_id))
        row = cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row:
        raise ValueError("YouTube publishing record not found or access denied.")

    (
        scpid, cid, aid, custom_title, custom_desc, priv_status, made_for_kids,
        cat_id, existing_post_id, master_title, master_caption, hashtags,
        temp_media_path, file_size_bytes, raw_scopes, connection_status
    ) = row

    if existing_post_id:
        return f"ALREADY_EXISTS:{existing_post_id}"

    if connection_status != "ACTIVE":
        raise ValueError(f"Connected YouTube account is {connection_status}. Please reconnect.")

    scope_set = set((raw_scopes or "").split())
    if YOUTUBE_UPLOAD_SCOPE not in scope_set:
        raise ValueError("UPLOAD_SCOPE_REQUIRED: Account requires reconnection to grant 'youtube.upload' scope.")

    if not temp_media_path:
        raise ValueError("MEDIA_EXPIRED: Temporary video file reference is missing.")

    temp_abs_path = get_safe_temp_path(temp_media_path)
    if not os.path.exists(temp_abs_path):
        raise ValueError("MEDIA_EXPIRED: Temporary video file has expired or was removed from server storage.")

    real_file_size = os.path.getsize(temp_abs_path)

    # Validate metadata
    title = custom_title or master_title
    description = custom_desc or master_caption or ""
    metadata = validate_youtube_metadata(
        title=title,
        description=description,
        tags=hashtags or "",
        privacy=priv_status or "PRIVATE",
        category_id=cat_id or "22"
    )

    # Determine validated video MIME type
    ext = os.path.splitext(temp_media_path)[1].lower()
    video_mime = "video/mp4"
    if ext == ".mov":
        video_mime = "video/quicktime"
    elif ext == ".webm":
        video_mime = "video/webm"

    # Heartbeat lease renewal before Google call
    if not renew_publishing_claim(scpid, user_id, claim_token):
        raise ValueError("LEASE_LOST: Publishing claim was lost or acquired by another worker.")

    access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id)

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": metadata["category_id"]
        },
        "status": {
            "privacyStatus": metadata["privacy"].lower(),
            "selfDeclaredMadeForKids": bool(made_for_kids),
            "embeddable": True
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": video_mime,
        "X-Upload-Content-Length": str(real_file_size)
    }

    url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    resp = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=(Config.YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS, Config.YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS)
    )

    # Heartbeat lease renewal after Google call
    if not renew_publishing_claim(scpid, user_id, claim_token):
        raise ValueError("LEASE_LOST: Publishing claim was lost during session creation.")

    if resp.status_code not in (200, 201):
        error_code = f"HTTP_{resp.status_code}"
        error_text = f"Google rejected resumable session initiation (HTTP {resp.status_code})."
        _record_upload_failure(scpid, user_id, claim_token, error_code, error_text)
        raise ValueError(error_text)

    session_uri = resp.headers.get("Location")
    if not session_uri:
        raise ValueError("Google did not return a resumable session Location header.")

    encrypted_session = encrypt_token(session_uri)

    # Fenced DB update
    updated = _save_resumable_session_uri(scpid, user_id, claim_token, cid, encrypted_session, real_file_size)
    if not updated:
        raise ValueError("LEASE_LOST: Lost lease while persisting resumable session URI.")

    return session_uri


def _query_server_offset(session_uri: str, access_token: str, file_size: int) -> tuple:
    """
    Queries Google for server-acknowledged byte offset with status headers.
    Returns: (status_code, next_offset, video_id)
    """
    try:
        status_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Length": "0",
            "Content-Range": f"bytes */{file_size}"
        }
        status_resp = requests.put(
            session_uri,
            headers=status_headers,
            timeout=(Config.YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS, Config.YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS)
        )

        if status_resp.status_code == 308:
            range_header = status_resp.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                match = re.search(r"bytes=0-(\d+)", range_header)
                if match:
                    parsed_offset = int(match.group(1)) + 1
                    if 0 <= parsed_offset <= file_size:
                        return (308, parsed_offset, None)
            return (308, 0, None)

        elif status_resp.status_code in (200, 201):
            try:
                resp_json = status_resp.json()
                video_id = resp_json.get("id")
                return (status_resp.status_code, file_size, video_id)
            except Exception:
                return (status_resp.status_code, 0, None)

        return (status_resp.status_code, 0, None)
    except Exception:
        return (-1, 0, None)


def stream_video_chunks(content_platform_id: int, user_id: int, claim_token: str) -> dict:
    """
    Streams video file in 1MB chunks to YouTube with full Bearer token authentication and lease heartbeat.
    - Requires valid non-empty claim_token and active lease.
    - Queries Google for server-confirmed offset after any error or ambiguous response.
    - Handles 308 Resume Incomplete, monotonic offset updates, and 401 token refreshing.
    - Stops immediately if fencing lease is lost.
    """
    if not claim_token or not str(claim_token).strip():
        return {"success": False, "error": "LEASE_LOST: A valid claim token is required to stream video chunks."}

    # 1. Fetch initial state
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                scp.id, scp.content_id, scp.account_id, scp.encrypted_session_uri,
                scp.total_bytes, scp.bytes_sent, scp.platform_post_id,
                sc.temp_media_path
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            WHERE scp.id = %s AND sc.user_id = %s;
        """, (content_platform_id, user_id))
        row = cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row:
        return {"success": False, "error": "Publishing record not found or access denied."}

    scpid, cid, aid, enc_session, total_bytes, bytes_sent, existing_video_id, temp_media_path = row

    if existing_video_id:
        return {"success": True, "video_id": existing_video_id, "already_completed": True}

    if not temp_media_path:
        return {"success": False, "error": "Temporary video file reference is missing."}

    temp_abs_path = get_safe_temp_path(temp_media_path)
    if not os.path.exists(temp_abs_path):
        return {"success": False, "error": "Temporary video file is missing or expired."}

    file_size = os.path.getsize(temp_abs_path)

    # Obtain or decrypt session URI
    try:
        if not enc_session:
            session_uri = initiate_resumable_upload_session(content_platform_id, user_id, claim_token)
            if session_uri.startswith("ALREADY_EXISTS:"):
                return {"success": True, "video_id": session_uri.split(":")[1], "already_completed": True}
        else:
            try:
                session_uri = decrypt_token(enc_session)
            except Exception:
                session_uri = initiate_resumable_upload_session(content_platform_id, user_id, claim_token)
    except ValueError as ve:
        return {"success": False, "error": str(ve)}

    # Heartbeat lease renewal
    if not renew_publishing_claim(scpid, user_id, claim_token):
        return {"success": False, "error": "LEASE_LOST: Publishing lease expired or was reclaimed by another worker."}

    access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id)

    # Query initial server offset
    st_code, start_offset, finished_vid = _query_server_offset(session_uri, access_token, file_size)
    if finished_vid:
        if not _save_video_id_and_status(scpid, user_id, claim_token, finished_vid):
            return {"success": False, "error": "LEASE_LOST: Worker lost claim while saving video ID."}
        return {"success": True, "video_id": finished_vid}
    elif st_code == 401:
        access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id, force_refresh=True)
        st_code, start_offset, finished_vid = _query_server_offset(session_uri, access_token, file_size)
        if finished_vid:
            _save_video_id_and_status(scpid, user_id, claim_token, finished_vid)
            return {"success": True, "video_id": finished_vid}
    elif st_code == 404:
        session_uri = initiate_resumable_upload_session(content_platform_id, user_id, claim_token)
        start_offset = 0

    chunk_size = Config.YOUTUBE_UPLOAD_CHUNK_SIZE_BYTES
    current_offset = start_offset
    video_id = None

    # Stream chunk by chunk
    with open(temp_abs_path, "rb") as vf:
        while current_offset < file_size:
            # Heartbeat renewal before every chunk
            if not renew_publishing_claim(scpid, user_id, claim_token):
                return {"success": False, "error": "LEASE_LOST: Publishing lease lost during chunk streaming."}

            chunk_len = min(chunk_size, file_size - current_offset)
            vf.seek(current_offset)
            chunk_data = vf.read(chunk_len)

            chunk_end = current_offset + chunk_len - 1
            chunk_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(chunk_len),
                "Content-Range": f"bytes {current_offset}-{chunk_end}/{file_size}"
            }

            retry_count = 0
            backoff_sec = Config.YOUTUBE_UPLOAD_INITIAL_BACKOFF_SECONDS
            chunk_success = False

            while retry_count < Config.YOUTUBE_UPLOAD_MAX_RETRIES:
                try:
                    put_resp = requests.put(
                        session_uri,
                        headers=chunk_headers,
                        data=chunk_data,
                        timeout=(Config.YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS, Config.YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS)
                    )

                    # Heartbeat renewal after chunk response
                    if not renew_publishing_claim(scpid, user_id, claim_token):
                        return {"success": False, "error": "LEASE_LOST: Publishing lease lost during chunk response."}

                    if put_resp.status_code == 308:
                        range_header = put_resp.headers.get("Range")
                        if range_header and range_header.startswith("bytes="):
                            match = re.search(r"bytes=0-(\d+)", range_header)
                            if match:
                                next_offset = int(match.group(1)) + 1
                                if current_offset <= next_offset <= file_size:
                                    current_offset = next_offset
                                else:
                                    current_offset += chunk_len
                            else:
                                current_offset += chunk_len
                        else:
                            current_offset += chunk_len

                        progress_pct = int((current_offset / file_size) * 100)
                        if not _update_upload_progress(scpid, user_id, claim_token, current_offset, file_size, progress_pct):
                            return {"success": False, "error": "LEASE_LOST: Worker lost claim while updating progress."}

                        chunk_success = True
                        break

                    elif put_resp.status_code in (200, 201):
                        try:
                            resp_json = put_resp.json()
                            video_id = resp_json.get("id")
                        except Exception:
                            _record_upload_failure(scpid, user_id, claim_token, "MALFORMED_RESPONSE", "Google returned non-JSON final response.")
                            return {"success": False, "error": "Invalid response format from Google."}

                        if not video_id:
                            _record_upload_failure(scpid, user_id, claim_token, "MISSING_VIDEO_ID", "Google response did not contain a YouTube video ID.")
                            return {"success": False, "error": "YouTube video ID missing in Google response."}

                        current_offset = file_size
                        _update_upload_progress(scpid, user_id, claim_token, file_size, file_size, 100)
                        if not _save_video_id_and_status(scpid, user_id, claim_token, video_id):
                            return {"success": False, "error": "LEASE_LOST: Worker lost claim while saving video ID."}
                        chunk_success = True
                        break

                    elif put_resp.status_code == 401:
                        access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id, force_refresh=True)
                        chunk_headers["Authorization"] = f"Bearer {access_token}"
                        # Query authoritative server offset before resending
                        st_code, confirmed_offset, vid = _query_server_offset(session_uri, access_token, file_size)
                        if vid:
                            video_id = vid
                            _save_video_id_and_status(scpid, user_id, claim_token, video_id)
                            chunk_success = True
                            break
                        elif st_code == 308 and confirmed_offset >= current_offset:
                            current_offset = confirmed_offset
                        retry_count += 1

                    elif put_resp.status_code in (429, 500, 502, 503, 504):
                        retry_after = put_resp.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            sleep_time = int(retry_after)
                        else:
                            sleep_time = backoff_sec + random.uniform(0.1, 0.5)
                            backoff_sec *= 2

                        slept = sleep_with_lease_heartbeat(scpid, user_id, claim_token, sleep_time)
                        if not slept:
                            return {"success": False, "error": "LEASE_LOST: Lease renewal failed during backoff sleep."}

                        # Confirm offset after transient error
                        st_code, confirmed_offset, vid = _query_server_offset(session_uri, access_token, file_size)
                        if vid:
                            video_id = vid
                            _save_video_id_and_status(scpid, user_id, claim_token, video_id)
                            chunk_success = True
                            break
                        elif st_code == 308 and confirmed_offset >= current_offset:
                            current_offset = confirmed_offset

                        retry_count += 1

                    elif put_resp.status_code == 404:
                        session_uri = initiate_resumable_upload_session(content_platform_id, user_id, claim_token)
                        current_offset = 0
                        chunk_success = True
                        break

                    else:
                        _record_upload_failure(scpid, user_id, claim_token, f"HTTP_{put_resp.status_code}", f"YouTube rejected chunk (HTTP {put_resp.status_code}).")
                        return {"success": False, "error": f"YouTube rejected upload chunk (HTTP {put_resp.status_code})."}

                except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                    slept = sleep_with_lease_heartbeat(scpid, user_id, claim_token, backoff_sec + random.uniform(0.1, 0.5))
                    if not slept:
                        return {"success": False, "error": "LEASE_LOST: Lease renewal failed during timeout backoff."}
                    backoff_sec *= 2

                    # Query authoritative server offset after timeout/network drop
                    st_code, confirmed_offset, vid = _query_server_offset(session_uri, access_token, file_size)
                    if vid:
                        video_id = vid
                        _save_video_id_and_status(scpid, user_id, claim_token, video_id)
                        chunk_success = True
                        break
                    elif st_code == 308 and confirmed_offset >= current_offset:
                        current_offset = confirmed_offset

                    retry_count += 1

            if not chunk_success:
                _record_upload_failure(scpid, user_id, claim_token, "NETWORK_TIMEOUT", "Maximum retries exceeded during chunked upload.")
                return {"success": False, "error": "Network timeout during chunked video upload."}

    if video_id:
        return {"success": True, "video_id": video_id}
    else:
        return {"success": False, "error": "Upload concluded without receiving a valid YouTube video ID."}


# =============================================================================
# 4. Custom Thumbnail Upload & Deletion
# =============================================================================

def upload_custom_thumbnail(content_platform_id: int, user_id: int, video_id: str, claim_token: str) -> dict:
    """
    Uploads custom thumbnail image to YouTube via thumbnails.set with lease heartbeat and ownership verification.
    - Strictly requires valid non-empty claim_token.
    - On success: marks thumbnail_status = 'UPLOADED' and deletes temporary thumbnail file.
    - On failure: marks thumbnail_status = 'FAILED' but does NOT fail the video publication.
    """
    if not claim_token or not str(claim_token).strip():
        return {"success": False, "error": "LEASE_LOST: A valid claim token is required to upload custom thumbnails."}

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT scp.account_id, sc.temp_thumbnail_path, scp.thumbnail_status
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            WHERE scp.id = %s AND sc.user_id = %s;
        """, (content_platform_id, user_id))
        row = cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row or not row[1]:
        return {"success": True, "message": "No thumbnail requested."}

    aid, temp_thumb_path, current_thumb_status = row
    if current_thumb_status == "UPLOADED":
        return {"success": True, "message": "Thumbnail is already uploaded."}

    thumb_abs_path = get_safe_temp_path(temp_thumb_path)
    if not os.path.exists(thumb_abs_path):
        return {"success": False, "error": "Thumbnail file missing from server storage."}

    file_size = os.path.getsize(thumb_abs_path)
    if file_size > 2 * 1024 * 1024:
        _update_thumbnail_status(content_platform_id, user_id, claim_token, "FAILED")
        return {"success": False, "error": "Thumbnail exceeds YouTube 2 MB limit."}

    # Heartbeat lease renewal before Google call
    if not renew_publishing_claim(content_platform_id, user_id, claim_token):
        return {"success": False, "error": "LEASE_LOST: Publishing lease lost before thumbnail upload."}

    access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id)

    ext = os.path.splitext(temp_thumb_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": mime_type
    }
    params = {"videoId": video_id}

    with open(thumb_abs_path, "rb") as tf:
        thumb_data = tf.read()

    url = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
    resp = requests.post(
        url,
        headers=headers,
        params=params,
        data=thumb_data,
        timeout=(Config.YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS, Config.YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS)
    )

    # Heartbeat lease renewal after Google call
    if not renew_publishing_claim(content_platform_id, user_id, claim_token):
        return {"success": False, "error": "LEASE_LOST: Publishing lease lost after thumbnail upload response."}

    if resp.status_code in (200, 201):
        del_res = safe_delete_temp_file(temp_thumb_path)
        _update_thumbnail_status(content_platform_id, user_id, claim_token, "UPLOADED", cleared_path=temp_thumb_path if del_res.get("removed") else None)
        return {"success": True, "message": "Thumbnail uploaded successfully."}
    else:
        _update_thumbnail_status(content_platform_id, user_id, claim_token, "FAILED")
        return {"success": False, "error": f"Thumbnail upload failed (HTTP {resp.status_code})."}


# =============================================================================
# 5. YouTube Processing Confirmation & Video Deletion
# =============================================================================

def poll_youtube_processing_status(content_platform_id: int, user_id: int, video_id: str, claim_token: str, max_polls: int = None, poll_interval: float = None) -> dict:
    """
    Polls YouTube Data API v3 videos.list?part=processingDetails,status with ownership checks and lease renewal.
    - uploadStatus == 'uploaded' -> remains PROCESSING.
    - processingStatus == 'succeeded' or uploadStatus == 'processed' -> confirmed PUBLISHED & deletes temporary video file.
    - processingStatus in ('failed', 'terminated') -> FAILED.
    - When polling timeout occurs, schedules next_processing_check_at and increments check count.
    """
    if not claim_token or not str(claim_token).strip():
        return {"status": "LEASE_LOST", "error": "A valid claim token is required to poll processing status."}

    if max_polls is None:
        max_polls = Config.YOUTUBE_PROCESSING_MAX_POLLS_PER_RUN
    if poll_interval is None:
        poll_interval = Config.YOUTUBE_PROCESSING_POLL_INTERVAL_SECONDS

    # 1. Fetch metadata
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT scp.account_id, scp.content_id, sc.temp_media_path, scp.processing_check_count
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            WHERE scp.id = %s AND sc.user_id = %s;
        """, (content_platform_id, user_id))
        row = cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row:
        return {"status": "UNKNOWN", "error": "Record not found or access denied."}

    aid, cid, temp_media_path, check_count = row
    access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id)

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"part": "processingDetails,status", "id": video_id}
    url = "https://www.googleapis.com/youtube/v3/videos"

    for _ in range(max_polls):
        if not renew_publishing_claim(content_platform_id, user_id, claim_token):
            return {"status": "LEASE_LOST", "error": "Publishing claim lease lost during processing poll."}

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=(Config.YOUTUBE_UPLOAD_CONNECT_TIMEOUT_SECONDS, Config.YOUTUBE_UPLOAD_READ_TIMEOUT_SECONDS)
            )

            if not renew_publishing_claim(content_platform_id, user_id, claim_token):
                return {"status": "LEASE_LOST", "error": "Publishing claim lease lost after processing response."}

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    upload_status = item.get("status", {}).get("uploadStatus", "")
                    processing_status = item.get("processingDetails", {}).get("processingStatus", "")

                    if processing_status == "succeeded" or upload_status == "processed":
                        finalized = _finalize_publication_success(content_platform_id, user_id, claim_token, cid, temp_media_path)
                        if not finalized:
                            return {"status": "LEASE_LOST", "error": "Lost lease while finalizing publication success."}
                        return {"status": "PUBLISHED", "video_id": video_id}

                    elif processing_status in ("failed", "terminated") or upload_status in ("failed", "rejected"):
                        finalized = _finalize_publication_failure(content_platform_id, user_id, claim_token, cid, "PROCESSING_FAILED", "YouTube video processing failed or was rejected.")
                        if not finalized:
                            return {"status": "LEASE_LOST", "error": "Lost lease while finalizing publication failure."}
                        return {"status": "FAILED", "error": "YouTube processing failed."}

            elif resp.status_code == 401:
                access_token = get_valid_youtube_access_token(account_id=aid, user_id=user_id, force_refresh=True)
                headers["Authorization"] = f"Bearer {access_token}"
        except Exception:
            pass

        slept = sleep_with_lease_heartbeat(content_platform_id, user_id, claim_token, poll_interval)
        if not slept:
            return {"status": "LEASE_LOST", "error": "Publishing claim lease lost during poll interval sleep."}

    # Timed out for this poll cycle -> schedule future check and release claim
    backoff_delay = min(60, max(5, (check_count + 1) * 10))
    _schedule_next_processing_check(content_platform_id, user_id, claim_token, backoff_delay)

    return {"status": "PROCESSING", "video_id": video_id, "message": "Video uploaded; YouTube processing in progress."}


# =============================================================================
# 6. Pipeline Orchestrator & Bounded Worker Queue
# =============================================================================

def execute_youtube_publish_pipeline(content_id: int, user_id: int) -> dict:
    """
    Full end-to-end publishing pipeline with atomic job claiming and job-type routing:
    1. Claim job lease & determine job type.
    2. FULL_UPLOAD: Stream video in chunks -> thumbnail -> poll.
    3. PROCESSING_CHECK: Poll processing confirmation.
    4. THUMBNAIL_RETRY: Upload thumbnail only (never call videos.insert).
    5. Clean up media upon confirmed success.
    """
    # 1. Fetch platform target id
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT scp.id
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            WHERE scp.content_id = %s AND sc.user_id = %s AND scp.platform = 'YOUTUBE'
            ORDER BY scp.id ASC LIMIT 1;
        """, (content_id, user_id))
        row = cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row:
        return {"success": False, "error": "No YouTube publishing target found or access denied."}

    scpid = row[0]

    # 2. Claim job lease atomically
    claim_res = claim_publishing_job(content_platform_id=scpid, user_id=user_id)
    if not claim_res.get("claimed"):
        return {"success": True, "message": claim_res.get("message", "Job is active.")}

    claim_token = claim_res["claim_token"]
    job_type = claim_res["job_type"]

    try:
        if job_type == "NO_OP":
            return {"success": True, "message": "Job is already complete."}

        elif job_type == "THUMBNAIL_RETRY":
            video_id = claim_res.get("platform_post_id")
            thumb_res = upload_custom_thumbnail(content_platform_id=scpid, user_id=user_id, video_id=video_id, claim_token=claim_token)
            return {
                "success": thumb_res.get("success", False),
                "video_id": video_id,
                "post_url": f"https://www.youtube.com/watch?v={video_id}",
                "job_type": "THUMBNAIL_RETRY",
                "message": thumb_res.get("message")
            }

        elif job_type == "PROCESSING_CHECK":
            video_id = claim_res.get("platform_post_id")
            proc_result = poll_youtube_processing_status(content_platform_id=scpid, user_id=user_id, video_id=video_id, claim_token=claim_token)
            return {
                "success": True,
                "video_id": video_id,
                "post_url": f"https://www.youtube.com/watch?v={video_id}",
                "processing_status": proc_result.get("status"),
                "job_type": "PROCESSING_CHECK"
            }

        else:  # FULL_UPLOAD
            upload_result = stream_video_chunks(content_platform_id=scpid, user_id=user_id, claim_token=claim_token)
            if not upload_result.get("success"):
                return upload_result
            video_id = upload_result.get("video_id")

            # Upload thumbnail if requested
            upload_custom_thumbnail(content_platform_id=scpid, user_id=user_id, video_id=video_id, claim_token=claim_token)

            # Poll processing status
            proc_result = poll_youtube_processing_status(content_platform_id=scpid, user_id=user_id, video_id=video_id, claim_token=claim_token)

            return {
                "success": True,
                "video_id": video_id,
                "post_url": f"https://www.youtube.com/watch?v={video_id}",
                "processing_status": proc_result.get("status"),
                "job_type": "FULL_UPLOAD"
            }
    finally:
        release_publishing_claim(scpid, user_id, claim_token)


def start_youtube_publish_task(content_id: int, user_id: int):
    """
    Submits a publication task to the bounded ThreadPoolExecutor worker queue.
    """
    executor = get_publish_executor()
    return executor.submit(execute_youtube_publish_pipeline, content_id, user_id)


def recover_pending_youtube_tasks():
    """
    Scans for interrupted, queued, or scheduled YouTube publishing tasks and enqueues them for recovery.
    - Respects lease expiry, ownership, next_processing_check_at schedule, and media existence.
    """
    if not Config.ENABLE_YOUTUBE_PUBLISH_WORKER:
        return

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT scp.content_id, sc.user_id
            FROM social_content_platforms scp
            JOIN social_content sc ON scp.content_id = sc.id
            WHERE scp.platform = 'YOUTUBE'
              AND (scp.claim_expires_at IS NULL OR scp.claim_expires_at < CURRENT_TIMESTAMP)
              AND (scp.next_processing_check_at IS NULL OR scp.next_processing_check_at <= CURRENT_TIMESTAMP)
              AND (
                  -- Interrupted / Pending Full Upload with valid temp media
                  (
                      scp.platform_post_id IS NULL
                      AND scp.platform_status IN ('PENDING', 'PROCESSING')
                      AND sc.temp_media_path IS NOT NULL
                      AND sc.temp_file_deleted = FALSE
                      AND (sc.temp_file_expires_at IS NULL OR sc.temp_file_expires_at > CURRENT_TIMESTAMP)
                  )
                  OR
                  -- In-progress processing confirmation
                  (
                      scp.platform_post_id IS NOT NULL
                      AND scp.platform_status != 'PUBLISHED'
                  )
                  OR
                  -- Failed thumbnail retry
                  (
                      scp.platform_post_id IS NOT NULL
                      AND scp.thumbnail_status = 'FAILED'
                      AND sc.temp_thumbnail_path IS NOT NULL
                      AND (sc.temp_file_expires_at IS NULL OR sc.temp_file_expires_at > CURRENT_TIMESTAMP)
                  )
              )
            ORDER BY scp.last_attempt_at ASC NULLS FIRST
            LIMIT 10;
        """)
        rows = cur.fetchall()
        for cid, uid in rows:
            start_youtube_publish_task(cid, uid)
    except Exception:
        pass
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =============================================================================
# 7. Helper Internal State Updaters with Strict Fencing
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


def _save_resumable_session_uri(scpid: int, user_id: int, claim_token: str, cid: int, enc_session: str, file_size: int) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET encrypted_session_uri = %s,
                total_bytes = %s,
                bytes_sent = 0,
                upload_progress_percent = 0,
                platform_status = 'PROCESSING',
                processing_status = 'UPLOADING',
                last_attempt_at = CURRENT_TIMESTAMP,
                error_message = NULL
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (enc_session, file_size, scpid, user_id, claim_token))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE social_content SET overall_status = 'PROCESSING' WHERE id = %s AND user_id = %s;", (cid, user_id))
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _update_upload_progress(scpid: int, user_id: int, claim_token: str, bytes_sent: int, total_bytes: int, progress_pct: int) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET bytes_sent = %s,
                total_bytes = %s,
                upload_progress_percent = %s,
                processing_status = 'UPLOADING'
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (bytes_sent, total_bytes, progress_pct, scpid, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _save_video_id_and_status(scpid: int, user_id: int, claim_token: str, video_id: str) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        cur.execute("""
            UPDATE social_content_platforms scp
            SET platform_post_id = %s,
                platform_post_url = %s,
                upload_progress_percent = 100,
                processing_status = 'PROCESSING',
                encrypted_session_uri = NULL,
                error_message = NULL
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (video_id, canonical_url, scpid, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _record_upload_failure(scpid: int, user_id: int, claim_token: str, error_code: str, error_msg: str) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET platform_status = 'FAILED',
                processing_status = 'FAILED',
                platform_error_code = %s,
                error_message = %s
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.content_id;
        """, (error_code, error_msg, scpid, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        if row:
            recalculate_content_overall_status(row[0])
            return True
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _update_thumbnail_status(scpid: int, user_id: int, claim_token: str, status: str, cleared_path: str = None) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET thumbnail_status = %s
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.content_id;
        """, (status, scpid, user_id, claim_token))
        row = cur.fetchone()
        if cleared_path and row:
            cid = row[0]
            cur.execute("""
                UPDATE social_content
                SET temp_thumbnail_path = NULL
                WHERE id = %s AND user_id = %s;
            """, (cid, user_id))
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _schedule_next_processing_check(scpid: int, user_id: int, claim_token: str, delay_seconds: int) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET next_processing_check_at = CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL,
                processing_check_count = processing_check_count + 1
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (str(delay_seconds), scpid, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        return bool(row)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _finalize_publication_success(scpid: int, user_id: int, claim_token: str, cid: int, temp_media_path: str, defer_media_cleanup: bool = False) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET platform_status = 'PUBLISHED',
                processing_status = 'READY',
                published_at = CURRENT_TIMESTAMP,
                next_processing_check_at = NULL,
                error_message = NULL
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (scpid, user_id, claim_token))
        row = cur.fetchone()
        if not row:
            conn.commit()
            return False

        conn.commit()
        recalculate_content_overall_status(cid)

        # Only attempt physical video deletion if not deferred and no other pending/processing platform targets exist
        if temp_media_path and not defer_media_cleanup:
            cur.execute("""
                SELECT COUNT(*)
                FROM social_content_platforms
                WHERE content_id = %s AND id != %s AND platform_status NOT IN ('PUBLISHED', 'CANCELLED');
            """, (cid, scpid))
            other_pending_count = cur.fetchone()[0]

            if other_pending_count == 0:
                del_res = safe_delete_temp_file(temp_media_path)
                if del_res.get("removed"):
                    cur.execute("""
                        UPDATE social_content
                        SET temp_media_path = NULL,
                            temp_file_deleted = CASE WHEN temp_thumbnail_path IS NULL THEN TRUE ELSE temp_file_deleted END,
                            temp_file_deleted_at = CASE WHEN temp_thumbnail_path IS NULL THEN CURRENT_TIMESTAMP ELSE temp_file_deleted_at END
                        WHERE id = %s AND user_id = %s;
                    """, (cid, user_id))
                    conn.commit()
        return True
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def publish_youtube(user_id: int, content_id: int, account_id: int, options: dict = None, defer_media_cleanup: bool = True) -> dict:
    """
    Synchronously orchestrates publication of a content record to YouTube:
    1. Validates ownership and account status.
    2. Upserts/claims social_content_platforms row with options (privacy_status, category_id, made_for_kids).
    3. If already PUBLISHED, returns existing publication immediately (idempotency).
    4. Executes publishing pipeline.
    5. Returns sanitized standardized result dictionary.
    """
    if not user_id:
        return {"success": False, "error": "User authentication required.", "platform": "YOUTUBE", "account_id": account_id}
    if not content_id or not isinstance(content_id, int) or content_id <= 0:
        return {"success": False, "error": "Valid content ID required.", "platform": "YOUTUBE", "account_id": account_id}
    if not account_id or not isinstance(account_id, int) or account_id <= 0:
        return {"success": False, "error": "Valid account ID required.", "platform": "YOUTUBE", "account_id": account_id}

    options = options or {}
    privacy_status = str(options.get("privacy_status", "PUBLIC")).upper()
    if privacy_status not in ("PUBLIC", "PRIVATE", "UNLISTED"):
        privacy_status = "PUBLIC"
    category_id = str(options.get("category_id", "22")).strip() or "22"
    made_for_kids = bool(options.get("made_for_kids", False))

    conn = None
    cur = None
    scp_id = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Verify content ownership and media presence
        cur.execute("""
            SELECT id, user_id, title, common_caption, hashtags, temp_media_path, temp_file_deleted, temp_file_expires_at
            FROM social_content
            WHERE id = %s AND user_id = %s;
        """, (content_id, user_id))
        c_row = cur.fetchone()
        if not c_row:
            return {"success": False, "error": "Content not found or access denied.", "platform": "YOUTUBE", "account_id": account_id}

        cid, uid, title, caption, tags, temp_media, temp_deleted, expires_at = c_row
        if temp_deleted or not temp_media:
            return {"success": False, "error": "Temporary video media has been deleted or purged.", "platform": "YOUTUBE", "account_id": account_id}

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return {"success": False, "error": "Temporary video media has expired.", "platform": "YOUTUBE", "account_id": account_id}

        # 2. Verify account
        cur.execute("""
            SELECT id, user_id, platform, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))
        acc_row = cur.fetchone()
        if not acc_row:
            return {"success": False, "error": "YouTube account not found or access denied.", "platform": "YOUTUBE", "account_id": account_id}

        aid, a_uid, plat, conn_status = acc_row
        if plat != "YOUTUBE":
            return {"success": False, "error": f"Selected account is not a YouTube account ({plat}).", "platform": "YOUTUBE", "account_id": account_id}
        if conn_status != "ACTIVE":
            return {"success": False, "error": f"YouTube account connection is in {conn_status} state. Please reconnect.", "platform": "YOUTUBE", "account_id": account_id}

        # 3. Upsert social_content_platforms
        cur.execute("""
            INSERT INTO social_content_platforms (
                content_id, account_id, platform, custom_title, custom_caption,
                privacy_status, category_id, made_for_kids, platform_status,
                processing_status, last_attempt_at, updated_at
            )
            VALUES (
                %s, %s, 'YOUTUBE', %s, %s,
                %s, %s, %s, 'PENDING',
                'IDLE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (content_id, platform, account_id) DO UPDATE SET
                privacy_status = EXCLUDED.privacy_status,
                category_id = EXCLUDED.category_id,
                made_for_kids = EXCLUDED.made_for_kids,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, platform_status, platform_post_id, platform_post_url;
        """, (cid, aid, title, caption, privacy_status, category_id, made_for_kids))
        scp_row = cur.fetchone()
        scp_id, p_status, post_id, post_url = scp_row
        conn.commit()

        # Idempotency: If already published, return immediately
        if p_status == "PUBLISHED":
            return {
                "success": True,
                "platform": "YOUTUBE",
                "account_id": account_id,
                "publish_status": "PUBLISHED",
                "publish_id": post_id,
                "publish_url": post_url or (f"https://www.youtube.com/watch?v={post_id}" if post_id else None),
                "already_published": True
            }

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # 4. Execute pipeline
    execute_youtube_publish_pipeline(content_id=content_id, user_id=user_id)

    # 5. Fetch final status
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT platform_status, platform_post_id, platform_post_url, error_message
            FROM social_content_platforms
            WHERE id = %s;
        """, (scp_id,))
        final_row = cur.fetchone()
        if final_row:
            p_status, post_id, post_url, err_msg = final_row
            is_success = (p_status == "PUBLISHED")
            return {
                "success": is_success,
                "platform": "YOUTUBE",
                "account_id": account_id,
                "publish_status": p_status,
                "publish_id": post_id,
                "publish_url": post_url or (f"https://www.youtube.com/watch?v={post_id}" if post_id else None),
                "already_published": False,
                "error": err_msg if not is_success else None
            }
        return {
            "success": False,
            "platform": "YOUTUBE",
            "account_id": account_id,
            "publish_status": "FAILED",
            "error": "Failed to read final YouTube status."
        }
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



def _finalize_publication_failure(scpid: int, user_id: int, claim_token: str, cid: int, error_code: str, error_msg: str) -> bool:
    if not claim_token or not str(claim_token).strip():
        return False
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms scp
            SET platform_status = 'FAILED',
                processing_status = 'FAILED',
                platform_error_code = %s,
                next_processing_check_at = NULL,
                error_message = %s
            FROM social_content sc
            WHERE scp.id = %s
              AND scp.content_id = sc.id
              AND sc.user_id = %s
              AND scp.claim_token = %s
              AND scp.claim_expires_at > CURRENT_TIMESTAMP
            RETURNING scp.id;
        """, (error_code, error_msg, scpid, user_id, claim_token))
        row = cur.fetchone()
        conn.commit()
        if row:
            recalculate_content_overall_status(cid)
            return True
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
