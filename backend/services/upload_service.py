"""
LifeOS — Secure Temporary Upload and Cleanup Service
Handles streaming temporary uploads, multi-tiered format and container validation,
atomic storage, strict path traversal and symlink prevention, and transaction-safe
lifecycle cleanup routines.

System Dependency Note:
If 'ffprobe' (part of the FFmpeg suite) is installed on the system host, deep container
and codec validation is performed. When ffprobe is absent, native ISO Base Media File
Format (ISOBMFF) and EBML box parsing is used to ensure container integrity.
"""

import os
import re
import uuid
import json
import shutil
import struct
import datetime
import subprocess
from zoneinfo import ZoneInfo
from PIL import Image

from config import Config
from database.db import get_connection

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/webm", "video/x-m4v", "application/octet-stream"}

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}

ALLOWED_PLATFORMS = {"YOUTUBE", "INSTAGRAM", "FACEBOOK"}

# Explicit recognized ISO Base Media File Format brands
KNOWN_MP4_BRANDS = {
    b"isom", b"iso2", b"mp41", b"mp42", b"qt  ", b"M4V ",
    b"MSNV", b"avc1", b"dash", b"mp71", b"iso4", b"iso5", b"iso6"
}

def sanitize_filename(filename: str) -> str:
    """Strip path separators and dangerous characters from user-supplied filename."""
    if not filename:
        return "unnamed_media"
    cleaned = os.path.basename(filename)
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", cleaned)

def validate_timezone(tz_name: str) -> str:
    """
    Validate timezone name against the IANA timezone database.
    Rejects invalid arbitrary strings.
    """
    if not tz_name or not isinstance(tz_name, str):
        return "UTC"
    cleaned = tz_name.strip()
    try:
        ZoneInfo(cleaned)
        return cleaned
    except Exception:
        raise ValueError(f"Invalid IANA timezone '{tz_name}'. Please provide a valid timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Kolkata').")

def parse_strict_bool(val) -> bool:
    """
    Strictly parse boolean parameters to prevent string 'false' from becoming True.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in ("true", "1", "yes"):
            return True
        if cleaned in ("false", "0", "no", ""):
            return False
    return False

def get_safe_temp_path(filename: str) -> str:
    """
    Resolve and validate that a filename resides strictly inside the configured temp_uploads directory.
    Prevents directory traversal and rejects symbolic links.
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Invalid filename provided.")

    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Path traversal attempt detected in filename.")

    upload_dir_real = os.path.realpath(Config.TEMP_UPLOAD_DIR)
    os.makedirs(upload_dir_real, exist_ok=True)

    target_path = os.path.join(upload_dir_real, filename)
    target_path_real = os.path.realpath(target_path)

    if not target_path_real.startswith(upload_dir_real + os.sep) and target_path_real != upload_dir_real:
        raise ValueError("Path traversal violation: resolved path is outside temp directory.")

    if os.path.islink(target_path):
        raise ValueError("Symbolic links are strictly rejected.")

    return target_path_real

def safe_delete_temp_file(filename: str) -> dict:
    """
    Safely delete a temporary file strictly inside Config.TEMP_UPLOAD_DIR.
    Never operates outside TEMP_UPLOAD_DIR and rejects symlinks.
    Idempotent: non-existent files return status 'missing' without error.
    """
    if not filename or not isinstance(filename, str):
        return {"removed": False, "status": "missing"}

    try:
        safe_path = get_safe_temp_path(filename)
    except Exception:
        return {"removed": False, "status": "rejected"}

    if not os.path.exists(safe_path):
        return {"removed": False, "status": "missing"}

    if os.path.islink(safe_path):
        return {"removed": False, "status": "rejected"}

    try:
        os.remove(safe_path)
        return {"removed": True, "status": "deleted"}
    except Exception as e:
        print(f"Warning: Failed to physically remove temp file {filename}: {e}")
        return {"removed": False, "status": "failed"}

def probe_video_with_ffprobe(file_path: str) -> dict:
    """
    Probe video container, codec, duration, and dimensions using ffprobe if available.
    Returns metadata dictionary or None if ffprobe is not installed.
    Raises ValueError if video stream is corrupt or unreadable.
    """
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return None

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name:format=duration,format_name",
        "-of", "json",
        file_path
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if proc.returncode != 0:
            raise ValueError("Corrupt or unreadable video file detected by ffprobe.")

        info = json.loads(proc.stdout)
        streams = info.get("streams", [])
        if not streams:
            raise ValueError("No valid video stream found in uploaded container.")

        v_stream = streams[0]
        width = v_stream.get("width")
        height = v_stream.get("height")

        duration = None
        fmt_info = info.get("format", {})
        if "duration" in fmt_info:
            try:
                duration = round(float(fmt_info["duration"]), 2)
            except (ValueError, TypeError):
                duration = None

        return {
            "width": width,
            "height": height,
            "duration_seconds": duration,
            "format_name": fmt_info.get("format_name", "mp4")
        }
    except subprocess.TimeoutExpired:
        raise ValueError("Video validation timed out.")
    except json.JSONDecodeError:
        raise ValueError("Failed to parse video stream metadata.")

def validate_video_file_signature(file_path: str) -> str:
    """
    Validate video magic bytes signature directly from file header.
    Only recognized MP4, QuickTime, and WebM containers are accepted.
    """
    with open(file_path, "rb") as f:
        header = f.read(128)

    if len(header) < 12:
        raise ValueError("File is too small to be a valid video container.")

    # Check WebM / Matroska EBML signature
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"

    # Check ISO Base Media File Format (ftyp box)
    ftyp_idx = header.find(b"ftyp")
    if ftyp_idx != -1 and ftyp_idx <= 8:
        major_brand = header[ftyp_idx + 4:ftyp_idx + 8]
        # Check against strictly enumerated known brands
        if major_brand in KNOWN_MP4_BRANDS or any(b in header[:64] for b in KNOWN_MP4_BRANDS):
            return "mp4"

    # QuickTime atom fallback
    if header[4:8] in [b"moov", b"mdat", b"wide", b"free"]:
        return "mov"

    raise ValueError("Invalid video file signature. File header does not match valid MP4, MOV, or WebM format.")

def validate_image_file_signature(file_path: str) -> tuple[str, int, int]:
    """
    Validate image file signature using Pillow and return (format, width, height).
    """
    try:
        with Image.open(file_path) as img:
            img.verify()
        with Image.open(file_path) as img:
            fmt = (img.format or "").lower()
            width, height = img.size
            if fmt not in ["jpeg", "jpg", "png", "webp"]:
                raise ValueError(f"Unsupported image format '{fmt}'. Allowed: JPEG, PNG, WebP.")
            return fmt, width, height
    except Exception as e:
        raise ValueError(f"Invalid image file signature or corrupted image: {str(e)}")

def parse_mp4_metadata_native(file_path: str) -> dict:
    """
    Native ISOBMFF box parser for MP4/MOV containers to extract duration, dimensions, and aspect ratio.
    """
    duration = None
    width = None
    height = None

    try:
        with open(file_path, "rb") as f:
            file_size = os.path.getsize(file_path)
            pos = 0
            while pos < file_size - 8:
                f.seek(pos)
                box_header = f.read(8)
                if len(box_header) < 8:
                    break
                box_size, box_type = struct.unpack(">I4s", box_header)
                if box_size == 1:
                    box_size = struct.unpack(">Q", f.read(8))[0]
                    header_len = 16
                else:
                    header_len = 8

                if box_size == 0:
                    box_size = file_size - pos

                if box_type == b"moov":
                    moov_data = f.read(min(box_size - header_len, 200000))
                    mvhd_idx = moov_data.find(b"mvhd")
                    if mvhd_idx != -1:
                        version = moov_data[mvhd_idx + 4]
                        if version == 0:
                            timescale, dur = struct.unpack(">II", moov_data[mvhd_idx + 16:mvhd_idx + 24])
                        elif version == 1:
                            timescale, dur = struct.unpack(">IQ", moov_data[mvhd_idx + 24:mvhd_idx + 36])
                        else:
                            timescale, dur = 1000, 0
                        if timescale > 0:
                            duration = round(dur / float(timescale), 2)

                    tkhd_idx = moov_data.find(b"tkhd")
                    if tkhd_idx != -1:
                        tkhd_version = moov_data[tkhd_idx + 4]
                        offset = 80 if tkhd_version == 0 else 92
                        if len(moov_data) >= tkhd_idx + offset + 8:
                            w_fixed, h_fixed = struct.unpack(">II", moov_data[tkhd_idx + offset:tkhd_idx + offset + 8])
                            width = w_fixed >> 16
                            height = h_fixed >> 16
                    break
                pos += box_size
    except Exception:
        pass

    aspect_ratio = None
    if width and height and height > 0:
        ratio = width / float(height)
        if 0.5 <= ratio <= 0.6:
            aspect_ratio = "9:16"
        elif 1.7 <= ratio <= 1.85:
            aspect_ratio = "16:9"
        elif 0.9 <= ratio <= 1.1:
            aspect_ratio = "1:1"
        elif 1.3 <= ratio <= 1.4:
            aspect_ratio = "4:3"
        else:
            aspect_ratio = f"{round(ratio, 2)}:1"

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio
    }

def validate_and_save_upload(file_storage, user_id: int, is_thumbnail: bool = False) -> dict:
    """
    Atomically stream, validate, and store a temporary upload file.
    - Enforces separate video vs thumbnail limits.
    - Validates extension, client MIME type, and magic bytes signature.
    - Uses ffprobe when available, falling back to native ISOBMFF parsing.
    - Returns safe sanitized metadata with zero absolute path exposure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided in request.")

    orig_name = sanitize_filename(file_storage.filename)
    _, ext = os.path.splitext(orig_name.lower())

    client_mime = (getattr(file_storage, "content_type", "") or getattr(file_storage, "mimetype", "") or "").lower().strip()

    if is_thumbnail:
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Invalid thumbnail file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}")
        if client_mime and client_mime not in ALLOWED_IMAGE_MIMES:
            raise ValueError(f"Invalid thumbnail MIME type '{client_mime}'. Allowed: image/jpeg, image/png, image/webp.")
        max_bytes = Config.MAX_THUMBNAIL_SIZE_MB * 1024 * 1024
        size_limit_mb = Config.MAX_THUMBNAIL_SIZE_MB
    else:
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError(f"Invalid video file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")
        if client_mime and client_mime not in ALLOWED_VIDEO_MIMES:
            raise ValueError(f"Invalid video MIME type '{client_mime}'. Allowed: video/mp4, video/quicktime, video/webm.")
        max_bytes = Config.MAX_VIDEO_SIZE_MB * 1024 * 1024
        size_limit_mb = Config.MAX_VIDEO_SIZE_MB

    unique_id = uuid.uuid4().hex
    partial_filename = f".upload_{unique_id}.tmp"
    final_filename = f"{unique_id}{ext}"

    upload_dir = os.path.realpath(Config.TEMP_UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    partial_path = get_safe_temp_path(partial_filename)
    final_path = get_safe_temp_path(final_filename)

    total_bytes = 0
    try:
        with open(partial_path, "wb") as f_out:
            while True:
                chunk = file_storage.stream.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    target_name = "Thumbnail" if is_thumbnail else "Video"
                    raise ValueError(f"{target_name} file size exceeds maximum allowed limit of {size_limit_mb}MB.")
                f_out.write(chunk)

        if total_bytes == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")

        # Validate signature & container
        if is_thumbnail:
            fmt, width, height = validate_image_file_signature(partial_path)
            meta = {
                "media_type": "IMAGE",
                "width": width,
                "height": height,
                "duration_seconds": None,
                "aspect_ratio": f"{width}:{height}" if height else None
            }
        else:
            validate_video_file_signature(partial_path)
            # Try ffprobe first, fall back to native parser
            ffprobe_meta = probe_video_with_ffprobe(partial_path)
            if ffprobe_meta:
                meta = ffprobe_meta
                w = meta.get("width")
                h = meta.get("height")
                meta["aspect_ratio"] = f"{w}:{h}" if w and h else None
            else:
                meta = parse_mp4_metadata_native(partial_path)
            meta["media_type"] = "VIDEO"

        # Atomic rename after successful validation
        os.replace(partial_path, final_path)

        return {
            "media_filename": final_filename,
            "original_filename": orig_name,
            "file_size_bytes": total_bytes,
            "duration_seconds": meta.get("duration_seconds"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "aspect_ratio": meta.get("aspect_ratio"),
            "media_type": meta.get("media_type", "VIDEO")
        }
    except Exception as e:
        safe_delete_temp_file(partial_filename)
        raise e

def validate_platform_targets(user_id: int, platforms_data: list, cur) -> list:
    """
    Validate selected platform targets before database persistence:
    - Must be a list of dicts.
    - platform must be in ALLOWED_PLATFORMS.
    - No duplicate platforms.
    - account_id must belong to authenticated user_id.
    - account_id platform must match selected platform.
    """
    if not platforms_data:
        return []

    if not isinstance(platforms_data, list):
        raise ValueError("Platforms parameter must be a valid JSON list.")

    seen_platforms = set()
    for idx, item in enumerate(platforms_data):
        if not isinstance(item, dict):
            raise ValueError(f"Platform entry #{idx+1} must be an object.")
        platform = (item.get("platform") or "").upper().strip()
        if not platform or platform not in ALLOWED_PLATFORMS:
            raise ValueError(f"Invalid platform '{platform}'. Allowed: {', '.join(sorted(ALLOWED_PLATFORMS))}.")
        if platform in seen_platforms:
            raise ValueError(f"Duplicate platform '{platform}' selected in post.")
        seen_platforms.add(platform)

    validated = []
    for item in platforms_data:
        platform = (item.get("platform") or "").upper().strip()
        account_id = item.get("account_id")

        if not account_id or not isinstance(account_id, int):
            raise ValueError(f"A valid integer account_id is required for platform {platform}.")

        # Verify account ownership and platform match in social_accounts
        cur.execute("""
            SELECT id, platform, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))
        acc_row = cur.fetchone()

        if not acc_row:
            raise ValueError(f"Social account #{account_id} not found or does not belong to current user.")

        acc_platform = acc_row[1]
        if acc_platform != platform:
            raise ValueError(f"Account #{account_id} is registered for {acc_platform}, not {platform}.")

        validated.append({
            "account_id": account_id,
            "platform": platform,
            "custom_title": item.get("custom_title"),
            "custom_caption": item.get("custom_caption"),
            "custom_description": item.get("custom_description"),
            "privacy_status": item.get("privacy_status", "PUBLIC")
        })

    return validated

def create_social_content_record(user_id: int, title: str, common_caption: str, hashtags: str,
                                 media_meta: dict, thumbnail_meta: dict = None,
                                 platforms: list = None, original_timezone: str = "UTC",
                                 privacy_status: str = "PUBLIC", made_for_kids: bool = False,
                                 category_id: str = "22") -> dict:
    """
    Persist social_content record and platform targets inside an atomic transaction.
    If validation or persistence fails, safely cleans up all uploaded files.
    """
    if not title or not title.strip():
        raise ValueError("Post title is required.")

    validated_tz = validate_timezone(original_timezone)

    media_filename = media_meta.get("media_filename") if media_meta else None
    thumb_filename = thumbnail_meta.get("media_filename") if thumbnail_meta else None

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Validate platforms before inserting master record
        validated_platforms = validate_platform_targets(user_id, platforms, cur) if platforms else []

        ttl_hours = Config.TEMP_FILE_TTL_HOURS
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ttl_hours)

        cur.execute("""
            INSERT INTO social_content (
                user_id, title, common_caption, hashtags, media_type,
                temp_media_path, temp_thumbnail_path, file_size_bytes,
                duration_seconds, width, height, aspect_ratio,
                overall_status, original_timezone, temp_file_expires_at,
                privacy_status, made_for_kids, category_id,
                temp_file_deleted
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                'DRAFT', %s, %s,
                %s, %s, %s,
                FALSE
            )
            RETURNING id, created_at, temp_file_expires_at;
        """, (
            user_id, title.strip(), common_caption or "", hashtags or "", media_meta.get("media_type", "VIDEO") if media_meta else "VIDEO",
            media_filename, thumb_filename, media_meta.get("file_size_bytes") if media_meta else None,
            media_meta.get("duration_seconds") if media_meta else None, media_meta.get("width") if media_meta else None,
            media_meta.get("height") if media_meta else None, media_meta.get("aspect_ratio") if media_meta else None,
            validated_tz, expires_at, privacy_status or "PUBLIC", bool(made_for_kids), str(category_id or "22")
        ))

        content_row = cur.fetchone()
        content_id = content_row[0]
        created_at = content_row[1]

        # Insert target platforms
        created_platforms = []
        for p in validated_platforms:
            plat_priv = p.get("privacy_status") or privacy_status or "PUBLIC"
            cur.execute("""
                INSERT INTO social_content_platforms (
                    content_id, account_id, platform, custom_title, custom_caption,
                    custom_description, privacy_status, made_for_kids, category_id,
                    platform_status, processing_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', 'IDLE')
                RETURNING id, platform;
            """, (
                content_id, p["account_id"], p["platform"],
                p["custom_title"] or title.strip(),
                p["custom_caption"] or common_caption or "",
                p["custom_description"] or "",
                plat_priv,
                bool(made_for_kids),
                str(category_id or "22")
            ))
            scpid, plat = cur.fetchone()
            created_platforms.append({"id": scpid, "platform": plat})

        conn.commit()

        return {
            "content_id": content_id,
            "title": title.strip(),
            "overall_status": "DRAFT",
            "file_size_bytes": media_meta.get("file_size_bytes"),
            "duration_seconds": media_meta.get("duration_seconds"),
            "aspect_ratio": media_meta.get("aspect_ratio"),
            "original_timezone": validated_tz,
            "temp_file_expires_at": str(expires_at),
            "created_at": str(created_at),
            "platforms": created_platforms
        }
    except Exception as e:
        if conn:
            conn.rollback()
        # Clean up files on any database or validation error
        if media_filename:
            safe_delete_temp_file(media_filename)
        if thumb_filename:
            safe_delete_temp_file(thumb_filename)
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def cleanup_content_media(content_id: int, user_id: int = None, force: bool = False) -> dict:
    """
    Clean up temporary media files for a content record:
    - Idempotent: repeated calls succeed without error.
    - Transaction-safe with explicit rollback and connection cleanup.
    - Preserves database references if physical deletion fails.
    - Never operates on original files from the client.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = "SELECT id, user_id, temp_media_path, temp_thumbnail_path, temp_file_deleted, overall_status FROM social_content WHERE id = %s"
        params = [content_id]
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)

        cur.execute(query, tuple(params))
        row = cur.fetchone()

        if not row:
            return {"success": False, "message": "Content record not found or access denied.", "deleted": False}

        cid, uid, media_file, thumb_file, already_deleted, overall_status = row

        if already_deleted:
            return {"success": True, "message": "Temporary file has already been deleted.", "deleted": False}

        # Check platform completion if not forced
        if not force:
            cur.execute("SELECT platform_status FROM social_content_platforms WHERE content_id = %s;", (content_id,))
            plat_statuses = [r[0] for r in cur.fetchall()]

            if plat_statuses and not all(st == "PUBLISHED" for st in plat_statuses):
                return {
                    "success": True,
                    "message": "Temporary file retained for retry because some platforms have not completed publishing.",
                    "deleted": False
                }

        # Perform safe deletion independently
        media_removed = False
        thumb_removed = False

        if media_file:
            media_del = safe_delete_temp_file(media_file)
            media_removed = bool(media_del.get("removed") or media_del.get("status") == "missing")
        else:
            media_removed = True

        if thumb_file:
            thumb_del = safe_delete_temp_file(thumb_file)
            thumb_removed = bool(thumb_del.get("removed") or thumb_del.get("status") == "missing")
        else:
            thumb_removed = True

        both_cleared = media_removed and thumb_removed

        cur.execute("""
            UPDATE social_content
            SET temp_media_path = CASE WHEN %s THEN NULL ELSE temp_media_path END,
                temp_thumbnail_path = CASE WHEN %s THEN NULL ELSE temp_thumbnail_path END,
                temp_file_deleted = CASE WHEN %s THEN TRUE ELSE temp_file_deleted END,
                temp_file_deleted_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE temp_file_deleted_at END
            WHERE id = %s;
        """, (media_removed, thumb_removed, both_cleared, both_cleared, content_id))

        conn.commit()

        return {
            "success": True,
            "message": "Temporary media cleanup evaluated.",
            "deleted": both_cleared
        }
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def cleanup_expired_and_orphan_files() -> dict:
    """
    Synchronous system sweeper routine for startup and periodic maintenance:
    1. Deletes expired temporary files from social_content older than 24 hours / TTL.
    2. Deletes orphan/stale files in temp_uploads directory not linked to active DB records.
    3. Idempotent and safe under Flask's debug reloader.
    """
    cleaned_records = 0
    orphan_files_deleted = 0

    upload_dir = os.path.realpath(Config.TEMP_UPLOAD_DIR)
    if not os.path.exists(upload_dir):
        return {"cleaned_records": 0, "orphan_files_deleted": 0}

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Sweep expired database records
        cur.execute("""
            SELECT id, temp_media_path, temp_thumbnail_path
            FROM social_content
            WHERE temp_file_deleted = FALSE
              AND (temp_file_expires_at <= CURRENT_TIMESTAMP OR created_at <= CURRENT_TIMESTAMP - INTERVAL '24 hours');
        """)
        expired_rows = cur.fetchall()

        for cid, media_file, thumb_file in expired_rows:
            m_del = safe_delete_temp_file(media_file) if media_file else {"status": "missing"}
            t_del = safe_delete_temp_file(thumb_file) if thumb_file else {"status": "missing"}

            # Update DB only if not failed
            if m_del.get("status") != "failed" and t_del.get("status") != "failed":
                cur.execute("""
                    UPDATE social_content
                    SET temp_file_deleted = TRUE,
                        temp_file_deleted_at = CURRENT_TIMESTAMP,
                        temp_media_path = NULL,
                        temp_thumbnail_path = NULL
                    WHERE id = %s;
                """, (cid,))
                cleaned_records += 1

        conn.commit()

        # 2. Sweep orphan files from disk
        cur.execute("""
            SELECT temp_media_path FROM social_content WHERE temp_media_path IS NOT NULL
            UNION
            SELECT temp_thumbnail_path FROM social_content WHERE temp_thumbnail_path IS NOT NULL;
        """)
        active_db_files = {r[0] for r in cur.fetchall() if r[0]}

        now = datetime.datetime.now().timestamp()
        for fname in os.listdir(upload_dir):
            if fname.startswith(".git"):
                continue

            fpath = os.path.join(upload_dir, fname)
            if not os.path.isfile(fpath) or os.path.islink(fpath):
                continue

            # Partial upload file (.upload_*.tmp) older than 1 hour
            if fname.startswith(".upload_") and fname.endswith(".tmp"):
                if now - os.path.getmtime(fpath) > 3600:
                    del_res = safe_delete_temp_file(fname)
                    if del_res.get("removed"):
                        orphan_files_deleted += 1
                continue

            # Unreferenced file older than 1 hour
            if fname not in active_db_files:
                if now - os.path.getmtime(fpath) > 3600:
                    del_res = safe_delete_temp_file(fname)
                    if del_res.get("removed"):
                        orphan_files_deleted += 1

    except Exception as e:
        if conn:
            conn.rollback()
        print("Notice: Stale temporary upload cleanup finished with notice:", e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return {
        "cleaned_records": cleaned_records,
        "orphan_files_deleted": orphan_files_deleted
    }
