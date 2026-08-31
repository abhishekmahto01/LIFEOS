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
from services.social_publish_service import (
    publish_content_to_platforms,
    SUPPORTED_PLATFORMS,
    MAX_PLATFORM_TARGETS
)


class TestUnifiedPublishing(unittest.TestCase):

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
        Config.INSTAGRAM_MAX_PUBLISH_RETRIES = 3
        Config.INSTAGRAM_PUBLISH_LEASE_SECONDS = 300

        Config.GOOGLE_CLIENT_ID = "mock_google_id"
        Config.GOOGLE_CLIENT_SECRET = "mock_google_secret"
        Config.YOUTUBE_PROCESSING_POLL_INTERVAL_SECONDS = 0.05
        Config.YOUTUBE_PROCESSING_MAX_POLLS_PER_RUN = 2
        Config.YOUTUBE_PUBLISH_LEASE_SECONDS = 300

        # Create physical dummy media file
        os.makedirs(Config.TEMP_UPLOAD_DIR, exist_ok=True)
        self.dummy_media_filename = "test_unified_video.mp4"
        self.dummy_media_path = os.path.join(Config.TEMP_UPLOAD_DIR, self.dummy_media_filename)
        with open(self.dummy_media_path, "wb") as f:
            f.write(b"mock_mp4_video_data_for_unified_publishing_tests")

    def tearDown(self):
        if os.path.exists(self.dummy_media_path):
            try:
                os.remove(self.dummy_media_path)
            except Exception:
                pass

    def _insert_account(self, user_id=1, platform="YOUTUBE", platform_acc_id="UC123", status="ACTIVE", token="valid_tok"):
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
                %s, %s, %s, %s, %s,
                'https://example.com/pic.jpg', %s, %s, %s,
                'scope1,scope2', '{"test": true}'::jsonb
            )
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                connection_status = EXCLUDED.connection_status
            RETURNING id;
        """, (user_id, platform, platform_acc_id, f"{platform} Account", f"user_{platform.lower()}", enc, future_exp, status))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return acc_id

    def _insert_social_content(self, user_id=1, title="Unified Post", desc="Common Caption", tags="#lifeos #tech", temp_filename=None, deleted=False, expired=False):
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

    def test_01_jwt_required_on_unified_publish_endpoint(self):
        """Test POST /api/social-media/publish requires valid JWT authorization."""
        res = self.app.post("/api/social-media/publish", json={"content_id": 1, "targets": [{"platform": "YOUTUBE", "account_id": 1}]})
        self.assertEqual(res.status_code, 401)

        res_bad = self.app.post("/api/social-media/publish", json={"content_id": 1}, headers={"Authorization": "Bearer invalid_token"})
        self.assertEqual(res_bad.status_code, 401)

    def test_02_missing_content_id_rejected(self):
        """Test missing content_id returns 400."""
        res = self.app.post("/api/social-media/publish", json={"targets": [{"platform": "YOUTUBE", "account_id": 1}]}, headers=self.headers_user1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("content_id is required", res.get_json()["error"])

    def test_03_invalid_negative_content_id_rejected(self):
        """Test non-integer or negative content_id returns 400."""
        res1 = self.app.post("/api/social-media/publish", json={"content_id": -5, "targets": [{"platform": "YOUTUBE", "account_id": 1}]}, headers=self.headers_user1)
        self.assertEqual(res1.status_code, 400)

        res2 = self.app.post("/api/social-media/publish", json={"content_id": "abc", "targets": [{"platform": "YOUTUBE", "account_id": 1}]}, headers=self.headers_user1)
        self.assertEqual(res2.status_code, 400)

    def test_04_content_ownership_enforced(self):
        """Test User 1 cannot publish User 2's content."""
        cid_user2 = self._insert_social_content(user_id=self.user2_id)
        aid_user1 = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_u1")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid_user2, "targets": [{"platform": "YOUTUBE", "account_id": aid_user1}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Content item not found or access denied", res.get_json()["error"])

    def test_05_targets_required_and_empty_targets_rejected(self):
        """Test missing or empty targets list returns 400."""
        cid = self._insert_social_content(user_id=self.user1_id)
        res1 = self.app.post("/api/social-media/publish", json={"content_id": cid}, headers=self.headers_user1)
        self.assertEqual(res1.status_code, 400)

        res2 = self.app.post("/api/social-media/publish", json={"content_id": cid, "targets": []}, headers=self.headers_user1)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("cannot be empty", res2.get_json()["error"])

    def test_06_malformed_target_rejected(self):
        """Test target missing platform or account_id returns 400."""
        cid = self._insert_social_content(user_id=self.user1_id)

        res1 = self.app.post("/api/social-media/publish", json={"content_id": cid, "targets": [{"account_id": 1}]}, headers=self.headers_user1)
        self.assertEqual(res1.status_code, 400)
        self.assertIn("Platform is required", res1.get_json()["error"])

        res2 = self.app.post("/api/social-media/publish", json={"content_id": cid, "targets": [{"platform": "YOUTUBE"}]}, headers=self.headers_user1)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Valid account_id required", res2.get_json()["error"])

    def test_07_unsupported_platform_rejected(self):
        """Test unsupported platform (e.g. FACEBOOK, TIKTOK) returns 400."""
        cid = self._insert_social_content(user_id=self.user1_id)
        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "FACEBOOK", "account_id": 1}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported platform 'FACEBOOK'", res.get_json()["error"])

    def test_08_duplicate_exact_targets_rejected(self):
        """Test duplicate targets with same platform and account_id return 400."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_dup")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid},
                {"platform": "YOUTUBE", "account_id": aid}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Duplicate target specified", res.get_json()["error"])

    def test_09_account_ownership_enforced(self):
        """Test User 1 cannot target User 2's account ID."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_user2 = self._insert_account(user_id=self.user2_id, platform="YOUTUBE", platform_acc_id="UC_u2")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_user2}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Account ID", res.get_json()["error"])

    def test_10_account_platform_mismatch_rejected(self):
        """Test requesting platform YOUTUBE with an INSTAGRAM account ID returns 400."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140001")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_ig}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("is for INSTAGRAM, but target requested YOUTUBE", res.get_json()["error"])

    @patch("services.social_publish_service.publish_youtube")
    def test_11_single_target_youtube_unified_publish(self, mock_yt):
        """Test single-target YouTube unified publishing succeeds."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_single_yt")

        mock_yt.return_value = {
            "success": True,
            "platform": "YOUTUBE",
            "account_id": aid_yt,
            "publish_status": "PUBLISHED",
            "publish_id": "yt_video_111",
            "publish_url": "https://www.youtube.com/watch?v=yt_video_111",
            "already_published": False
        }

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_yt}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["platform"], "YOUTUBE")
        self.assertEqual(data["results"][0]["publish_id"], "yt_video_111")

    @patch("services.social_publish_service.publish_instagram_reel")
    def test_12_single_target_instagram_unified_publish(self, mock_ig):
        """Test single-target Instagram unified publishing succeeds."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140002")

        mock_ig.return_value = {
            "success": True,
            "platform": "INSTAGRAM",
            "content_id": cid,
            "account_id": aid_ig,
            "publish_status": "PUBLISHED",
            "publish_id": "ig_media_222",
            "publish_url": "https://www.instagram.com/reel/222/",
            "already_published": False
        }

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "INSTAGRAM", "account_id": aid_ig}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["platform"], "INSTAGRAM")
        self.assertEqual(data["results"][0]["publish_id"], "ig_media_222")

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_13_multi_platform_youtube_and_instagram_both_succeed(self, mock_ig, mock_yt):
        """Test multi-platform publishing where both YouTube and Instagram succeed."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_both")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140003")

        mock_yt.return_value = {
            "success": True, "platform": "YOUTUBE", "account_id": aid_yt,
            "publish_status": "PUBLISHED", "publish_id": "yt_both_123", "publish_url": "https://youtube.com/watch?v=yt_both_123"
        }
        mock_ig.return_value = {
            "success": True, "platform": "INSTAGRAM", "account_id": aid_ig,
            "publish_status": "PUBLISHED", "publish_id": "ig_both_456", "publish_url": "https://instagram.com/reel/ig_both_456/"
        }

        # Seed platform rows
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'PUBLISHED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["overall_status"], "PUBLISHED")
        self.assertEqual(len(data["results"]), 2)

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_14_youtube_succeeds_instagram_fails(self, mock_ig, mock_yt):
        """Test YouTube succeeds but Instagram fails -> overall_status is PARTIALLY_PUBLISHED and success is False."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_part")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140004")

        mock_yt.return_value = {
            "success": True, "platform": "YOUTUBE", "account_id": aid_yt,
            "publish_status": "PUBLISHED", "publish_id": "yt_part_1", "publish_url": "https://youtube.com/watch?v=yt_part_1"
        }
        mock_ig.return_value = {
            "success": False, "platform": "INSTAGRAM", "account_id": aid_ig,
            "publish_status": "FAILED", "error": "Instagram rate limit reached", "retry_allowed": True
        }

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'FAILED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["overall_status"], "PARTIALLY_PUBLISHED")

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_15_youtube_fails_instagram_succeeds(self, mock_ig, mock_yt):
        """Test YouTube fails but Instagram succeeds -> overall_status is PARTIALLY_PUBLISHED."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_fail")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140005")

        mock_yt.return_value = {
            "success": False, "platform": "YOUTUBE", "account_id": aid_yt,
            "publish_status": "FAILED", "error": "YouTube quota exceeded"
        }
        mock_ig.return_value = {
            "success": True, "platform": "INSTAGRAM", "account_id": aid_ig,
            "publish_status": "PUBLISHED", "publish_id": "ig_success_5", "publish_url": "https://instagram.com/reel/5/"
        }

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'FAILED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'PUBLISHED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["overall_status"], "PARTIALLY_PUBLISHED")

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_16_both_platforms_fail(self, mock_ig, mock_yt):
        """Test both platforms fail -> overall_status is FAILED."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_both_fail")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140006")

        mock_yt.return_value = {"success": False, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "FAILED", "error": "YT Error"}
        mock_ig.return_value = {"success": False, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "FAILED", "error": "IG Error"}

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'FAILED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'FAILED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["overall_status"], "FAILED")

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_17_failure_on_first_platform_does_not_abort_second_platform(self, mock_ig, mock_yt):
        """Test failure isolation: when YouTube fails first, Instagram is still dispatched."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_iso")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140007")

        mock_yt.side_effect = Exception("YouTube catastrophic crash")
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_iso_7"}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        mock_ig.assert_called_once()

    def test_18_shared_temporary_media_retained_on_multi_platform_publish(self):
        """Test physical video file remains on disk throughout multi-platform orchestration."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_retain")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140008")

        with patch("services.social_publish_service.publish_youtube") as mock_yt, \
             patch("services.social_publish_service.publish_instagram_reel") as mock_ig:

            mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_ret_1"}
            mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_ret_1"}

            self.app.post(
                "/api/social-media/publish",
                json={"content_id": cid, "targets": [
                    {"platform": "YOUTUBE", "account_id": aid_yt},
                    {"platform": "INSTAGRAM", "account_id": aid_ig}
                ]},
                headers=self.headers_user1
            )

            # Physical file must still exist
            self.assertTrue(os.path.exists(self.dummy_media_path))

            # Database flag temp_file_deleted must be False
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT temp_file_deleted FROM social_content WHERE id = %s;", (cid,))
            self.assertFalse(cur.fetchone()[0])
            cur.close()
            conn.close()

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_19_duplicate_unified_publish_does_not_republish_already_published(self, mock_ig, mock_yt):
        """Test repeating unified publish when platforms are already PUBLISHED returns already_published without re-calling APIs."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_idemp")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140009")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_idemp", "already_published": True}
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_idemp", "already_published": True}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["results"][0]["already_published"])
        self.assertTrue(data["results"][1]["already_published"])

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_20_retry_via_unified_publish_retries_failed_instagram_while_keeping_youtube(self, mock_ig, mock_yt):
        """Test calling unified publish again on a partially published post retries only failed targets."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_retry")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140010")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_keep", "already_published": True}
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_now_ok", "already_published": False}

        # Update DB to reflect both published
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'PUBLISHED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["overall_status"], "PUBLISHED")

    @patch("services.social_publish_service.publish_youtube")
    def test_21_youtube_platform_options_applied(self, mock_yt):
        """Test options (e.g. privacy_status='PRIVATE', category_id='24') are passed to YouTube publisher."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_opts")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_opt_vid"}

        self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt, "options": {"privacy_status": "PRIVATE", "category_id": "24", "made_for_kids": True}}
            ]},
            headers=self.headers_user1
        )

        mock_yt.assert_called_once()
        passed_options = mock_yt.call_args[1]["options"]
        self.assertEqual(passed_options["privacy_status"], "PRIVATE")
        self.assertEqual(passed_options["category_id"], "24")
        self.assertTrue(passed_options["made_for_kids"])

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_22_zero_token_and_secret_exposure_in_response(self, mock_ig, mock_yt):
        """Test unified publish response never leaks tokens or client secrets."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_clean")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140011")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_clean"}
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_clean"}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        body = res.get_data(as_text=True)
        for secret_pattern in ("access_token", "encrypted_access_token", "client_secret", "EAA", "ya29"):
            self.assertNotIn(secret_pattern, body)

    def test_23_expired_media_rejected_with_410_before_dispatch(self):
        """Test expired media returns 410 before calling any publisher."""
        cid = self._insert_social_content(user_id=self.user1_id, expired=True)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_exp")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_yt}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 410)
        self.assertIn("expired", res.get_json()["error"].lower())

    def test_24_max_targets_limit_enforced(self):
        """Test exceeding MAX_PLATFORM_TARGETS (5) returns 400."""
        cid = self._insert_social_content(user_id=self.user1_id)
        targets = [{"platform": "YOUTUBE", "account_id": i + 1} for i in range(MAX_PLATFORM_TARGETS + 1)]

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": targets},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(f"Maximum of {MAX_PLATFORM_TARGETS} targets", res.get_json()["error"])

    def test_25_standalone_youtube_endpoint_remains_intact(self):
        """Test standalone POST /api/social-media/content/<id>/publish/youtube continues to work."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_stand")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'PENDING');", (cid, aid))
        conn.commit()
        cur.close()
        conn.close()

        with patch("routes.social_routes.start_youtube_publish_task") as mock_task:
            res = self.app.post(f"/api/social-media/content/{cid}/publish/youtube", headers=self.headers_user1)
            self.assertEqual(res.status_code, 200)
            mock_task.assert_called_once()

    def test_26_standalone_instagram_endpoint_remains_intact(self):
        """Test standalone POST /api/social-media/publish/instagram continues to work."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140012")

        with patch("routes.social_routes.publish_instagram_reel") as mock_ig:
            mock_ig.return_value = {"success": True, "publish_status": "PUBLISHED", "publish_id": "ig_12"}
            res = self.app.post(
                "/api/social-media/publish/instagram",
                json={"content_id": cid, "account_id": aid},
                headers=self.headers_user1
            )
            self.assertEqual(res.status_code, 200)
            mock_ig.assert_called_once()

    def test_27_standalone_instagram_retry_endpoint_remains_intact(self):
        """Test standalone POST /api/social-media/content/<id>/retry/instagram continues to work."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140013")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'FAILED');", (cid, aid))
        conn.commit()
        cur.close()
        conn.close()

        with patch("routes.social_routes.publish_instagram_reel") as mock_ig:
            mock_ig.return_value = {"success": True, "publish_status": "PUBLISHED", "publish_id": "ig_retry_ok"}
            res = self.app.post(
                f"/api/social-media/content/{cid}/retry/instagram",
                json={"account_id": aid},
                headers=self.headers_user1
            )
            self.assertEqual(res.status_code, 200)
            mock_ig.assert_called_once()

    def test_28_cross_user_account_rejected_in_multi_target(self):
        """Test multi-target request fails with 404 if any target account is not owned by user."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_u1 = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_own")
        aid_u2 = self._insert_account(user_id=self.user2_id, platform="INSTAGRAM", platform_acc_id="1784140099")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_u1},
                {"platform": "INSTAGRAM", "account_id": aid_u2}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found or access denied", res.get_json()["error"])

    def test_29_missing_media_file_on_disk_rejected_with_410(self):
        """Test missing physical media file on disk returns 410."""
        cid = self._insert_social_content(user_id=self.user1_id, temp_filename="ghost_video.mp4")
        aid = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_ghost")

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 410)
        self.assertIn("not found on disk", res.get_json()["error"])

    @patch("services.social_publish_service.publish_youtube")
    def test_30_unknown_option_keys_sanitized_safely(self, mock_yt):
        """Test extra/unknown option keys do not cause crashes and are handled safely."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_extra")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid, "publish_status": "PUBLISHED", "publish_id": "yt_extra"}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid, "options": {"privacy_status": "PUBLIC", "unsafe_key": "DROP TABLE", "nested": {"bad": 1}}}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

    @patch("services.social_publish_service.publish_youtube")
    def test_31_multiple_accounts_different_ids_allowed_if_owned(self, mock_yt):
        """Test multiple distinct accounts for same platform are allowed if owned by user."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid1 = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_chan1")
        aid2 = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_chan2")

        mock_yt.side_effect = [
            {"success": True, "platform": "YOUTUBE", "account_id": aid1, "publish_status": "PUBLISHED", "publish_id": "yt_c1"},
            {"success": True, "platform": "YOUTUBE", "account_id": aid2, "publish_status": "PUBLISHED", "publish_id": "yt_c2"}
        ]

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid1},
                {"platform": "YOUTUBE", "account_id": aid2}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["account_id"], aid1)
        self.assertEqual(data["results"][1]["account_id"], aid2)

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_32_results_preserve_platform_independence(self, mock_ig, mock_yt):
        """Test result structure is cleanly decoupled and standard across platforms."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_indep")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140032")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_indep", "publish_url": "https://youtube.com/watch?v=yt_indep"}
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_indep", "publish_url": "https://instagram.com/reel/ig_indep/"}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "YOUTUBE", "account_id": aid_yt},
                {"platform": "INSTAGRAM", "account_id": aid_ig}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["platform"], "YOUTUBE")
        self.assertEqual(data["results"][1]["platform"], "INSTAGRAM")

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_33_duplicate_api_calls_remain_consistent(self, mock_ig, mock_yt):
        """Test calling unified publish repeatedly returns consistent responses."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_cons")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140033")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED", "publish_id": "yt_cons", "already_published": True}
        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_cons", "already_published": True}

        res1 = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_yt}, {"platform": "INSTAGRAM", "account_id": aid_ig}]},
            headers=self.headers_user1
        )
        res2 = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_yt}, {"platform": "INSTAGRAM", "account_id": aid_ig}]},
            headers=self.headers_user1
        )
        self.assertEqual(res1.status_code, res2.status_code)
        self.assertEqual(len(res1.get_json()["results"]), len(res2.get_json()["results"]))

    @patch("services.social_publish_service.publish_youtube")
    @patch("services.social_publish_service.publish_instagram_reel")
    def test_34_overall_status_recalculated_safely(self, mock_ig, mock_yt):
        """Test social_content overall_status reflects aggregation accurately."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_yt = self._insert_account(user_id=self.user1_id, platform="YOUTUBE", platform_acc_id="UC_yt_agg")
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140034")

        mock_yt.return_value = {"success": True, "platform": "YOUTUBE", "account_id": aid_yt, "publish_status": "PUBLISHED"}
        mock_ig.return_value = {"success": False, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "FAILED"}

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED');", (cid, aid_yt))
        cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status) VALUES (%s, %s, 'INSTAGRAM', 'FAILED');", (cid, aid_ig))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [{"platform": "YOUTUBE", "account_id": aid_yt}, {"platform": "INSTAGRAM", "account_id": aid_ig}]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["overall_status"], "PARTIALLY_PUBLISHED")

    @patch("services.social_publish_service.publish_instagram_reel")
    def test_35_orchestrator_passes_custom_video_url_to_instagram(self, mock_ig):
        """Test custom_video_url option is forwarded to Instagram publisher."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_ig = self._insert_account(user_id=self.user1_id, platform="INSTAGRAM", platform_acc_id="1784140035")

        mock_ig.return_value = {"success": True, "platform": "INSTAGRAM", "account_id": aid_ig, "publish_status": "PUBLISHED", "publish_id": "ig_custom"}

        res = self.app.post(
            "/api/social-media/publish",
            json={"content_id": cid, "targets": [
                {"platform": "INSTAGRAM", "account_id": aid_ig, "options": {"custom_video_url": "https://cdn.example.com/stream/v123.mp4"}}
            ]},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        mock_ig.assert_called_once()
        self.assertEqual(mock_ig.call_args[1]["custom_video_url"], "https://cdn.example.com/stream/v123.mp4")


if __name__ == "__main__":
    unittest.main()

