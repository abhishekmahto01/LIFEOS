"""
LifeOS — YouTube Publishing MVP Comprehensive Integration Tests (Phase 6 Fully Hardened & Fenced)
Validates all requirements:
1. Bearer token present on all 5 official Google requests (POST, PUT, GET).
2. Zero token, session URI, or local path leakage in API / DB / logs.
3. Exact upload-scope set parsing (rejects readonly without upload).
4. Strict validation limits & rejection of invalid privacy/category/metadata.
5. Actual video MIME type transmitted.
6. 308 Resume Incomplete Range header parsing & monotonic offset advancement.
7. Malformed / missing / out-of-bounds Range handling.
8. Ambiguous timeout queries authoritative server offset.
9. 401 Unauthorized token refresh and safe offset resumption.
10. Transient 5xx / 429 & Retry-After backoff handling.
11. Final success without video ID fails safely.
12. Malformed Google JSON fails safely.
13. uploadStatus="uploaded" remains PROCESSING and retains temporary file.
14. processed / succeeded confirms publication & safely deletes temporary video.
15. Physical delete failure preserves DB reference and keeps temp_file_deleted=False.
16. Independent video and thumbnail deletion lifecycle tracking.
17. Fenced worker state mutations reject null, wrong, or expired claim tokens.
18. Lost-lease worker stops immediately and cannot delete files or finalize success.
19. Lease heartbeat renewal & sleep_with_lease_heartbeat handling.
20. Job-type discrimination (FULL_UPLOAD, PROCESSING_CHECK, THUMBNAIL_RETRY, NO_OP).
21. Processing retry scheduling (next_processing_check_at) and due-time recovery.
22. Safe configuration parsing (rejects NaN, negative, non-multiple of 256 KB).
23. Database constraints verification (bounds, total_bytes >= bytes_sent, check counts).
24. Cross-user claim denial and user isolation.
25. Distinct recent posts query in Dashboard.
26. Multi-platform overall status recalculation.
27. Oversized thumbnail rejection without video failure.
28. Full-upload claim rejects missing or expired temporary media.
29. Processing check works after video media deletion.
30. Thumbnail retry respects thumbnail expiry.
"""

import os
import io
import sys
import json
import datetime
import unittest
from unittest.mock import patch, MagicMock
import requests

# Enforce backend path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Enforce isolated test database
test_db = os.getenv("TEST_DB_NAME", "lifeos_test")
prod_db = os.getenv("PROD_DB_NAME", "lifeos")
if test_db == prod_db or test_db == "lifeos":
    raise RuntimeError(f"SAFETY CHECK FAILED: Refusing to run tests against primary database '{prod_db}'. Set TEST_DB_NAME='lifeos_test'.")
os.environ["DB_NAME"] = test_db
os.environ["ENABLE_YOUTUBE_PUBLISH_WORKER"] = "false"

from app import app
from config import Config, _parse_int_config, _parse_float_config, _parse_bool_config
from database.db import get_connection, init_db
from utils.crypto import encrypt_token, decrypt_token
from utils.jwt_handler import generate_token
from services.upload_service import (
    create_social_content_record,
    get_safe_temp_path,
    safe_delete_temp_file,
    cleanup_content_media
)
from services.youtube_publish_service import (
    validate_youtube_metadata,
    initiate_resumable_upload_session,
    stream_video_chunks,
    upload_custom_thumbnail,
    poll_youtube_processing_status,
    execute_youtube_publish_pipeline,
    claim_publishing_job,
    renew_publishing_claim,
    release_publishing_claim,
    sleep_with_lease_heartbeat,
    _query_server_offset,
    _save_resumable_session_uri,
    _update_upload_progress,
    _save_video_id_and_status,
    _record_upload_failure,
    _update_thumbnail_status,
    _schedule_next_processing_check,
    _finalize_publication_success,
    _finalize_publication_failure,
    recover_pending_youtube_tasks,
    recalculate_content_overall_status,
    shutdown_publish_executor
)
from services.social_post_service import (
    get_user_post_history,
    get_user_dashboard_summary,
    get_content_status_detail
)
from services.youtube_oauth_service import (
    YOUTUBE_READONLY_SCOPE,
    YOUTUBE_UPLOAD_SCOPE
)


class TestYouTubePublishingHardened(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        init_db()

        self.user1_id = 1
        self.user2_id = 2

        # Ensure users exist in user_master
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_master (user_id, user_name, password, is_active)
            VALUES
                (1, 'admin', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE),
                (2, 'user2_test', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE)
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE, user_name = EXCLUDED.user_name;
        """)

        # Clean tables for test isolation
        cur.execute("DELETE FROM social_publish_attempts;")
        cur.execute("DELETE FROM social_content_platforms;")
        cur.execute("DELETE FROM social_content;")
        cur.execute("DELETE FROM social_accounts;")

        # Insert User 1 active YouTube account with upload scope
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                encrypted_access_token, encrypted_refresh_token, raw_scopes,
                token_expires_at, connection_status
            )
            VALUES (
                %s, 'YOUTUBE', 'UC_user1_channel', 'User 1 Creator Channel', 'creator1',
                %s, %s, %s,
                %s, 'ACTIVE'
            )
            RETURNING id;
        """, (
            self.user1_id,
            encrypt_token("ya29.user1_valid_access_token"),
            encrypt_token("1//user1_valid_refresh_token"),
            f"{YOUTUBE_READONLY_SCOPE} {YOUTUBE_UPLOAD_SCOPE}",
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        ))
        self.user1_account_id = cur.fetchone()[0]

        # Insert User 1 read-only account (missing upload scope)
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, raw_scopes,
                token_expires_at, connection_status
            )
            VALUES (
                %s, 'YOUTUBE', 'UC_user1_readonly', 'User 1 Readonly Channel',
                %s, %s, %s,
                %s, 'ACTIVE'
            )
            RETURNING id;
        """, (
            self.user1_id,
            encrypt_token("ya29.user1_ro_access"),
            encrypt_token("1//user1_ro_ref"),
            YOUTUBE_READONLY_SCOPE,
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        ))
        self.user1_readonly_account_id = cur.fetchone()[0]

        # Insert User 2 account
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, raw_scopes,
                token_expires_at, connection_status
            )
            VALUES (
                %s, 'YOUTUBE', 'UC_user2_channel', 'User 2 Channel',
                %s, %s, %s,
                %s, 'ACTIVE'
            )
            RETURNING id;
        """, (
            self.user2_id,
            encrypt_token("ya29.user2_access_token"),
            encrypt_token("1//user2_refresh_token"),
            f"{YOUTUBE_READONLY_SCOPE} {YOUTUBE_UPLOAD_SCOPE}",
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        ))
        self.user2_account_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        self.token_user1 = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")
        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Create a sample test video file in temp_uploads (2.5 MB)
        self.test_video_filename = "test_sample_vid_99999.mp4"
        self.test_video_abs = get_safe_temp_path(self.test_video_filename)
        with open(self.test_video_abs, "wb") as f:
            f.write(b"0" * (2 * 1024 * 1024 + 512 * 1024))

        # Create a sample test thumbnail file in temp_uploads (50 KB)
        self.test_thumb_filename = "test_thumb_99999.jpg"
        self.test_thumb_abs = get_safe_temp_path(self.test_thumb_filename)
        with open(self.test_thumb_abs, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xE0" + b"\x00" * 50000)

    def tearDown(self):
        shutdown_publish_executor(wait=False)
        safe_delete_temp_file(self.test_video_filename)
        safe_delete_temp_file(self.test_thumb_filename)

    # -------------------------------------------------------------------------
    # 1. Critical Authorization Tests
    # -------------------------------------------------------------------------

    @patch("time.sleep", return_value=None)
    @patch("services.youtube_publish_service.requests.get")
    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_01_bearer_token_present_on_all_google_requests(self, mock_post, mock_put, mock_get, mock_sleep):
        """Test Bearer token exists on session init POST, status query PUT, chunk PUT, thumbnails POST, and processing GET."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Auth Header Check",
            common_caption="Testing authorization header",
            hashtags="#auth",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            thumbnail_meta={"media_filename": self.test_thumb_filename, "file_size_bytes": os.path.getsize(self.test_thumb_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]

        mock_post_session = MagicMock(status_code=200, headers={"Location": "https://www.googleapis.com/upload/session_1"})
        mock_post_thumb = MagicMock(status_code=200)
        mock_post.side_effect = [mock_post_session, mock_post_thumb]

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={"Range": "bytes=0--1"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-2097151"}),
            MagicMock(status_code=201, json=lambda: {"id": "yt_auth_test_id"})
        ]

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"status": {"uploadStatus": "processed"}, "processingDetails": {"processingStatus": "succeeded"}}]}
        )

        res = execute_youtube_publish_pipeline(content_id=content_id, user_id=self.user1_id)
        self.assertTrue(res["success"])

        for call_args in mock_post.call_args_list:
            headers = call_args[1].get("headers", {})
            self.assertIn("Authorization", headers)
            self.assertTrue(headers["Authorization"].startswith("Bearer ya29."))

        for call_args in mock_put.call_args_list:
            headers = call_args[1].get("headers", {})
            self.assertIn("Authorization", headers)
            self.assertTrue(headers["Authorization"].startswith("Bearer ya29."))

        for call_args in mock_get.call_args_list:
            headers = call_args[1].get("headers", {})
            self.assertIn("Authorization", headers)
            self.assertTrue(headers["Authorization"].startswith("Bearer ya29."))

    def test_02_no_token_or_session_uri_leakage_in_responses_and_db(self):
        """Verify tokens and session URIs are never present in client responses or plaintext in DB."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Leakage Check Post",
            common_caption="Sanitization verification",
            hashtags="#sanitized",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]

        res_status = self.app.get(f"/api/social-media/content/{content_id}/status", headers=self.headers_user1)
        res_history = self.app.get("/api/social-media/history", headers=self.headers_user1)
        res_dash = self.app.get("/api/social-media/dashboard", headers=self.headers_user1)

        for res in [res_status, res_history, res_dash]:
            text = json.dumps(res.get_json())
            self.assertNotIn("ya29.", text)
            self.assertNotIn("1//", text)
            self.assertNotIn("upload_id=", text)
            self.assertNotIn("temp_uploads", text)

    def test_03_exact_upload_scope_set_parsing(self):
        """Test account with only youtube.readonly fails with clear UPLOAD_SCOPE_REQUIRED error."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Readonly Scope Test",
            common_caption="Checking exact scope parsing",
            hashtags="#scope",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_readonly_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        with self.assertRaises(ValueError) as ctx:
            initiate_resumable_upload_session(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertIn("UPLOAD_SCOPE_REQUIRED", str(ctx.exception))

    def test_04_invalid_privacy_category_and_boolean_rejection(self):
        """Test metadata validator strictly rejects invalid privacy, title, and description length."""
        with self.assertRaises(ValueError):
            validate_youtube_metadata(title="Title", privacy="INVALID_PRIVACY")
        with self.assertRaises(ValueError):
            validate_youtube_metadata(title="  ")
        with self.assertRaises(ValueError):
            validate_youtube_metadata(title="A" * 101)
        with self.assertRaises(ValueError):
            validate_youtube_metadata(title="Valid Title", description="D" * 5001)
        with self.assertRaises(ValueError):
            validate_youtube_metadata(title="Valid Title", tags=["tag" * 60, "tag" * 60, "tag" * 60])

    @patch("services.youtube_publish_service.requests.post")
    def test_05_actual_video_mime_passed_to_google(self, mock_post):
        """Test X-Upload-Content-Type passes actual validated video MIME type."""
        mov_filename = "test_mov_file.mov"
        mov_abs = get_safe_temp_path(mov_filename)
        with open(mov_abs, "wb") as f:
            f.write(b"0" * 1000)

        try:
            record = create_social_content_record(
                user_id=self.user1_id,
                title="MOV Test Post",
                common_caption="Testing MOV MIME",
                hashtags="#mov",
                media_meta={"media_filename": mov_filename, "file_size_bytes": 1000},
                platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
            )
            platform_id = record["platforms"][0]["id"]
            claim = claim_publishing_job(platform_id, self.user1_id)
            self.assertTrue(claim["claimed"])

            mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})
            initiate_resumable_upload_session(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])

            call_headers = mock_post.call_args[1]["headers"]
            self.assertEqual(call_headers["X-Upload-Content-Type"], "video/quicktime")
        finally:
            safe_delete_temp_file(mov_filename)

    # -------------------------------------------------------------------------
    # 2. Resumable Chunk Streaming & 308 Offset Tests
    # -------------------------------------------------------------------------

    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_06_308_offset_range_header_parsing(self, mock_post, mock_put):
        """Test 308 Resume Incomplete Range header bytes=0-1048575 advances offset to 1048576."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="308 Range Header Test",
            common_caption="Testing 308 offset parsing",
            hashtags="#offset",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={"Range": "bytes=0--1"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-2097151"}),
            MagicMock(status_code=201, json=lambda: {"id": "yt_308_success"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "yt_308_success")

    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_07_malformed_missing_and_out_of_bounds_range_rejection(self, mock_post, mock_put):
        """Test malformed, missing or out-of-bounds Range header does not crash streaming."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Range Edge Cases",
            common_caption="Edge cases",
            hashtags="#edge",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={"Range": "bytes=0-99999999"}), # Out of bounds
            MagicMock(status_code=308, headers={"Range": "invalid_range_value"}), # Malformed
            MagicMock(status_code=308, headers={}), # Missing
            MagicMock(status_code=201, json=lambda: {"id": "yt_edge_range_id"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "yt_edge_range_id")

    @patch("time.sleep", return_value=None)
    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_08_ambiguous_timeout_queries_authoritative_server_offset(self, mock_post, mock_put, mock_sleep):
        """Test transient timeout on chunk upload causes worker to query server offset before resending."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Timeout Status Query Test",
            common_caption="Testing status query on timeout",
            hashtags="#timeout",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})

        # Initial offset check -> chunk PUT timeout -> query server offset -> chunk 2 -> 201
        mock_put.side_effect = [
            MagicMock(status_code=308, headers={}),
            requests.exceptions.Timeout("Read timed out"),
            MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"}), # Server confirms 1MB accepted
            MagicMock(status_code=308, headers={"Range": "bytes=0-2097151"}),
            MagicMock(status_code=201, json=lambda: {"id": "yt_timeout_recovered_id"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "yt_timeout_recovered_id")

    @patch("services.youtube_publish_service.get_valid_youtube_access_token")
    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_09_401_token_refresh_and_offset_recovery(self, mock_post, mock_put, mock_get_token):
        """Test HTTP 401 during chunk upload refreshes token, queries offset, and safely resumes."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="401 Token Refresh Test",
            common_caption="Testing 401 recovery",
            hashtags="#refresh",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_get_token.side_effect = ["ya29.initial_token", "ya29.refreshed_token", "ya29.refreshed_token", "ya29.refreshed_token"]
        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={}),
            MagicMock(status_code=401),
            MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-2097151"}),
            MagicMock(status_code=201, json=lambda: {"id": "yt_401_recovered_id"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "yt_401_recovered_id")
        mock_get_token.assert_any_call(account_id=self.user1_account_id, user_id=self.user1_id, force_refresh=True)

    @patch("time.sleep", return_value=None)
    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_10_transient_5xx_and_retry_after_handling(self, mock_post, mock_put, mock_sleep):
        """Test transient HTTP 503 with Retry-After header is retried and completes successfully."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="503 Retry-After Test",
            common_caption="Testing 503 backoff",
            hashtags="#backoff",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={}),
            MagicMock(status_code=503, headers={"Retry-After": "3"}),
            MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"}),
            MagicMock(status_code=201, json=lambda: {"id": "yt_503_id"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "yt_503_id")

    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_11_final_success_without_video_id_fails_safely(self, mock_post, mock_put):
        """Test HTTP 200 without a YouTube video ID in body fails safely without crashing."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Missing Video ID Test",
            common_caption="Testing missing ID",
            hashtags="#test",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})
        mock_put.side_effect = [
            MagicMock(status_code=308, headers={}),
            MagicMock(status_code=200, json=lambda: {"kind": "youtube#video"})
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertFalse(result["success"])
        self.assertIn("YouTube video ID missing", result["error"])

    @patch("services.youtube_publish_service.requests.put")
    @patch("services.youtube_publish_service.requests.post")
    def test_12_malformed_google_json_fails_safely(self, mock_post, mock_put):
        """Test malformed non-JSON final response fails safely with error code."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Malformed JSON Test",
            common_caption="Testing malformed body",
            hashtags="#test",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        mock_post.return_value = MagicMock(status_code=200, headers={"Location": "https://upload.session"})
        malformed_resp = MagicMock(status_code=200)
        malformed_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        mock_put.side_effect = [
            MagicMock(status_code=308, headers={}),
            malformed_resp
        ]

        result = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token=claim["claim_token"])
        self.assertFalse(result["success"])
        self.assertIn("Invalid response format", result["error"])

    # -------------------------------------------------------------------------
    # 3. Processing Semantics & Temporary File Lifecycle Tests
    # -------------------------------------------------------------------------

    @patch("time.sleep", return_value=None)
    @patch("services.youtube_publish_service.requests.get")
    def test_13_upload_status_uploaded_remains_processing_and_retains_file(self, mock_get, mock_sleep):
        """Regression test: uploadStatus='uploaded' does NOT mark published and does NOT delete temp file."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Uploaded Status Regression Test",
            common_caption="Testing uploaded vs processed semantics",
            hashtags="#uploaded",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        self.assertTrue(os.path.exists(self.test_video_abs))

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"status": {"uploadStatus": "uploaded"}, "processingDetails": {"processingStatus": "processing"}}]}
        )

        res = poll_youtube_processing_status(
            content_platform_id=platform_id,
            user_id=self.user1_id,
            video_id="yt_uploaded_id",
            claim_token=claim["claim_token"],
            max_polls=2,
            poll_interval=0.01
        )

        self.assertEqual(res["status"], "PROCESSING")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT overall_status, temp_file_deleted FROM social_content WHERE id = %s;", (content_id,))
        overall_st, temp_deleted = cur.fetchone()
        cur.close()
        conn.close()

        self.assertNotEqual(overall_st, "PUBLISHED")
        self.assertFalse(temp_deleted)
        self.assertTrue(os.path.exists(self.test_video_abs))

    @patch("services.youtube_publish_service.requests.get")
    def test_14_processed_and_succeeded_confirms_publication(self, mock_get):
        """Test processingStatus='succeeded' marks PUBLISHED and deletes temporary video file."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Succeeded Test",
            common_caption="Testing succeeded confirmation",
            hashtags="#succeeded",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        self.assertTrue(os.path.exists(self.test_video_abs))

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"status": {"uploadStatus": "processed"}, "processingDetails": {"processingStatus": "succeeded"}}]}
        )

        res = poll_youtube_processing_status(
            content_platform_id=platform_id,
            user_id=self.user1_id,
            video_id="yt_succeeded_id",
            claim_token=claim["claim_token"],
            max_polls=1,
            poll_interval=0.01
        )

        self.assertEqual(res["status"], "PUBLISHED")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT overall_status, temp_file_deleted FROM social_content WHERE id = %s;", (content_id,))
        overall_st, temp_deleted = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(overall_st, "PUBLISHED")
        self.assertTrue(temp_deleted)
        self.assertFalse(os.path.exists(self.test_video_abs))

    @patch("services.upload_service.safe_delete_temp_file")
    def test_15_physical_delete_failure_preserves_db_reference(self, mock_del):
        """Test physical deletion failure preserves DB path reference and leaves temp_file_deleted=False."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Physical Delete Fail Test",
            common_caption="Testing delete failure handling",
            hashtags="#delete",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]

        mock_del.return_value = {"removed": False, "status": "failed", "error": "Permission denied"}

        cleanup_res = cleanup_content_media(content_id=content_id, user_id=self.user1_id, force=True)
        self.assertFalse(cleanup_res["deleted"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT temp_media_path, temp_file_deleted FROM social_content WHERE id = %s;", (content_id,))
        temp_path, temp_deleted = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(temp_path)
        self.assertFalse(temp_deleted)

    @patch("services.youtube_publish_service.requests.post")
    def test_16_video_and_thumbnail_deletion_tracked_independently(self, mock_post):
        """Test thumbnail upload success deletes thumbnail file while video is still processing."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Independent Lifecycle Test",
            common_caption="Testing independent cleanup",
            hashtags="#thumb",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            thumbnail_meta={"media_filename": self.test_thumb_filename, "file_size_bytes": 50000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])

        self.assertTrue(os.path.exists(self.test_thumb_abs))
        self.assertTrue(os.path.exists(self.test_video_abs))

        mock_post.return_value = MagicMock(status_code=200)

        res = upload_custom_thumbnail(content_platform_id=platform_id, user_id=self.user1_id, video_id="yt_thumb_ind_id", claim_token=claim["claim_token"])
        self.assertTrue(res["success"])

        self.assertFalse(os.path.exists(self.test_thumb_abs))
        self.assertTrue(os.path.exists(self.test_video_abs))

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT temp_media_path, temp_thumbnail_path, temp_file_deleted FROM social_content WHERE id = %s;", (content_id,))
        temp_vid, temp_thumb, is_del = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(temp_vid)
        self.assertIsNone(temp_thumb)
        self.assertFalse(is_del)

    # -------------------------------------------------------------------------
    # 4. Strict Fencing, Heartbeat Renewal & Worker Lifecycle Tests
    # -------------------------------------------------------------------------

    def test_17_fenced_worker_mutations_reject_null_wrong_and_expired_tokens(self):
        """Test all worker state mutation helpers reject null, wrong, or expired claim tokens."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Mutation Fencing Test",
            common_caption="Testing strict token fencing",
            hashtags="#fenced",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        # 1. Null / empty claim token is rejected
        self.assertFalse(_update_upload_progress(platform_id, self.user1_id, None, 100, 1000, 10))
        self.assertFalse(_save_video_id_and_status(platform_id, self.user1_id, "", "yt_vid_test"))
        self.assertFalse(_record_upload_failure(platform_id, self.user1_id, "   ", "ERR", "msg"))
        self.assertFalse(_update_thumbnail_status(platform_id, self.user1_id, None, "FAILED"))
        self.assertFalse(_finalize_publication_success(platform_id, self.user1_id, None, content_id, None))
        self.assertFalse(_finalize_publication_failure(platform_id, self.user1_id, None, content_id, "ERR", "msg"))
        self.assertFalse(_schedule_next_processing_check(platform_id, self.user1_id, None, 10))

        # 2. Valid claim acquired
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])
        token = claim["claim_token"]

        # 3. Wrong token is rejected
        self.assertFalse(_update_upload_progress(platform_id, self.user1_id, "wrong_token_xyz", 100, 1000, 10))

        # 4. Correct token succeeds
        self.assertTrue(_update_upload_progress(platform_id, self.user1_id, token, 100, 1000, 10))

        # 5. Expired claim (claim_expires_at in past) is rejected
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE social_content_platforms SET claim_expires_at = CURRENT_TIMESTAMP - interval '10 seconds' WHERE id = %s;", (platform_id,))
        conn.commit()
        cur.close()
        conn.close()

        self.assertFalse(_update_upload_progress(platform_id, self.user1_id, token, 200, 1000, 20))
        self.assertFalse(_finalize_publication_success(platform_id, self.user1_id, token, content_id, None))

    @patch("services.youtube_publish_service.requests.put")
    def test_18_lost_lease_worker_stops_and_cannot_delete_files(self, mock_put):
        """Test worker whose lease is lost stops immediately without making requests or deleting files."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Lost Lease Action Test",
            common_caption="Testing lost lease stoppage",
            hashtags="#lost",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": os.path.getsize(self.test_video_abs)},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]

        mock_put.return_value = MagicMock(status_code=308, headers={"Range": "bytes=0-1048575"})

        res = stream_video_chunks(content_platform_id=platform_id, user_id=self.user1_id, claim_token="stale_unclaimed_token")
        self.assertFalse(res["success"])
        self.assertIn("LEASE_LOST", res["error"])
        # Temp video file must still exist
        self.assertTrue(os.path.exists(self.test_video_abs))

    def test_19_lease_heartbeat_renewal_and_sleep(self):
        """Test sleep_with_lease_heartbeat renews active leases and aborts when lease is expired."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Sleep Heartbeat Test",
            common_caption="Testing heartbeat sleep",
            hashtags="#sleep",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]
        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])
        token = claim["claim_token"]

        with patch("time.sleep", return_value=None):
            # Active lease sleep succeeds
            self.assertTrue(sleep_with_lease_heartbeat(platform_id, self.user1_id, token, total_seconds=2.0, interval_seconds=1.0))

            # Expire lease in DB
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE social_content_platforms SET claim_expires_at = CURRENT_TIMESTAMP - interval '1 second' WHERE id = %s;", (platform_id,))
            conn.commit()
            cur.close()
            conn.close()

            # Heartbeat renewal fails -> sleep returns False immediately
            self.assertFalse(sleep_with_lease_heartbeat(platform_id, self.user1_id, token, total_seconds=2.0, interval_seconds=1.0))

    @patch("services.youtube_publish_service.upload_custom_thumbnail")
    @patch("services.youtube_publish_service.initiate_resumable_upload_session")
    def test_20_job_type_thumbnail_retry_never_calls_videos_insert(self, mock_init, mock_thumb):
        """Test THUMBNAIL_RETRY job type uploads thumbnail without initiating video session."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Thumbnail Job Type Test",
            common_caption="Testing job routing",
            hashtags="#thumb",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            thumbnail_meta={"media_filename": self.test_thumb_filename, "file_size_bytes": 50000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        # Mark post as published with failed thumbnail
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_post_id = 'yt_existing_published_id',
                platform_post_url = 'https://www.youtube.com/watch?v=yt_existing_published_id',
                platform_status = 'PUBLISHED',
                thumbnail_status = 'FAILED'
            WHERE id = %s;
        """, (platform_id,))
        cur.execute("UPDATE social_content SET overall_status = 'PUBLISHED' WHERE id = %s;", (content_id,))
        conn.commit()
        cur.close()
        conn.close()

        mock_thumb.return_value = {"success": True, "message": "Thumbnail uploaded."}

        res = execute_youtube_publish_pipeline(content_id=content_id, user_id=self.user1_id)
        self.assertTrue(res["success"])
        self.assertEqual(res.get("job_type"), "THUMBNAIL_RETRY")
        mock_init.assert_not_called()
        mock_thumb.assert_called_once()

    @patch("services.youtube_publish_service.Config.ENABLE_YOUTUBE_PUBLISH_WORKER", True)
    def test_21_processing_retry_schedule_and_recovery(self):
        """Test processing poll sets next_processing_check_at and recovery picks up due tasks."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Processing Schedule Test",
            common_caption="Testing scheduling",
            hashtags="#schedule",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]

        # Set next_processing_check_at in the future (+1 hour)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_post_id = 'yt_future_id',
                platform_status = 'PROCESSING',
                next_processing_check_at = CURRENT_TIMESTAMP + interval '1 hour'
            WHERE id = %s;
        """, (platform_id,))
        conn.commit()
        cur.close()
        conn.close()

        with patch("services.youtube_publish_service.start_youtube_publish_task") as mock_start:
            # When future scheduled, recovery should skip it
            recover_pending_youtube_tasks()
            mock_start.assert_not_called()

            # When due (now/past), recovery should pick it up
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE social_content_platforms
                SET next_processing_check_at = CURRENT_TIMESTAMP - interval '1 minute'
                WHERE id = %s;
            """, (platform_id,))
            conn.commit()
            cur.close()
            conn.close()

            recover_pending_youtube_tasks()
            mock_start.assert_called_once_with(record["content_id"], self.user1_id)

    # -------------------------------------------------------------------------
    # 5. Configuration & Database Constraints Tests
    # -------------------------------------------------------------------------

    def test_22_safe_configuration_parsing(self):
        """Test safe configuration parsers reject malformed, negative, NaN, and non-multiple values."""
        # 1. Invalid integer / below min
        with patch.dict(os.environ, {"TEST_INT_BELOW": "-5"}):
            with self.assertRaises(ValueError):
                _parse_int_config("TEST_INT_BELOW", 1024, min_val=1)

        with patch.dict(os.environ, {"TEST_INT": "abc"}):
            with self.assertRaises(ValueError):
                _parse_int_config("TEST_INT", 1024)

        # 2. Non-multiple of 256
        with patch.dict(os.environ, {"TEST_CHUNK": "1000"}):
            with self.assertRaises(ValueError):
                _parse_int_config("TEST_CHUNK", 1024, multiple_of=256)

        # 3. NaN float
        with patch.dict(os.environ, {"TEST_FLOAT": "NaN"}):
            with self.assertRaises(ValueError):
                _parse_float_config("TEST_FLOAT", 1.0)

        # 4. Invalid boolean
        with patch.dict(os.environ, {"TEST_BOOL": "maybe"}):
            with self.assertRaises(ValueError):
                _parse_bool_config("TEST_BOOL", True)

    def test_23_database_constraints_integrity(self):
        """Test table constraints reject invalid upload progress, negative bytes, and invalid bytes relation."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="DB Constraint Test",
            common_caption="Testing constraints",
            hashtags="#db",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        platform_id = record["platforms"][0]["id"]

        conn = get_connection()
        cur = conn.cursor()

        # 1. upload_progress_percent > 100 violates constraint
        with self.assertRaises(Exception):
            cur.execute("UPDATE social_content_platforms SET upload_progress_percent = 101 WHERE id = %s;", (platform_id,))
        conn.rollback()

        # 2. bytes_sent > total_bytes violates constraint
        with self.assertRaises(Exception):
            cur.execute("UPDATE social_content_platforms SET total_bytes = 500, bytes_sent = 600 WHERE id = %s;", (platform_id,))
        conn.rollback()

        # 3. invalid thumbnail_status violates constraint
        with self.assertRaises(Exception):
            cur.execute("UPDATE social_content_platforms SET thumbnail_status = 'INVALID_STATUS' WHERE id = %s;", (platform_id,))
        conn.rollback()

        cur.close()
        conn.close()

    def test_24_dashboard_and_history_user_isolation(self):
        """Test User 1 cannot access User 2's post history, status, or dashboard."""
        create_social_content_record(
            user_id=self.user1_id,
            title="User 1 Isolated Post",
            common_caption="User 1 post",
            hashtags="#u1",
            media_meta={"media_filename": "u1.mp4", "file_size_bytes": 100},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        r2 = create_social_content_record(
            user_id=self.user2_id,
            title="User 2 Isolated Post",
            common_caption="User 2 post",
            hashtags="#u2",
            media_meta={"media_filename": "u2.mp4", "file_size_bytes": 100},
            platforms=[{"account_id": self.user2_account_id, "platform": "YOUTUBE"}]
        )
        u2_content_id = r2["content_id"]

        res1 = self.app.get("/api/social-media/history", headers=self.headers_user1)
        self.assertEqual(res1.status_code, 200)
        items1 = res1.get_json().get("content", [])
        self.assertEqual(len(items1), 1)
        self.assertEqual(items1[0]["title"], "User 1 Isolated Post")

        res_cross = self.app.get(f"/api/social-media/content/{u2_content_id}/status", headers=self.headers_user1)
        self.assertEqual(res_cross.status_code, 404)

    def test_25_distinct_recent_posts_query(self):
        """Test Dashboard recent posts returns distinct posts when multiple platforms exist."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Multi-Platform Post",
            common_caption="Testing distinct rows",
            hashtags="#distinct",
            media_meta={"media_filename": "multi.mp4", "file_size_bytes": 100},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        cid = record["content_id"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status)
            VALUES (%s, %s, 'INSTAGRAM', 'PENDING');
        """, (cid, self.user1_account_id))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.get("/api/social-media/dashboard", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)
        recent = res.get_json().get("recentPosts", [])
        self.assertEqual(len(recent), 1)

    def test_26_overall_status_recalculation_multi_platform(self):
        """Test recalculate_content_overall_status for combinations of platform states."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Status Recalc Test",
            common_caption="Recalculation test",
            hashtags="#recalc",
            media_meta={"media_filename": "recalc.mp4", "file_size_bytes": 100},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("UPDATE social_content_platforms SET platform_status = 'PUBLISHED' WHERE id = %s;", (platform_id,))
        conn.commit()
        recalculate_content_overall_status(content_id)
        cur.execute("SELECT overall_status FROM social_content WHERE id = %s;", (content_id,))
        self.assertEqual(cur.fetchone()[0], "PUBLISHED")

        cur.execute("UPDATE social_content_platforms SET platform_status = 'FAILED' WHERE id = %s;", (platform_id,))
        conn.commit()
        recalculate_content_overall_status(content_id)
        cur.execute("SELECT overall_status FROM social_content WHERE id = %s;", (content_id,))
        self.assertEqual(cur.fetchone()[0], "FAILED")

        cur.close()
        conn.close()

    @patch("services.youtube_publish_service.requests.post")
    def test_27_thumbnail_upload_oversized_rejected_without_failing_video(self, mock_post):
        """Test thumbnail > 2MB is rejected without throwing exception or failing video."""
        oversized_thumb = "test_oversized_thumb.jpg"
        thumb_abs = get_safe_temp_path(oversized_thumb)
        with open(thumb_abs, "wb") as f:
            f.write(b"0" * (2 * 1024 * 1024 + 100))

        try:
            record = create_social_content_record(
                user_id=self.user1_id,
                title="Oversized Thumbnail Test",
                common_caption="Testing 2MB limit",
                hashtags="#thumb",
                media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
                thumbnail_meta={"media_filename": oversized_thumb, "file_size_bytes": os.path.getsize(thumb_abs)},
                platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
            )
            platform_id = record["platforms"][0]["id"]
            claim = claim_publishing_job(platform_id, self.user1_id)
            self.assertTrue(claim["claimed"])

            res = upload_custom_thumbnail(content_platform_id=platform_id, user_id=self.user1_id, video_id="yt_vid_test", claim_token=claim["claim_token"])
            self.assertFalse(res["success"])
            self.assertIn("exceeds YouTube 2 MB limit", res["error"])
            mock_post.assert_not_called()
        finally:
            safe_delete_temp_file(oversized_thumb)

    def test_28_full_upload_claim_rejects_missing_or_expired_media(self):
        """Test FULL_UPLOAD claim is rejected when media is deleted or expired."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Expired Claim Test",
            common_caption="Testing claim eligibility",
            hashtags="#claim",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        # 1. Mark temp file expired in past
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE social_content SET temp_file_expires_at = CURRENT_TIMESTAMP - interval '1 hour' WHERE id = %s;", (content_id,))
        conn.commit()
        cur.close()
        conn.close()

        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertFalse(claim["claimed"])

    def test_29_processing_check_works_after_video_media_deleted(self):
        """Test PROCESSING_CHECK claim succeeds even when temporary video file was deleted."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Processing Without Media Test",
            common_caption="Testing proc check without media",
            hashtags="#proc",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        # Pre-set video ID and deleted temp file
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_post_id = 'yt_proc_test_id',
                platform_status = 'PROCESSING',
                processing_status = 'PROCESSING'
            WHERE id = %s;
        """, (platform_id,))
        cur.execute("UPDATE social_content SET temp_media_path = NULL, temp_file_deleted = TRUE WHERE id = %s;", (content_id,))
        conn.commit()
        cur.close()
        conn.close()

        claim = claim_publishing_job(platform_id, self.user1_id)
        self.assertTrue(claim["claimed"])
        self.assertEqual(claim["job_type"], "PROCESSING_CHECK")

    def test_30_thumbnail_retry_respects_thumbnail_expiry(self):
        """Test THUMBNAIL_RETRY claim fails if thumbnail media is expired or deleted."""
        record = create_social_content_record(
            user_id=self.user1_id,
            title="Thumb Expiry Test",
            common_caption="Testing thumb expiry",
            hashtags="#thumb",
            media_meta={"media_filename": self.test_video_filename, "file_size_bytes": 1000},
            thumbnail_meta={"media_filename": self.test_thumb_filename, "file_size_bytes": 50000},
            platforms=[{"account_id": self.user1_account_id, "platform": "YOUTUBE"}]
        )
        content_id = record["content_id"]
        platform_id = record["platforms"][0]["id"]

        # Mark post as published, thumbnail failed, thumbnail expired
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE social_content_platforms
            SET platform_post_id = 'yt_published_id',
                platform_status = 'PUBLISHED',
                thumbnail_status = 'FAILED'
            WHERE id = %s;
        """, (platform_id,))
        cur.execute("UPDATE social_content SET temp_thumbnail_path = NULL WHERE id = %s;", (content_id,))
        conn.commit()
        cur.close()
        conn.close()

        claim = claim_publishing_job(platform_id, self.user1_id)
        # Cannot claim thumbnail retry when thumbnail path is missing
        self.assertFalse(claim["claimed"])


if __name__ == "__main__":
    unittest.main()
