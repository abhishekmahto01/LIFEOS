"""
LifeOS — Social Post & Dashboard Service (Phase 6)
Encapsulates database access for:
- User Post History with retry eligibility computation
- Real-time content publishing status
- Dashboard telemetry and distinct recent posts
- Enforces strict user isolation and sanitization
"""

import datetime
from database.db import get_connection

VALID_STATUS_FILTERS = {
    "ALL",
    "DRAFT",
    "SCHEDULED",
    "PROCESSING",
    "PUBLISHED",
    "PARTIALLY_PUBLISHED",
    "FAILED",
}


def get_user_post_history(user_id: int, status_filter: str = None, page: int = 1, limit: int = 50) -> dict:
    """
    Retrieve paginated post history for the authenticated user.
    Computes retry eligibility and retry type (full video vs thumbnail-only).
    """
    if not user_id:
        return {"success": False, "error": "Unauthorized", "content": []}

    clean_filter = (status_filter or "ALL").upper()
    if clean_filter not in VALID_STATUS_FILTERS:
        clean_filter = "ALL"

    limit = max(1, min(limit, 100))
    offset = max(0, (page - 1) * limit)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT
                sc.id, sc.title, sc.common_caption, sc.hashtags, sc.media_type,
                sc.overall_status, sc.temp_file_deleted, sc.temp_file_expires_at,
                sc.created_at, sc.published_at,
                scp.id AS scp_id, scp.platform, scp.platform_status, scp.processing_status,
                scp.platform_post_id, scp.platform_post_url, scp.error_message,
                scp.upload_progress_percent, scp.thumbnail_status
            FROM social_content sc
            LEFT JOIN social_content_platforms scp ON sc.id = scp.content_id
            WHERE sc.user_id = %s
        """
        params = [user_id]

        if clean_filter != "ALL":
            query += " AND sc.overall_status = %s"
            params.append(clean_filter)

        query += " ORDER BY sc.created_at DESC LIMIT %s OFFSET %s;"
        params.extend([limit * 3, offset])

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        posts_map = {}

        for r in rows:
            (
                cid, title, caption, tags, mtype, status, temp_deleted, expires_at,
                created_at, published_at, scp_id, plat, pstatus, proc_status,
                post_id, post_url, err_msg, prog_pct, thumb_status
            ) = r

            if cid not in posts_map:
                is_media_valid = (not temp_deleted) and (expires_at is None or expires_at > now_utc)
                posts_map[cid] = {
                    "id": cid,
                    "title": title,
                    "common_caption": caption,
                    "hashtags": tags,
                    "media_type": mtype,
                    "content_status": status,
                    "overall_status": status,
                    "temp_file_deleted": temp_deleted,
                    "temp_file_expires_at": expires_at.isoformat() if expires_at else None,
                    "media_valid_for_retry": is_media_valid,
                    "retry_eligible": False,
                    "retry_type": None,
                    "created_at": created_at.isoformat() if created_at else None,
                    "published_at": published_at.isoformat() if published_at else None,
                    "platforms": []
                }

            if plat:
                posts_map[cid]["platforms"].append({
                    "id": scp_id,
                    "platform": plat,
                    "platform_status": pstatus,
                    "processing_status": proc_status,
                    "platform_post_id": post_id,
                    "platform_post_url": post_url,
                    "error_message": err_msg,
                    "progress_percent": prog_pct or 0,
                    "thumbnail_status": thumb_status or "IDLE"
                })

                # Determine retry eligibility
                is_plat_failed = pstatus == "FAILED" or proc_status == "FAILED" or thumb_status == "FAILED"
                if is_plat_failed and posts_map[cid]["media_valid_for_retry"]:
                    posts_map[cid]["retry_eligible"] = True
                    if post_id and thumb_status == "FAILED":
                        posts_map[cid]["retry_type"] = "THUMBNAIL_ONLY"
                    else:
                        posts_map[cid]["retry_type"] = "FULL_VIDEO"

        return {
            "success": True,
            "content": list(posts_map.values())[:limit]
        }

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_user_dashboard_summary(user_id: int) -> dict:
    """
    Retrieve real KPI metrics and distinct recent post summaries for the authenticated user.
    """
    if not user_id:
        return {"success": False, "error": "Unauthorized"}

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Total Published
        cur.execute("SELECT COUNT(*) FROM social_content WHERE user_id = %s AND overall_status = 'PUBLISHED';", (user_id,))
        total_published = cur.fetchone()[0]

        # 2. Processing (Active)
        cur.execute("SELECT COUNT(*) FROM social_content WHERE user_id = %s AND overall_status = 'PROCESSING';", (user_id,))
        processing_posts = cur.fetchone()[0]

        # 3. Scheduled
        cur.execute("SELECT COUNT(*) FROM social_content WHERE user_id = %s AND overall_status = 'SCHEDULED';", (user_id,))
        scheduled_posts = cur.fetchone()[0]

        # 4. Failed
        cur.execute("SELECT COUNT(*) FROM social_content WHERE user_id = %s AND overall_status = 'FAILED';", (user_id,))
        failed_posts = cur.fetchone()[0]

        # 5. Connected Accounts
        cur.execute("SELECT COUNT(*) FROM social_accounts WHERE user_id = %s AND connection_status = 'ACTIVE';", (user_id,))
        connected_count = cur.fetchone()[0]

        # 6. Platforms status dictionary
        cur.execute("""
            SELECT platform, account_name, account_username, connection_status, raw_scopes
            FROM social_accounts
            WHERE user_id = %s;
        """, (user_id,))
        acc_rows = cur.fetchall()

        platforms_dict = {
            "youtube": {"connected": False, "channelName": None, "status": "Not Connected", "can_upload": False},
            "instagram": {"connected": False, "accountName": None, "status": "Not Connected", "can_upload": False},
            "facebook": {"connected": False, "pageName": None, "status": "Not Connected", "can_upload": False}
        }

        for p, aname, auser, st, raw_scopes in acc_rows:
            key = p.lower()
            if key in platforms_dict:
                can_up = "youtube.upload" in set((raw_scopes or "").split()) if key == "youtube" else False
                platforms_dict[key] = {
                    "connected": st == "ACTIVE",
                    "channelName": aname or auser,
                    "accountName": aname or auser,
                    "pageName": aname or auser,
                    "status": "Connected" if st == "ACTIVE" else st,
                    "can_upload": can_up
                }

        # 7. Distinct recent 5 posts
        cur.execute("""
            SELECT sc.id, sc.title, sc.common_caption, sc.overall_status, sc.created_at
            FROM social_content sc
            WHERE sc.user_id = %s
            ORDER BY sc.created_at DESC
            LIMIT 5;
        """, (user_id,))
        recent_content_rows = cur.fetchall()

        recent_posts = []
        for cid, title, cap, st, created_at in recent_content_rows:
            # Fetch target platform post url if available
            cur.execute("""
                SELECT platform, platform_post_url FROM social_content_platforms
                WHERE content_id = %s ORDER BY id ASC LIMIT 1;
            """, (cid,))
            p_row = cur.fetchone()
            plat_name = p_row[0] if p_row else "YOUTUBE"
            post_url = p_row[1] if p_row else None

            recent_posts.append({
                "id": cid,
                "title": title,
                "caption": cap,
                "status": st,
                "created_at": created_at.isoformat() if created_at else None,
                "platform": plat_name,
                "url": post_url
            })

        return {
            "success": True,
            "metrics": {
                "totalPublished": total_published,
                "processingPosts": processing_posts,
                "scheduledPosts": scheduled_posts,
                "failedPosts": failed_posts,
                "connectedPlatforms": connected_count
            },
            "platforms": platforms_dict,
            "recentPosts": recent_posts
        }

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_content_status_detail(content_id: int, user_id: int) -> dict:
    """
    Retrieve real-time status and platform details for a single content record.
    """
    if not user_id or not content_id:
        return {"success": False, "error": "Invalid request", "status_code": 400}

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, title, overall_status, temp_file_deleted, temp_file_expires_at, created_at, published_at
            FROM social_content
            WHERE id = %s AND user_id = %s;
        """, (content_id, user_id))

        c_row = cur.fetchone()
        if not c_row:
            return {"success": False, "error": "Post not found or access denied.", "status_code": 404}

        cid, title, overall_status, temp_deleted, expires_at, created_at, published_at = c_row

        cur.execute("""
            SELECT
                id, platform, platform_status, processing_status,
                upload_progress_percent, bytes_sent, total_bytes,
                platform_post_id, platform_post_url, error_message,
                thumbnail_status, claim_expires_at
            FROM social_content_platforms
            WHERE content_id = %s;
        """, (content_id,))

        plat_rows = cur.fetchall()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        is_media_valid = (not temp_deleted) and (expires_at is None or expires_at > now_utc)

        platforms_status = []
        is_retry_eligible = False
        retry_type = None

        for r in plat_rows:
            scpid, plat, pstatus, proc_status, prog_pct, b_sent, b_total, post_id, post_url, err_msg, thumb_status, claim_exp = r

            platforms_status.append({
                "id": scpid,
                "platform": plat,
                "platform_status": pstatus,
                "processing_status": proc_status,
                "upload_progress_percent": prog_pct or 0,
                "bytes_sent": b_sent or 0,
                "total_bytes": b_total or 0,
                "platform_post_id": post_id,
                "platform_post_url": post_url,
                "error_message": err_msg,
                "thumbnail_status": thumb_status or "IDLE"
            })

            if (pstatus == "FAILED" or proc_status == "FAILED" or thumb_status == "FAILED") and is_media_valid:
                is_retry_eligible = True
                if post_id and thumb_status == "FAILED":
                    retry_type = "THUMBNAIL_ONLY"
                else:
                    retry_type = "FULL_VIDEO"

        return {
            "success": True,
            "content_id": cid,
            "title": title,
            "overall_status": overall_status,
            "temp_file_deleted": temp_deleted,
            "media_valid_for_retry": is_media_valid,
            "retry_eligible": is_retry_eligible,
            "retry_type": retry_type,
            "created_at": created_at.isoformat() if created_at else None,
            "published_at": published_at.isoformat() if published_at else None,
            "platforms": platforms_status,
            "status_code": 200
        }

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
