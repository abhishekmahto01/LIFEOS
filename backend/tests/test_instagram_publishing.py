import os
import sys
import json
import time
import datetime
import unittest
from unittest.mock import patch, MagicMock
import requests

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Enforce isolated test database
test_db = os.getenv("TEST_DB_NAME", "lifeos_test")
prod_db = os.getenv("PROD_DB_NAME", "lifeos")
if test_db == prod_db or test_db == "lifeos":
    raise RuntimeError(f"SAFETY CHECK FAILED: Refusing to run tests against primary database '{prod_db}'. Set TEST_DB_NAME='lifeos_test'.")
os.environ["DB_NAME"] = test_db

from app import app
from config import Config
from database.db import get_connection, init_db
from utils.jwt_handler import generate_token
from utils.crypto import encrypt_token, decrypt_token
from services.instagram_publish_service import (
    format_instagram_caption,
    resolve_instagram_video_url,
    create_instagram_reel_container,
    poll_instagram_container_status,
    publish_instagram_container,
    get_instagram_media_permalink,
    publish_instagram_reel,
    recalculate_content_overall_status
)


class TestInstagramPublishing(unittest.TestCase):

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
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE;
        """)

        # Clean tables
        cur.execute("DELETE FROM social_publish_attempts;")
        cur.execute("DELETE FROM social_content_platforms;")
        cur.execute("DELETE FROM social_content;")
        cur.execute("DELETE FROM social_accounts;")
        conn.commit()
        cur.close()
        conn.close()

        self.token_user1 = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")

        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Mock configuration
        Config.INSTAGRAM_CLIENT_ID = "mock_meta_app_id"
        Config.INSTAGRAM_CLIENT_SECRET = "mock_meta_app_secret"
        Config.META_GRAPH_API_VERSION = "v21.0"
        Config.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
        Config.INSTAGRAM_MEDIA_BASE_URL = "https://cdn.example.com"
        Config.INSTAGRAM_PUBLISH_POLL_INTERVAL_SECONDS = 0.05
        Config.INSTAGRAM_PUBLISH_MAX_WAIT_SECONDS = 2

        # Create physical dummy media file in temp uploads directory
        os.makedirs(Config.TEMP_UPLOAD_DIR, exist_ok=True)
        self.dummy_media_filename = "test_reel_video_1.mp4"
        self.dummy_media_path = os.path.join(Config.TEMP_UPLOAD_DIR, self.dummy_media_filename)
        with open(self.dummy_media_path, "wb") as f:
            f.write(b"mock_mp4_video_data_for_testing_purposes")

    def tearDown(self):
        if os.path.exists(self.dummy_media_path):
            try:
                os.remove(self.dummy_media_path)
            except Exception:
                pass

    def _insert_instagram_account(self, user_id=1, ig_user_id="17841400000000001", status="ACTIVE", token="valid_meta_token"):
        conn = get_connection()
        cur = conn.cursor()
        enc = encrypt_token(token)
        future_exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                profile_image_url, encrypted_access_token, token_expires_at, connection_status,
                raw_scopes, metadata
            )
            VALUES (
                %s, 'INSTAGRAM', %s, 'LifeOS Creator', 'lifeos_creator',
                'https://example.com/pic.jpg', %s, %s, %s,
                'instagram_basic,instagram_content_publish', '{"facebook_page_id": "p123"}'::jsonb
            )
            RETURNING id;
        """, (user_id, ig_user_id, enc, future_exp, status))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return acc_id

    def _insert_social_content(self, user_id=1, title="Test Reel Title", desc="Test Description", tags="#reel #lifeos", temp_filename=None, deleted=False, expired=False):
        conn = get_connection()
        cur = conn.cursor()
        media_file = temp_filename or self.dummy_media_filename
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        exp_time = now_utc - datetime.timedelta(hours=2) if expired else now_utc + datetime.timedelta(hours=24)

        cur.execute("""
            INSERT INTO social_content (
                user_id, title, common_caption, hashtags, media_type,
                temp_media_path, temp_file_deleted, temp_file_expires_at, overall_status
            )
            VALUES (
                %s, %s, %s, %s, 'VIDEO',
                %s, %s, %s, 'DRAFT'
            )
            RETURNING id;
        """, (user_id, title, desc, tags, media_file, deleted, exp_time))
        cid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return cid

    def test_01_jwt_required_on_publish_endpoint(self):
        """Test POST /api/social-media/publish/instagram requires valid JWT authentication."""
        # 1. No JWT
        res1 = self.app.post("/api/social-media/publish/instagram", json={"content_id": 1, "account_id": 1})
        self.assertEqual(res1.status_code, 401)

        # 2. Invalid JWT
        res2 = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": 1, "account_id": 1},
            headers={"Authorization": "Bearer invalid_token_xyz"}
        )
        self.assertEqual(res2.status_code, 401)

    def test_02_invalid_content_id_rejected(self):
        """Test missing, null, or negative content_id is rejected with 400."""
        res1 = self.app.post("/api/social-media/publish/instagram", json={"account_id": 1}, headers=self.headers_user1)
        self.assertEqual(res1.status_code, 400)
        self.assertIn("content_id is required", res1.get_json()["error"])

        res2 = self.app.post("/api/social-media/publish/instagram", json={"content_id": -5, "account_id": 1}, headers=self.headers_user1)
        self.assertEqual(res2.status_code, 400)

        res3 = self.app.post("/api/social-media/publish/instagram", json={"content_id": "not_an_int", "account_id": 1}, headers=self.headers_user1)
        self.assertEqual(res3.status_code, 400)

    def test_03_invalid_account_id_rejected(self):
        """Test missing, null, or negative account_id is rejected with 400."""
        res1 = self.app.post("/api/social-media/publish/instagram", json={"content_id": 1}, headers=self.headers_user1)
        self.assertEqual(res1.status_code, 400)
        self.assertIn("account_id is required", res1.get_json()["error"])

        res2 = self.app.post("/api/social-media/publish/instagram", json={"content_id": 1, "account_id": -99}, headers=self.headers_user1)
        self.assertEqual(res2.status_code, 400)

    def test_04_content_ownership_enforced(self):
        """Test User 1 cannot publish User 2's content."""
        cid_user2 = self._insert_social_content(user_id=self.user2_id)
        aid_user1 = self._insert_instagram_account(user_id=self.user1_id)

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid_user2, "account_id": aid_user1},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Content item not found or access denied", res.get_json()["error"])

    def test_05_account_ownership_enforced(self):
        """Test User 1 cannot publish using User 2's Instagram account."""
        cid_user1 = self._insert_social_content(user_id=self.user1_id)
        aid_user2 = self._insert_instagram_account(user_id=self.user2_id)

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid_user1, "account_id": aid_user2},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Instagram account not found or access denied", res.get_json()["error"])

    def test_06_non_instagram_account_rejected(self):
        """Test attempting to publish to Instagram with a non-Instagram (e.g. YouTube) account fails."""
        cid = self._insert_social_content(user_id=self.user1_id)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name, connection_status)
            VALUES (%s, 'YOUTUBE', 'UC_some_channel_non_ig', 'YouTube Channel', 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET connection_status = 'ACTIVE'
            RETURNING id;
        """, (self.user1_id,))
        yt_aid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": yt_aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not an Instagram account", res.get_json()["error"])

    def test_07_disconnected_or_expired_account_rejected(self):
        """Test publishing with a disconnected account is rejected."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id, status="DISCONNECTED")

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("DISCONNECTED", res.get_json()["error"])

    def test_08_valid_token_retrieval_integration(self):
        """Test valid access token is decrypted and used on Meta API requests."""
        cid = self._insert_social_content(user_id=self.user1_id)
        raw_secret_token = "EAA_test_secret_token_12345"
        aid = self._insert_instagram_account(user_id=self.user1_id, token=raw_secret_token)

        with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
            # 1. Container creation response
            mock_container_resp = MagicMock()
            mock_container_resp.status_code = 200
            mock_container_resp.json.return_value = {"id": "container_123"}
            mock_post.side_effect = [
                mock_container_resp,
                MagicMock(status_code=200, json=lambda: {"id": "ig_media_999"})
            ]

            # 2. Polling and permalink responses
            mock_poll_resp = MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"})
            mock_permalink_resp = MagicMock(status_code=200, json=lambda: {"permalink": "https://www.instagram.com/reel/CXYZ123/"})
            mock_get.side_effect = [mock_poll_resp, mock_permalink_resp]

            res = self.app.post(
                "/api/social-media/publish/instagram",
                json={"content_id": cid, "account_id": aid},
                headers=self.headers_user1
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["publish_id"], "ig_media_999")

            # Verify Bearer token was passed in authorization header
            container_call_headers = mock_post.call_args_list[0][1]["headers"]
            self.assertEqual(container_call_headers["Authorization"], f"Bearer {raw_secret_token}")

    def test_09_missing_local_media_handled_safely(self):
        """Test missing physical media file on disk fails safely with 410."""
        cid = self._insert_social_content(user_id=self.user1_id, temp_filename="non_existent_file_999.mp4")
        aid = self._insert_instagram_account(user_id=self.user1_id)

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 410)
        self.assertIn("not found on disk", res.get_json()["error"])

    def test_10_expired_temporary_media_rejected(self):
        """Test expired temporary media file fails safely with 410."""
        cid = self._insert_social_content(user_id=self.user1_id, expired=True)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 410)
        self.assertIn("expired", res.get_json()["error"].lower())

    @patch("requests.post")
    def test_11_container_creation_success(self, mock_post):
        """Test create_instagram_reel_container successfully returns creation ID."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "17928238123456789"}
        mock_post.return_value = mock_resp

        creation_id = create_instagram_reel_container(
            ig_user_id="17841400000000001",
            access_token="EAA_mock_token",
            video_url="https://cdn.example.com/reel.mp4",
            caption="Test Caption"
        )
        self.assertEqual(creation_id, "17928238123456789")

    @patch("requests.post")
    def test_12_container_creation_meta_failure(self, mock_post):
        """Test Meta OAuth / validation error during container creation raises sanitized error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "Invalid video aspect ratio for Instagram Reels.",
                "type": "OAuthException",
                "code": 100
            }
        }
        mock_post.return_value = mock_resp

        with self.assertRaises(ValueError) as ctx:
            create_instagram_reel_container(
                ig_user_id="17841400000000001",
                access_token="EAA_mock_token",
                video_url="https://cdn.example.com/reel.mp4",
                caption="Test"
            )
        self.assertIn("Invalid video aspect ratio", str(ctx.exception))

    @patch("requests.post")
    def test_13_container_creation_malformed_json(self, mock_post):
        """Test malformed non-JSON response from Meta container creation is handled safely."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "bad_json", 0)
        mock_post.return_value = mock_resp

        with self.assertRaises(ValueError) as ctx:
            create_instagram_reel_container(
                ig_user_id="17841400000000001",
                access_token="EAA_mock_token",
                video_url="https://cdn.example.com/reel.mp4"
            )
        self.assertIn("Invalid JSON", str(ctx.exception))

    @patch("requests.get")
    def test_14_container_processing_in_progress_polling(self, mock_get):
        """Test poll_instagram_container_status polls IN_PROGRESS then succeeds on FINISHED."""
        resp_progress = MagicMock(status_code=200, json=lambda: {"status_code": "IN_PROGRESS"})
        resp_finished = MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"})
        mock_get.side_effect = [resp_progress, resp_progress, resp_finished]

        ready = poll_instagram_container_status(
            creation_id="c_123",
            access_token="EAA_token",
            max_wait_seconds=2,
            poll_interval_seconds=0.01
        )
        self.assertTrue(ready)
        self.assertEqual(mock_get.call_count, 3)

    @patch("requests.get")
    def test_15_container_processing_finished_flow(self, mock_get):
        """Test immediate FINISHED container status returns True on first poll."""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"})
        ready = poll_instagram_container_status(creation_id="c_123", access_token="EAA_token")
        self.assertTrue(ready)
        self.assertEqual(mock_get.call_count, 1)

    @patch("requests.get")
    def test_16_container_processing_error_flow(self, mock_get):
        """Test container processing ERROR from Meta raises descriptive error."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "ERROR", "status": "Video codec unsupported. Please use H.264."}
        )
        with self.assertRaises(ValueError) as ctx:
            poll_instagram_container_status(creation_id="c_123", access_token="EAA_token", max_wait_seconds=1)
        self.assertIn("Video codec unsupported", str(ctx.exception))

    @patch("requests.get")
    def test_17_container_processing_timeout(self, mock_get):
        """Test container processing exceeding max wait time raises TimeoutError."""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status_code": "IN_PROGRESS"})
        with self.assertRaises(TimeoutError):
            poll_instagram_container_status(
                creation_id="c_123",
                access_token="EAA_token",
                max_wait_seconds=0.1,
                poll_interval_seconds=0.02
            )

    @patch("requests.post")
    @patch("requests.get")
    def test_18_final_publish_success(self, mock_get, mock_post):
        """Test full end-to-end Instagram Reel publishing pipeline."""
        cid = self._insert_social_content(user_id=self.user1_id, title="Amazing Sunset Reel", desc="Nature vibes", tags="#nature #sunset")
        aid = self._insert_instagram_account(user_id=self.user1_id)

        # Container creation & Publish
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "creation_container_888"}),
            MagicMock(status_code=200, json=lambda: {"id": "ig_media_777777"})
        ]

        # Status check & Permalink
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://www.instagram.com/reel/CXYZ_sunset/"})
        ]

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["publish_status"], "PUBLISHED")
        self.assertEqual(data["publish_id"], "ig_media_777777")
        self.assertEqual(data["publish_url"], "https://www.instagram.com/reel/CXYZ_sunset/")

        # Verify DB records
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT platform_status, processing_status, platform_post_id, platform_post_url
            FROM social_content_platforms WHERE content_id = %s;
        """, (cid,))
        p_status, proc_status, post_id, post_url = cur.fetchone()
        self.assertEqual(p_status, "PUBLISHED")
        self.assertEqual(proc_status, "READY")
        self.assertEqual(post_id, "ig_media_777777")

        cur.execute("SELECT overall_status FROM social_content WHERE id = %s;", (cid,))
        self.assertEqual(cur.fetchone()[0], "PUBLISHED")
        cur.close()
        conn.close()

    @patch("requests.post")
    def test_19_final_publish_response_missing_media_id(self, mock_post):
        """Test Meta publish response missing media ID fails safely."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # Missing 'id'
        mock_post.return_value = mock_resp

        with self.assertRaises(ValueError) as ctx:
            publish_instagram_container(ig_user_id="17841400000000001", creation_id="c_123", access_token="tok")
        self.assertIn("missing final media ID", str(ctx.exception))

    @patch("requests.post")
    def test_20_final_publish_meta_failure(self, mock_post):
        """Test Meta media_publish endpoint failure raises sanitized error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "Media container has expired or already been published.",
                "code": 100
            }
        }
        mock_post.return_value = mock_resp

        with self.assertRaises(ValueError) as ctx:
            publish_instagram_container(ig_user_id="17841400000000001", creation_id="c_123", access_token="tok")
        self.assertIn("Media container has expired", str(ctx.exception))

    @patch("requests.post")
    def test_21_network_timeout_handling(self, mock_post):
        """Test requests.exceptions.Timeout on Meta API calls is caught and handled safely."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = requests.exceptions.Timeout("Read timeout after 30s")

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Temporary failure connecting", data["error"])

    @patch("requests.post")
    def test_22_transient_5xx_handling(self, mock_post):
        """Test Meta HTTP 503 Service Unavailable is handled cleanly."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.return_value = MagicMock(status_code=503, text="Service Unavailable", json=lambda: {})

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Meta Reel container creation failed (HTTP 503)", data["error"])

    @patch("requests.post")
    @patch("requests.get")
    def test_23_publish_attempt_recorded(self, mock_get, mock_post):
        """Test audit trail record is created in social_publish_attempts with status SUCCESS."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_attempt_test"}),
            MagicMock(status_code=200, json=lambda: {"id": "ig_media_attempt_test"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/123/"})
        ]

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT spa.status, spa.attempt_number, spa.duration_ms, spa.completed_at
            FROM social_publish_attempts spa
            JOIN social_content_platforms scp ON spa.content_platform_id = scp.id
            WHERE scp.content_id = %s;
        """, (cid,))
        attempt_row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(attempt_row)
        status, attempt_no, duration, completed_at = attempt_row
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(attempt_no, 1)
        self.assertIsNotNone(completed_at)

    @patch("requests.post")
    @patch("requests.get")
    def test_24_publish_status_transitions_processing_to_published(self, mock_get, mock_post):
        """Test platform_status transitions to PUBLISHED."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_trans"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_trans"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/trans/"})
        ]

        self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, processing_status FROM social_content_platforms WHERE content_id = %s;", (cid,))
        p_stat, proc_stat = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(p_stat, "PUBLISHED")
        self.assertEqual(proc_stat, "READY")

    @patch("requests.post")
    def test_25_failed_attempt_transitions_to_failed(self, mock_post):
        """Test on error, platform_status and publish_attempt are marked FAILED."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.return_value = MagicMock(status_code=400, json=lambda: {"error": {"message": "Invalid video aspect ratio."}})

        self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, error_message FROM social_content_platforms WHERE content_id = %s;", (cid,))
        p_stat, err_msg = cur.fetchone()
        self.assertEqual(p_stat, "FAILED")
        self.assertIn("Invalid video aspect ratio", err_msg)

        cur.execute("SELECT status, error_message FROM social_publish_attempts WHERE error_message IS NOT NULL;")
        att_stat, att_err = cur.fetchone()
        self.assertEqual(att_stat, "FAILED")
        self.assertIn("Invalid video aspect ratio", att_err)
        cur.close()
        conn.close()

    def test_26_encrypted_tokens_never_exposed(self):
        """Test encrypted and decrypted tokens are never echoed in error responses."""
        cid = self._insert_social_content(user_id=self.user1_id)
        secret_token = "EAA_super_secret_token_never_expose"
        aid = self._insert_instagram_account(user_id=self.user1_id, token=secret_token)

        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception(f"Failed with access_token={secret_token}")
            res = self.app.post(
                "/api/social-media/publish/instagram",
                json={"content_id": cid, "account_id": aid},
                headers=self.headers_user1
            )
            self.assertNotIn(secret_token, res.get_data(as_text=True))
            self.assertIn("[REDACTED]", res.get_data(as_text=True))

    @patch("requests.post")
    @patch("requests.get")
    def test_27_tokens_absent_from_response_payload(self, mock_get, mock_post):
        """Test successful publish response never contains any token fields."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_resp_clean"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_resp_clean"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/clean/"})
        ]

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        data = res.get_json()

        for forbidden in ("token", "access_token", "encrypted_access_token", "client_secret", "secret"):
            self.assertNotIn(forbidden, data)

    @patch("requests.post")
    @patch("requests.get")
    def test_28_tokens_absent_from_publish_attempt_record(self, mock_get, mock_post):
        """Test social_publish_attempts records do not store any token data."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_att_clean"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_att_clean"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/att_clean/"})
        ]

        self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM social_publish_attempts;")
        columns = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        cur.close()
        conn.close()

        row_dict = dict(zip(columns, row))
        for key, val in row_dict.items():
            self.assertFalse(str(val).startswith("EAA"))
            self.assertFalse(str(val).startswith("gAAAAA"))

    @patch("requests.post")
    @patch("requests.get")
    def test_29_source_temp_video_retained_on_disk(self, mock_get, mock_post):
        """Test local temporary video file is STRICTLY retained on disk after Instagram publish."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_retain"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_retain"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/retain/"})
        ]

        self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )

        # 1. Verify physical file is still on disk
        self.assertTrue(os.path.exists(self.dummy_media_path))

        # 2. Verify temp_file_deleted remains FALSE in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT temp_file_deleted FROM social_content WHERE id = %s;", (cid,))
        self.assertFalse(cur.fetchone()[0])
        cur.close()
        conn.close()

    def test_30_existing_youtube_publishing_remains_unaffected(self):
        """Test YouTube publishing service functions are intact and importable."""
        from services.youtube_publish_service import validate_youtube_metadata
        res = validate_youtube_metadata(title="YouTube Test", description="Desc", tags="tag1,tag2", privacy="PUBLIC")
        self.assertEqual(res["title"], "YouTube Test")
        self.assertEqual(res["privacy"], "PUBLIC")

    def test_31_rejection_of_local_filesystem_path_as_video_url(self):
        """Test resolve_instagram_video_url strictly rejects local filesystem paths."""
        with self.assertRaises(ValueError) as ctx:
            resolve_instagram_video_url(content_id=1, temp_media_path="video.mp4", custom_video_url="/Users/admin/video.mp4")
        self.assertIn("Invalid custom video URL", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            resolve_instagram_video_url(content_id=1, temp_media_path="video.mp4", custom_video_url="C:\\Users\\video.mp4")
        self.assertIn("Invalid custom video URL", str(ctx2.exception))

    def test_32_missing_public_media_configuration_fails_safely(self):
        """Test missing INSTAGRAM_MEDIA_BASE_URL fails safely with clear configuration error."""
        Config.INSTAGRAM_MEDIA_BASE_URL = ""
        with self.assertRaises(ValueError) as ctx:
            resolve_instagram_video_url(content_id=1, temp_media_path="video.mp4")
        self.assertIn("Instagram Reel publishing requires a publicly accessible video URL", str(ctx.exception))

    def test_33_caption_formatting_helper(self):
        """Test format_instagram_caption with title, description, hashtags, deduplication, and bounds."""
        # 1. Normal format
        cap1 = format_instagram_caption(
            title="My Great Reel",
            description="Behind the scenes footage",
            hashtags="#reels, #behindthescenes, reels, #filmmaking"
        )
        self.assertIn("My Great Reel", cap1)
        self.assertIn("Behind the scenes footage", cap1)
        self.assertIn("#reels", cap1)
        self.assertIn("#behindthescenes", cap1)
        self.assertIn("#filmmaking", cap1)
        # Deduplicated
        self.assertEqual(cap1.count("#reels"), 1)

        # 2. Max length bound (2200 characters)
        long_desc = "A" * 3000
        cap2 = format_instagram_caption(title="Title", description=long_desc)
        self.assertLessEqual(len(cap2), 2200)
        self.assertTrue(cap2.endswith("..."))

    def test_34_public_media_streaming_route(self):
        """Test GET /api/social-media/public-media/<content_id>/<filename> streams file safely."""
        cid = self._insert_social_content(user_id=self.user1_id, temp_filename=self.dummy_media_filename)

        res = self.app.get(f"/api/social-media/public-media/{cid}/{self.dummy_media_filename}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, b"mock_mp4_video_data_for_testing_purposes")

        # Wrong filename returns 404
        res_bad = self.app.get(f"/api/social-media/public-media/{cid}/wrong_filename.mp4")
        self.assertEqual(res_bad.status_code, 404)


if __name__ == "__main__":
    unittest.main()
