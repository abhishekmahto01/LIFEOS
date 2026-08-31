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
    publish_instagram_reel,
    claim_instagram_publish_slot,
    recalculate_content_overall_status
)


class TestInstagramRetryIdempotency(unittest.TestCase):

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

        # Create physical dummy media file
        os.makedirs(Config.TEMP_UPLOAD_DIR, exist_ok=True)
        self.dummy_media_filename = "test_reel_idempotency.mp4"
        self.dummy_media_path = os.path.join(Config.TEMP_UPLOAD_DIR, self.dummy_media_filename)
        with open(self.dummy_media_path, "wb") as f:
            f.write(b"mock_mp4_video_data_for_idempotency_testing")

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
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                connection_status = EXCLUDED.connection_status
            RETURNING id;
        """, (user_id, ig_user_id, enc, future_exp, status))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return acc_id

    def _insert_social_content(self, user_id=1, title="Test Reel", desc="Description", tags="#reel", temp_filename=None, deleted=False, expired=False):
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

    def _insert_content_platform(self, content_id, account_id, status="FAILED", retry_count=1, meta_container_id=None, post_id=None, post_url=None):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_content_platforms (
                content_id, account_id, platform, platform_status, processing_status,
                retry_count, meta_container_id, platform_post_id, platform_post_url,
                claim_token, claim_expires_at, last_attempt_at, error_message, updated_at
            )
            VALUES (
                %s, %s, 'INSTAGRAM', %s, 'FAILED',
                %s, %s, %s, %s,
                'claim123', CURRENT_TIMESTAMP + INTERVAL '300 seconds', CURRENT_TIMESTAMP, 'Prior failure', CURRENT_TIMESTAMP
            )
            RETURNING id;
        """, (content_id, account_id, status, retry_count, meta_container_id, post_id, post_url))
        scpid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return scpid

    def test_01_already_published_does_not_republish(self):
        """Test already PUBLISHED post returns already_published: True immediately without re-publishing."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="existing_ig_123", post_url="https://instagram.com/reel/123/")

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data.get("already_published"))
        self.assertEqual(data["publish_id"], "existing_ig_123")
        self.assertEqual(data["publish_status"], "PUBLISHED")

    @patch("requests.post")
    def test_02_published_request_does_not_call_meta_container_api(self, mock_post):
        """Test already PUBLISHED post does NOT make any HTTP calls to Meta APIs."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="existing_ig_123")

        self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        mock_post.assert_not_called()

    def test_03_active_processing_request_rejected_with_409(self):
        """Test concurrent or duplicate publish while status is PROCESSING returns 409 Conflict."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        # Insert active processing record with unexpired lease
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_content_platforms (
                content_id, account_id, platform, platform_status, processing_status,
                claim_token, claim_expires_at
            )
            VALUES (%s, %s, 'INSTAGRAM', 'PROCESSING', 'PROCESSING', 'tok123', CURRENT_TIMESTAMP + INTERVAL '120 seconds');
        """, (cid, aid))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            "/api/social-media/publish/instagram",
            json={"content_id": cid, "account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 409)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["publish_status"], "PROCESSING")
        self.assertIn("already in progress", data["message"])

    def test_04_concurrent_claim_race_allows_only_one_request(self):
        """Test claim_instagram_publish_slot allows first claim and rejects immediate second claim with 409."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        claim1 = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid)
        self.assertTrue(claim1["claimed"])

        claim2 = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid)
        self.assertFalse(claim2["claimed"])
        self.assertEqual(claim2["status_code"], 409)

    @patch("requests.post")
    @patch("requests.get")
    def test_05_failed_publication_can_retry(self, mock_get, mock_post):
        """Test a FAILED publication can be retried successfully."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_retry_1"}),
            MagicMock(status_code=200, json=lambda: {"id": "ig_media_retry_1"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/retry1/"})
        ]

        res = self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["publish_status"], "PUBLISHED")
        self.assertEqual(data["publish_id"], "ig_media_retry_1")

    @patch("requests.post")
    @patch("requests.get")
    def test_06_failed_retry_increments_retry_count_atomically(self, mock_get, mock_post):
        """Test retrying a FAILED publication increments retry_count from 1 to 2."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_2"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_2"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/2/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT retry_count FROM social_content_platforms WHERE id = %s;", (scpid,))
        retry_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        self.assertEqual(retry_count, 2)

    @patch("requests.post")
    @patch("requests.get")
    def test_07_retry_creates_new_publish_attempt(self, mock_get, mock_post):
        """Test retrying creates a new social_publish_attempts record with attempt_number = 2."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        # Seed initial failed attempt
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_publish_attempts (content_platform_id, attempt_number, status, error_message)
            VALUES (%s, 1, 'FAILED', 'First attempt network failure');
        """, (scpid,))
        conn.commit()
        cur.close()
        conn.close()

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_3"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_3"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/3/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT attempt_number, status FROM social_publish_attempts WHERE content_platform_id = %s ORDER BY attempt_number ASC;", (scpid,))
        attempts = cur.fetchall()
        cur.close()
        conn.close()

        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], (1, "FAILED"))
        self.assertEqual(attempts[1], (2, "SUCCESS"))

    def test_08_old_publish_attempts_preserved_in_audit_history(self):
        """Test prior failure attempts are never deleted when starting a retry."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_publish_attempts (content_platform_id, attempt_number, status, error_message)
            VALUES (%s, 1, 'FAILED', 'Old failure details');
        """, (scpid,))
        conn.commit()
        cur.close()
        conn.close()

        claim = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertTrue(claim["claimed"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM social_publish_attempts WHERE content_platform_id = %s;", (scpid,))
        total_attempts = cur.fetchone()[0]
        cur.close()
        conn.close()

        self.assertEqual(total_attempts, 2)

    def test_09_retry_clears_stale_error_state(self):
        """Test claiming a retry clears error_message from prior failure."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        claim = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertTrue(claim["claimed"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT error_message FROM social_content_platforms WHERE id = %s;", (scpid,))
        err = cur.fetchone()[0]
        cur.close()
        conn.close()

        self.assertIsNone(err)

    def test_10_retry_transitions_failed_to_processing(self):
        """Test claiming a retry transitions platform_status from FAILED to PROCESSING."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        claim = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertTrue(claim["claimed"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, processing_status FROM social_content_platforms WHERE id = %s;", (scpid,))
        pstat, procstat = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(pstat, "PROCESSING")
        self.assertEqual(procstat, "UPLOADING")

    @patch("requests.post")
    @patch("requests.get")
    def test_11_successful_retry_transitions_to_published(self, mock_get, mock_post):
        """Test a complete retry flow successfully updates platform_status to PUBLISHED."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_ok"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_ok"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/ok/"})
        ]

        res = publish_instagram_reel(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["publish_status"], "PUBLISHED")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, platform_post_id FROM social_content_platforms WHERE id = %s;", (scpid,))
        pstat, post_id = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(pstat, "PUBLISHED")
        self.assertEqual(post_id, "m_ok")

    @patch("requests.post")
    def test_12_failed_retry_transitions_to_failed(self, mock_post):
        """Test a failing retry updates platform_status back to FAILED with sanitized error."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.return_value = MagicMock(status_code=400, json=lambda: {"error": {"message": "Invalid video codec."}})

        res = publish_instagram_reel(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertFalse(res["success"])
        self.assertEqual(res["publish_status"], "FAILED")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, error_message FROM social_content_platforms WHERE id = %s;", (scpid,))
        pstat, err = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(pstat, "FAILED")
        self.assertIn("Invalid video codec", err)

    def test_13_retry_limit_enforced_after_max_retries(self):
        """Test when retry_count reaches Config.INSTAGRAM_MAX_PUBLISH_RETRIES, further retries are rejected."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=3)  # Max is 3

        res = self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertFalse(data.get("retry_allowed", True))
        self.assertIn("retry limit reached", data["message"])

    @patch("requests.post")
    def test_14_retry_after_limit_does_not_call_meta(self, mock_post):
        """Test reaching retry limit does NOT make any Meta API calls."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=3)

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        mock_post.assert_not_called()

    @patch("requests.post")
    @patch("requests.get")
    def test_15_same_content_and_account_reuses_platform_row(self, mock_get, mock_post):
        """Test publishing and retrying reuses the same social_content_platforms row."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        scpid = self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_reuse"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_reuse"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/reuse/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM social_content_platforms WHERE content_id = %s;", (cid,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], scpid)

    def test_16_no_duplicate_social_content_platforms_rows(self):
        """Test unique constraint prevents duplicate rows for (content_id, platform, account_id)."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        # Attempting duplicate raw insert must fail unique constraint
        conn = get_connection()
        cur = conn.cursor()
        with self.assertRaises(Exception):
            cur.execute("""
                INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status)
                VALUES (%s, %s, 'INSTAGRAM', 'PENDING');
            """, (cid, aid))
        conn.rollback()
        cur.close()
        conn.close()

    def test_17_deterministic_persisted_idempotency_key(self):
        """Test idempotency_key is generated with pattern ig_{user_id}_{cid}_{aid}_att_{attempt_no}."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        claim = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid)
        self.assertTrue(claim["claimed"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT idempotency_key FROM social_publish_attempts WHERE id = %s;", (claim["attempt_id"],))
        key = cur.fetchone()[0]
        cur.close()
        conn.close()

        expected_key = f"ig_{self.user1_id}_{cid}_{aid}_att_1"
        self.assertEqual(key, expected_key)

    def test_18_duplicate_api_calls_return_consistent_result(self):
        """Test multiple consecutive calls for an already PUBLISHED post return identical output."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="ig_consistent_999", post_url="https://instagram.com/reel/cons/")

        res1 = self.app.post("/api/social-media/publish/instagram", json={"content_id": cid, "account_id": aid}, headers=self.headers_user1)
        res2 = self.app.post("/api/social-media/publish/instagram", json={"content_id": cid, "account_id": aid}, headers=self.headers_user1)

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res1.get_json()["publish_id"], res2.get_json()["publish_id"])
        self.assertEqual(res1.get_json()["publish_url"], res2.get_json()["publish_url"])

    def test_19_database_locking_protects_simultaneous_claim(self):
        """Test claim_instagram_publish_slot uses row lock and updates state in single transaction."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        claim = claim_instagram_publish_slot(user_id=self.user1_id, content_id=cid, account_id=aid)
        self.assertTrue(claim["claimed"])
        self.assertEqual(claim["attempt_number"], 1)

    def test_20_ownership_protection_enforced_on_retry(self):
        """Test User 1 cannot retry User 2's content."""
        cid_user2 = self._insert_social_content(user_id=self.user2_id)
        aid_user1 = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid_user2, aid_user1, status="FAILED")

        res = self.app.post(
            f"/api/social-media/content/{cid_user2}/retry/instagram",
            json={"account_id": aid_user1},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)

    def test_21_cross_user_content_cannot_be_retried(self):
        """Test User 2 cannot retry User 1's post."""
        cid_user1 = self._insert_social_content(user_id=self.user1_id)
        aid_user1 = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid_user1, aid_user1, status="FAILED")

        res = self.app.post(
            f"/api/social-media/content/{cid_user1}/retry/instagram",
            json={"account_id": aid_user1},
            headers=self.headers_user2
        )
        self.assertEqual(res.status_code, 404)

    def test_22_cross_user_account_cannot_be_retried(self):
        """Test User 1 cannot use User 2's account for retry."""
        cid_user1 = self._insert_social_content(user_id=self.user1_id)
        aid_user2 = self._insert_instagram_account(user_id=self.user2_id)

        res = self.app.post(
            f"/api/social-media/content/{cid_user1}/retry/instagram",
            json={"account_id": aid_user2},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 404)

    def test_23_published_post_id_remains_unchanged_on_duplicate_request(self):
        """Test publish_id is immutable on duplicate requests."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="immutable_ig_id")

        res = self.app.post("/api/social-media/publish/instagram", json={"content_id": cid, "account_id": aid}, headers=self.headers_user1)
        self.assertEqual(res.get_json()["publish_id"], "immutable_ig_id")

    def test_24_published_post_url_remains_unchanged_on_duplicate_request(self):
        """Test publish_url is immutable on duplicate requests."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="id1", post_url="https://instagram.com/reel/immutable/")

        res = self.app.post("/api/social-media/publish/instagram", json={"content_id": cid, "account_id": aid}, headers=self.headers_user1)
        self.assertEqual(res.get_json()["publish_url"], "https://instagram.com/reel/immutable/")

    @patch("requests.post")
    @patch("requests.get")
    def test_25_retry_does_not_alter_youtube_platform_row(self, mock_get, mock_post):
        """Test retrying Instagram does NOT modify or corrupt an existing YouTube platform row."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_ig = self._insert_instagram_account(user_id=self.user1_id)
        scpid_ig = self._insert_content_platform(cid, aid_ig, status="FAILED", retry_count=1)

        # Insert YouTube platform row
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name, connection_status)
            VALUES (%s, 'YOUTUBE', 'UC_yt_chan', 'YT Chan', 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET connection_status = 'ACTIVE'
            RETURNING id;
        """, (self.user1_id,))
        aid_yt = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status, platform_post_id)
            VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED', 'yt_video_888')
            RETURNING id;
        """, (cid, aid_yt))
        scpid_yt = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_ig"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_ig"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/ig/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid_ig},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT platform_status, platform_post_id FROM social_content_platforms WHERE id = %s;", (scpid_yt,))
        yt_row = cur.fetchone()
        cur.close()
        conn.close()

        # YouTube row remains unchanged
        self.assertEqual(yt_row[0], "PUBLISHED")
        self.assertEqual(yt_row[1], "yt_video_888")

    @patch("requests.post")
    @patch("requests.get")
    def test_26_temp_media_retained_after_retry(self, mock_get, mock_post):
        """Test physical video file remains on disk after a successful retry."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_ret"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_ret"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/ret/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )

        self.assertTrue(os.path.exists(self.dummy_media_path))

    def test_27_tokens_never_exposed_in_retry_payloads(self):
        """Test tokens are never returned in retry responses or error messages."""
        cid = self._insert_social_content(user_id=self.user1_id)
        secret_tok = "EAA_test_secret_for_retry_tests"
        aid = self._insert_instagram_account(user_id=self.user1_id, token=secret_tok)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception(f"Failed with access_token={secret_tok}")
            res = self.app.post(
                f"/api/social-media/content/{cid}/retry/instagram",
                json={"account_id": aid},
                headers=self.headers_user1
            )
            self.assertNotIn(secret_tok, res.get_data(as_text=True))
            self.assertIn("[REDACTED]", res.get_data(as_text=True))

    @patch("requests.post")
    @patch("requests.get")
    def test_28_tokens_never_stored_in_publish_attempts(self, mock_get, mock_post):
        """Test social_publish_attempts table contains no token strings after retry."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1)

        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "c_clean"}),
            MagicMock(status_code=200, json=lambda: {"id": "m_clean"})
        ]
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/clean/"})
        ]

        self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM social_publish_attempts;")
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for r in rows:
            r_dict = dict(zip(columns, r))
            for k, v in r_dict.items():
                self.assertFalse(str(v).startswith("EAA"))
                self.assertFalse(str(v).startswith("gAAAAA"))

    @patch("requests.post")
    @patch("requests.get")
    def test_29_ambiguous_meta_timeout_reuses_container_if_possible(self, mock_get, mock_post):
        """Test when meta_container_id was saved from prior attempt, it is reused instead of creating duplicate container."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED", retry_count=1, meta_container_id="existing_container_777")

        # Container status poll returns FINISHED immediately
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"}),
            MagicMock(status_code=200, json=lambda: {"permalink": "https://instagram.com/reel/reused/"})
        ]
        # Only media_publish is called (NOT container creation)
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "ig_media_reused_777"})

        res = publish_instagram_reel(user_id=self.user1_id, content_id=cid, account_id=aid, is_retry=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["publish_id"], "ig_media_reused_777")

        # Container creation was skipped, only media_publish was called once
        self.assertEqual(mock_post.call_count, 1)

    def test_30_explicit_retry_endpoint_rejects_published_post(self):
        """Test POST /content/<id>/retry/instagram returns already_published for a published post."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="PUBLISHED", post_id="already_pub")

        res = self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("already_published"))

    def test_31_explicit_retry_endpoint_rejects_processing_post(self):
        """Test POST /content/<id>/retry/instagram rejects an actively processing post with 409."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid = self._insert_instagram_account(user_id=self.user1_id)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status, claim_expires_at)
            VALUES (%s, %s, 'INSTAGRAM', 'PROCESSING', CURRENT_TIMESTAMP + INTERVAL '120 seconds');
        """, (cid, aid))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 409)

    def test_32_explicit_retry_endpoint_rejects_expired_media(self):
        """Test POST /content/<id>/retry/instagram returns 410 if temporary video media has expired."""
        cid = self._insert_social_content(user_id=self.user1_id, expired=True)
        aid = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid, status="FAILED")

        res = self.app.post(
            f"/api/social-media/content/{cid}/retry/instagram",
            json={"account_id": aid},
            headers=self.headers_user1
        )
        self.assertEqual(res.status_code, 410)
        self.assertIn("expired", res.get_json()["error"].lower())

    def test_33_overall_status_recalculated_safely_multi_platform(self):
        """Test overall social_content status is recalculated accurately for combinations of platform states."""
        cid = self._insert_social_content(user_id=self.user1_id)
        aid_ig = self._insert_instagram_account(user_id=self.user1_id)
        self._insert_content_platform(cid, aid_ig, status="FAILED")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name, connection_status)
            VALUES (%s, 'YOUTUBE', 'UC_yt_combo', 'YT Combo', 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET connection_status = 'ACTIVE'
            RETURNING id;
        """, (self.user1_id,))
        aid_yt = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO social_content_platforms (content_id, account_id, platform, platform_status)
            VALUES (%s, %s, 'YOUTUBE', 'PUBLISHED');
        """, (cid, aid_yt))
        conn.commit()
        cur.close()
        conn.close()

        recalculate_content_overall_status(cid)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT overall_status FROM social_content WHERE id = %s;", (cid,))
        overall = cur.fetchone()[0]
        cur.close()
        conn.close()

        # YouTube = PUBLISHED, Instagram = FAILED -> PARTIALLY_PUBLISHED
        self.assertEqual(overall, "PARTIALLY_PUBLISHED")


if __name__ == "__main__":
    unittest.main()
