import os
import sys
import json
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
from utils.crypto import decrypt_token, encrypt_token
from services.instagram_oauth_service import (
    is_instagram_token_expired,
    mark_instagram_account_status,
    mark_instagram_account_expired,
    mark_instagram_account_error,
    mark_instagram_account_revoked,
    refresh_instagram_access_token,
    get_valid_instagram_access_token
)
from services.youtube_oauth_service import get_user_social_accounts


class TestInstagramTokenLifecycle(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        init_db()

        self.user1_id = 1
        self.user2_id = 2

        # Ensure user1 and user2 exist in user_master
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_master (user_id, user_name, password, is_active)
            VALUES
                (1, 'admin', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE),
                (2, 'user2_test', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE)
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE;
        """)
        # Clean Instagram accounts and states
        cur.execute("DELETE FROM oauth_states WHERE platform IN ('INSTAGRAM', 'META');")
        cur.execute("DELETE FROM social_accounts WHERE platform = 'INSTAGRAM';")
        conn.commit()
        cur.close()
        conn.close()

        self.token_user1 = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")

        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Config mock
        Config.INSTAGRAM_CLIENT_ID = "mock_meta_app_id"
        Config.INSTAGRAM_CLIENT_SECRET = "mock_meta_app_secret"
        Config.META_GRAPH_API_VERSION = "v21.0"
        Config.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"

    def _insert_test_instagram_account(self, user_id=1, platform_id="17841400000000001", token="test_token_val", expires_at=None, status="ACTIVE", raw_encrypted=None):
        conn = get_connection()
        cur = conn.cursor()
        enc = raw_encrypted if raw_encrypted is not None else encrypt_token(token)
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                profile_image_url, encrypted_access_token, token_expires_at, connection_status,
                raw_scopes, metadata
            )
            VALUES (
                %s, 'INSTAGRAM', %s, 'Test IG Account', 'test_ig_user',
                'https://example.com/pic.jpg', %s, %s, %s,
                'instagram_basic,instagram_content_publish', '{"facebook_page_id": "p123"}'::jsonb
            )
            RETURNING id;
        """, (user_id, platform_id, enc, expires_at, status))
        account_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return account_id

    def test_01_valid_non_expired_token_retrieval(self):
        """Test retrieving valid non-expired token returns decrypted token successfully."""
        future_exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=45)
        raw_secret = "EAA_super_secret_meta_token_xyz"
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=raw_secret, expires_at=future_exp, status="ACTIVE")

        success, token, err = get_valid_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertTrue(success)
        self.assertEqual(token, raw_secret)
        self.assertIsNone(err)

    def test_02_encrypted_token_decrypted_only_internally(self):
        """Test that token stored in the database is strictly encrypted ciphertext."""
        raw_secret = "EAA_plain_token_never_plain_in_db"
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=raw_secret)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT encrypted_access_token FROM social_accounts WHERE id = %s;", (acc_id,))
        enc_token = cur.fetchone()[0]
        cur.close()
        conn.close()

        self.assertIsNotNone(enc_token)
        self.assertNotEqual(enc_token, raw_secret)
        self.assertTrue(enc_token.startswith("gAAAAA"))
        self.assertEqual(decrypt_token(enc_token), raw_secret)

    def test_03_missing_token_handled_safely(self):
        """Test account with missing encrypted token is marked ERROR and handled safely."""
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, raw_encrypted="")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE social_accounts SET encrypted_access_token = NULL WHERE id = %s;", (acc_id,))
        conn.commit()
        cur.close()
        conn.close()

        success, token, err = get_valid_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(token)
        self.assertIn("No access token found", err)

        # Check DB marked ERROR
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status, "ERROR")

    def test_04_malformed_encrypted_token_handled_safely(self):
        """Test account with corrupt encrypted token is caught safely and marked ERROR."""
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, raw_encrypted="gAAAAABcorrupt_cipher_string_123456789")

        success, token, err = get_valid_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(token)
        self.assertIn("Corrupt or malformed", err)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status, "ERROR")

    def test_05_expiry_detection_helper(self):
        """Test is_instagram_token_expired helper function with various date scenarios."""
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # None is treated as expired / requiring check
        self.assertTrue(is_instagram_token_expired(None))

        # Past date is expired
        past_exp = now_utc - datetime.timedelta(days=1)
        self.assertTrue(is_instagram_token_expired(past_exp))

        # Within 5 min threshold is considered expired
        near_exp = now_utc + datetime.timedelta(minutes=3)
        self.assertTrue(is_instagram_token_expired(near_exp, threshold_minutes=5))

        # Far in future is NOT expired
        future_exp = now_utc + datetime.timedelta(days=30)
        self.assertFalse(is_instagram_token_expired(future_exp, threshold_minutes=5))

    @patch("requests.get")
    def test_06_successful_token_renewal_updates_db_and_encrypts(self, mock_get):
        """Test refresh_instagram_access_token calls Meta Graph API and updates encrypted token and expiry."""
        old_token = "EAA_old_long_lived_token_123"
        new_token = "EAA_new_renewed_token_456"
        past_exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)

        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=old_token, expires_at=past_exp, status="ACTIVE")

        # Mock Meta Graph API response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 5184000  # 60 days
        }
        mock_get.return_value = mock_resp

        success, returned_token, err = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertTrue(success)
        self.assertEqual(returned_token, new_token)
        self.assertIsNone(err)

        # Verify DB updated
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT encrypted_access_token, token_expires_at, connection_status
            FROM social_accounts WHERE id = %s;
        """, (acc_id,))
        enc_token, new_exp, status = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(status, "ACTIVE")
        self.assertEqual(decrypt_token(enc_token), new_token)
        self.assertGreater(new_exp, datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=50))

    @patch("requests.get")
    def test_07_auto_refresh_in_get_valid_token(self, mock_get):
        """Test get_valid_instagram_access_token automatically triggers renewal when token is expired."""
        old_token = "EAA_old_token_expiring"
        new_token = "EAA_refreshed_auto_token"
        past_exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=old_token, expires_at=past_exp, status="ACTIVE")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": new_token,
            "expires_in": 5184000
        }
        mock_get.return_value = mock_resp

        success, valid_token, err = get_valid_instagram_access_token(account_id=acc_id, user_id=self.user1_id, auto_refresh=True)
        self.assertTrue(success)
        self.assertEqual(valid_token, new_token)
        self.assertIsNone(err)

    @patch("requests.get")
    def test_08_renewal_failure_permanent_oauth_error_marks_expired(self, mock_get):
        """Test Meta OAuth error code 190 marks account EXPIRED in database."""
        old_token = "EAA_expired_token_unrecoverable"
        past_exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)

        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=old_token, expires_at=past_exp, status="ACTIVE")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "Error validating access token: Session has expired on ...",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463
            }
        }
        mock_get.return_value = mock_resp

        success, valid_token, err = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(valid_token)
        self.assertIn("expired or been revoked", err)

        # Check DB marked EXPIRED
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status, "EXPIRED")

    @patch("requests.get")
    def test_09_renewal_failure_due_to_revocation_marks_expired(self, mock_get):
        """Test user revocation error from Meta marks account EXPIRED."""
        old_token = "EAA_revoked_token"
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=old_token, status="ACTIVE")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {
                "message": "User has revoked access to the application",
                "type": "OAuthException",
                "code": 190
            }
        }
        mock_get.return_value = mock_resp

        success, valid_token, err = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(valid_token)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status, "EXPIRED")

    @patch("requests.get")
    def test_10_transient_meta_network_or_5xx_error_preserves_active_status(self, mock_get):
        """Test temporary network failure or 5xx server error does NOT mark account expired in DB."""
        old_token = "EAA_active_token_network_glitch"
        future_exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token=old_token, expires_at=future_exp, status="ACTIVE")

        # 1. Test requests.Timeout
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout to Meta")
        success1, token1, err1 = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success1)
        self.assertIn("Temporary failure", err1)

        # Status in DB must remain ACTIVE
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status1 = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status1, "ACTIVE")

        # 2. Test HTTP 503 Service Unavailable
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_get.side_effect = None
        mock_get.return_value = mock_503

        success2, token2, err2 = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success2)
        self.assertIn("Temporary Meta server error", err2)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        status2 = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(status2, "ACTIVE")

    def test_11_account_ownership_protection(self):
        """Test User 1 cannot access or refresh User 2's Instagram account token."""
        acc_user2_id = self._insert_test_instagram_account(user_id=self.user2_id, token="user2_secret_token")

        # User 1 attempts to retrieve User 2's token
        success, token, err = get_valid_instagram_access_token(account_id=acc_user2_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(token)
        self.assertIn("access denied", err.lower())

        # User 1 attempts to refresh User 2's token
        ref_success, ref_token, ref_err = refresh_instagram_access_token(account_id=acc_user2_id, user_id=self.user1_id)
        self.assertFalse(ref_success)
        self.assertIsNone(ref_token)
        self.assertIn("access denied", ref_err.lower())

    def test_12_status_helpers_and_validation(self):
        """Test status updater helpers: mark_instagram_account_expired, mark_instagram_account_error, mark_instagram_account_revoked."""
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token="token_for_status_tests")

        # Expired
        mark_instagram_account_expired(account_id=acc_id, user_id=self.user1_id)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        self.assertEqual(cur.fetchone()[0], "EXPIRED")

        # Error with message
        mark_instagram_account_error(account_id=acc_id, user_id=self.user1_id, error_message="Meta API Error 100")
        cur.execute("SELECT connection_status, metadata FROM social_accounts WHERE id = %s;", (acc_id,))
        st, meta = cur.fetchone()
        self.assertEqual(st, "ERROR")
        self.assertEqual(meta.get("last_error"), "Meta API Error 100")

        # Revoked
        mark_instagram_account_revoked(account_id=acc_id, user_id=self.user1_id)
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        self.assertEqual(cur.fetchone()[0], "REVOKED")

        cur.close()
        conn.close()

        # Invalid status raises ValueError
        with self.assertRaises(ValueError):
            mark_instagram_account_status(account_id=acc_id, user_id=self.user1_id, status="INVALID_STATUS_XYZ")

    def test_13_disconnected_account_rejection(self):
        """Test disconnected accounts cannot be retrieved or refreshed."""
        acc_id = self._insert_test_instagram_account(user_id=self.user1_id, token="token_disconnected", status="DISCONNECTED")

        success, token, err = get_valid_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(success)
        self.assertIsNone(token)
        self.assertIn("disconnected", err.lower())

        ref_success, ref_token, ref_err = refresh_instagram_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertFalse(ref_success)
        self.assertIsNone(ref_token)
        self.assertIn("disconnected", ref_err.lower())

    def test_14_accounts_api_never_exposes_tokens_and_includes_reconnect_required(self):
        """Test GET /api/social-media/accounts never exposes tokens and sets reconnect_required properly."""
        # 1. Active account
        future_exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        acc1 = self._insert_test_instagram_account(user_id=self.user1_id, platform_id="ig_act_1", token="tok1", expires_at=future_exp, status="ACTIVE")

        # 2. Expired account
        past_exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
        acc2 = self._insert_test_instagram_account(user_id=self.user1_id, platform_id="ig_exp_2", token="tok2", expires_at=past_exp, status="EXPIRED")

        res = self.app.get("/api/social-media/accounts", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertTrue(data["success"])
        accounts = data["accounts"]

        # Ensure tokens are never present
        for acc in accounts:
            self.assertNotIn("encrypted_access_token", acc)
            self.assertNotIn("encrypted_refresh_token", acc)
            self.assertNotIn("access_token", acc)
            self.assertNotIn("refresh_token", acc)
            self.assertNotIn("token", acc)

        ig1 = next(a for a in accounts if a["id"] == acc1)
        self.assertEqual(ig1["connection_status"], "ACTIVE")
        self.assertFalse(ig1["reconnect_required"])

        ig2 = next(a for a in accounts if a["id"] == acc2)
        self.assertEqual(ig2["connection_status"], "EXPIRED")
        self.assertTrue(ig2["reconnect_required"])


if __name__ == "__main__":
    unittest.main()
