import os
import sys
import json
import datetime
import unittest
import hashlib
import urllib.parse
from unittest.mock import patch, MagicMock

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
    get_instagram_authorization_url,
    handle_instagram_oauth_callback,
    get_valid_instagram_access_token
)
from services.youtube_oauth_service import (
    get_user_social_accounts,
    disconnect_social_account
)


class TestInstagramOAuth(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        init_db()

        self.user1_id = 1
        self.user2_id = 2

        # Ensure user1 (admin) and user2 exist in user_master
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_master (user_id, user_name, password, is_active)
            VALUES
                (1, 'admin', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE),
                (2, 'user2_test', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE)
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE, user_name = EXCLUDED.user_name;
        """)
        # Clean test social accounts and states for pristine test isolation
        cur.execute("DELETE FROM oauth_states WHERE platform IN ('INSTAGRAM', 'META');")
        cur.execute("DELETE FROM social_accounts WHERE platform = 'INSTAGRAM';")
        conn.commit()
        cur.close()
        conn.close()

        self.token_user1 = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")

        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Mock Instagram / Meta Config for tests
        Config.FRONTEND_URL = "http://localhost:5173"
        Config.INSTAGRAM_CLIENT_ID = "mock_meta_app_id_12345"
        Config.INSTAGRAM_CLIENT_SECRET = "mock_meta_app_secret_67890"
        Config.INSTAGRAM_REDIRECT_URI = "http://localhost:5000/api/social-media/oauth/instagram/callback"
        Config.META_GRAPH_API_VERSION = "v21.0"
        Config.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
        Config.INSTAGRAM_SCOPES = ["instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement", "business_management"]

    def test_01_connect_instagram_requires_jwt(self):
        """Test that GET /api/social-media/connect/instagram requires valid JWT authentication."""
        # 1. Without JWT header
        res1 = self.app.get("/api/social-media/connect/instagram")
        self.assertEqual(res1.status_code, 401)

        # 2. With invalid JWT
        res2 = self.app.get("/api/social-media/connect/instagram", headers={"Authorization": "Bearer invalid_token_xyz"})
        self.assertEqual(res2.status_code, 401)

        # 3. With valid JWT
        res3 = self.app.get("/api/social-media/connect/instagram", headers=self.headers_user1)
        self.assertEqual(res3.status_code, 200)

    def test_02_authorization_url_generation_and_state_hashing(self):
        """Test authorization URL structure, query parameters, and SHA-256 state hashing in DB."""
        res = self.app.get("/api/social-media/connect/instagram", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertTrue(data["success"])
        auth_url = data["authorization_url"]

        # Validate URL parameters
        self.assertIn("facebook.com", auth_url)
        self.assertIn("v21.0/dialog/oauth", auth_url)
        self.assertIn(f"client_id={Config.INSTAGRAM_CLIENT_ID}", auth_url)
        self.assertIn("response_type=code", auth_url)
        self.assertIn("instagram_basic", auth_url)
        self.assertIn("instagram_content_publish", auth_url)
        self.assertIn("pages_show_list", auth_url)

        # Verify state is stored as SHA-256 hash in oauth_states table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, platform, state_hash, consumed_at, expires_at, redirect_uri
            FROM oauth_states
            WHERE user_id = %s AND platform = 'INSTAGRAM'
            ORDER BY id DESC LIMIT 1;
        """, (self.user1_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(row)
        state_id, platform, state_hash, consumed_at, expires_at, redirect_uri = row
        self.assertEqual(platform, "INSTAGRAM")
        self.assertEqual(len(state_hash), 64)  # Valid SHA-256 hex string length
        self.assertIsNone(consumed_at)  # Not consumed yet
        self.assertEqual(redirect_uri, Config.INSTAGRAM_REDIRECT_URI)

    def test_03_callback_rejects_missing_or_invalid_state(self):
        """Test callback endpoint safely rejects missing, unhashed, or unrecognized state values."""
        # 1. Missing state completely
        res1 = self.app.get("/api/social-media/oauth/instagram/callback?code=mock_code")
        self.assertEqual(res1.status_code, 302)
        self.assertIn("code=invalid_state", res1.location)

        # 2. Non-existent random state
        res2 = self.app.get("/api/social-media/oauth/instagram/callback?state=non_existent_state_123&code=mock_code")
        self.assertEqual(res2.status_code, 302)
        self.assertIn("code=invalid_state", res2.location)

    def test_04_callback_rejects_expired_state(self):
        """Test callback rejects state tokens that have exceeded their expiration TTL."""
        # Insert an expired state directly into oauth_states
        raw_state = "expired_test_state_1234567890123456"
        state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO oauth_states (state_hash, user_id, platform, redirect_uri, expires_at)
            VALUES (%s, %s, 'INSTAGRAM', %s, %s);
        """, (state_hash, self.user1_id, Config.INSTAGRAM_REDIRECT_URI, past_time))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.get(f"/api/social-media/oauth/instagram/callback?state={raw_state}&code=mock_code")
        self.assertEqual(res.status_code, 302)
        self.assertIn("code=state_expired", res.location)

    @patch("requests.get")
    def test_05_callback_single_use_state_rejects_replay(self, mock_get):
        """Test that single-use states are marked consumed and cannot be replayed/reused."""
        # Mock Meta token and profile responses
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            "access_token": "EAA_mock_meta_access_token_123",
            "expires_in": 5184000
        }

        mock_accounts_resp = MagicMock()
        mock_accounts_resp.status_code = 200
        mock_accounts_resp.json.return_value = {
            "data": [{
                "id": "1001_page_id",
                "name": "My Business Page",
                "instagram_business_account": {
                    "id": "17841400000000001",
                    "username": "my_creator_brand",
                    "name": "My Creator Brand",
                    "profile_picture_url": "https://graph.instagram.com/mock_profile.jpg"
                }
            }]
        }

        mock_long_resp = MagicMock()
        mock_long_resp.status_code = 200
        mock_long_resp.json.return_value = {
            "access_token": "EAA_mock_meta_access_token_long_lived_123",
            "expires_in": 5184000
        }

        mock_get.side_effect = [mock_token_resp, mock_long_resp, mock_accounts_resp]

        # 1. Generate active state
        auth_data = get_instagram_authorization_url(user_id=self.user1_id)
        raw_state = auth_data["state"]

        # 2. First callback succeeds
        res1 = self.app.get(f"/api/social-media/oauth/instagram/callback?state={raw_state}&code=mock_code_123")
        self.assertEqual(res1.status_code, 302)
        self.assertIn("status=success", res1.location)
        self.assertIn("platform=instagram", res1.location)

        # 3. Second callback with same state is rejected as state_already_used
        res2 = self.app.get(f"/api/social-media/oauth/instagram/callback?state={raw_state}&code=mock_code_123")
        self.assertEqual(res2.status_code, 302)
        self.assertIn("code=state_already_used", res2.location)

    def test_06_callback_handles_user_denial(self):
        """Test callback handles user denial / access cancellation from Meta."""
        auth_data = get_instagram_authorization_url(user_id=self.user1_id)
        raw_state = auth_data["state"]

        res = self.app.get(f"/api/social-media/oauth/instagram/callback?state={raw_state}&error=access_denied&error_reason=user_denied")
        self.assertEqual(res.status_code, 302)
        self.assertIn("code=oauth_denied", res.location)

    @patch("requests.get")
    def test_07_successful_connection_encrypts_tokens_and_stores_in_db(self, mock_get):
        """Test complete successful Instagram OAuth flow, token encryption, and database storage."""
        # 1. Mock Meta Graph API responses
        # First call: short-lived code exchange
        mock_short_token = MagicMock()
        mock_short_token.status_code = 200
        mock_short_token.json.return_value = {
            "access_token": "EAA_short_token_123",
            "expires_in": 7200
        }

        # Second call: long-lived token exchange
        mock_long_token = MagicMock()
        mock_long_token.status_code = 200
        mock_long_token.json.return_value = {
            "access_token": "EAA_long_token_60_days_456",
            "expires_in": 5184000
        }

        # Third call: /me/accounts discovery
        mock_accounts = MagicMock()
        mock_accounts.status_code = 200
        mock_accounts.json.return_value = {
            "data": [{
                "id": "page_99999",
                "name": "LifeOS Test Page",
                "instagram_business_account": {
                    "id": "17841400000000999",
                    "username": "lifeos_official",
                    "name": "LifeOS Official Creator",
                    "profile_picture_url": "https://scontent.cdninstagram.com/v/mock_avatar.jpg"
                }
            }]
        }

        mock_get.side_effect = [mock_short_token, mock_long_token, mock_accounts]

        # 2. Initiate connection
        auth_data = get_instagram_authorization_url(user_id=self.user1_id)
        raw_state = auth_data["state"]

        # 3. Trigger callback
        res = self.app.get(f"/api/social-media/oauth/instagram/callback?state={raw_state}&code=meta_code_999")
        self.assertEqual(res.status_code, 302)
        self.assertIn("status=success", res.location)
        self.assertIn("platform=instagram", res.location)
        self.assertIn("lifeos_official", res.location)

        # 4. Verify record in social_accounts table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, platform, platform_account_id, account_name, account_username,
                   profile_image_url, encrypted_access_token, connection_status, metadata
            FROM social_accounts
            WHERE user_id = %s AND platform = 'INSTAGRAM';
        """, (self.user1_id,))
        acc_row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(acc_row)
        aid, platform, paid, aname, auser, pimg, enc_token, status, meta = acc_row
        self.assertEqual(platform, "INSTAGRAM")
        self.assertEqual(paid, "17841400000000999")
        self.assertEqual(aname, "LifeOS Official Creator")
        self.assertEqual(auser, "lifeos_official")
        self.assertEqual(status, "ACTIVE")

        # Verify token is encrypted and decryptable
        self.assertNotEqual(enc_token, "EAA_long_token_60_days_456")
        decrypted = decrypt_token(enc_token)
        self.assertEqual(decrypted, "EAA_long_token_60_days_456")

        # Verify metadata contains Facebook page details
        self.assertEqual(meta.get("facebook_page_id"), "page_99999")
        self.assertEqual(meta.get("facebook_page_name"), "LifeOS Test Page")

        # 5. Verify get_valid_instagram_access_token retrieves decrypted token
        success, valid_token, err = get_valid_instagram_access_token(account_id=aid, user_id=self.user1_id)
        self.assertTrue(success)
        self.assertEqual(valid_token, "EAA_long_token_60_days_456")
        self.assertIsNone(err)

    @patch("requests.get")
    def test_08_upsert_prevents_duplicate_accounts(self, mock_get):
        """Test reconnecting the same Instagram account updates the existing record without creating duplicate entries."""
        mock_token = MagicMock()
        mock_token.status_code = 200
        mock_token.json.return_value = {
            "access_token": "EAA_token_v1",
            "expires_in": 7200
        }

        mock_accounts = MagicMock()
        mock_accounts.status_code = 200
        mock_accounts.json.return_value = {
            "data": [{
                "id": "page_111",
                "name": "Page Name V1",
                "instagram_business_account": {
                    "id": "17841400000000111",
                    "username": "creator_v1",
                    "name": "Creator Title V1",
                    "profile_picture_url": "https://instagram.com/pic1.jpg"
                }
            }]
        }

        # First connection
        mock_get.side_effect = [mock_token, MagicMock(status_code=400), mock_accounts]
        auth_data1 = get_instagram_authorization_url(user_id=self.user1_id)
        res1 = self.app.get(f"/api/social-media/oauth/instagram/callback?state={auth_data1['state']}&code=code_1")
        self.assertEqual(res1.status_code, 302)

        # Second connection for same IG account with updated title
        mock_token2 = MagicMock()
        mock_token2.status_code = 200
        mock_token2.json.return_value = {
            "access_token": "EAA_token_v2_updated",
            "expires_in": 5184000
        }

        mock_accounts2 = MagicMock()
        mock_accounts2.status_code = 200
        mock_accounts2.json.return_value = {
            "data": [{
                "id": "page_111",
                "name": "Page Name V2",
                "instagram_business_account": {
                    "id": "17841400000000111",
                    "username": "creator_v1",
                    "name": "Creator Title V2 (Updated)",
                    "profile_picture_url": "https://instagram.com/pic2.jpg"
                }
            }]
        }

        mock_get.side_effect = [mock_token2, MagicMock(status_code=400), mock_accounts2]
        auth_data2 = get_instagram_authorization_url(user_id=self.user1_id)
        res2 = self.app.get(f"/api/social-media/oauth/instagram/callback?state={auth_data2['state']}&code=code_2")
        self.assertEqual(res2.status_code, 302)

        # Verify only 1 record exists in social_accounts
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM social_accounts WHERE user_id = %s AND platform = 'INSTAGRAM';", (self.user1_id,))
        count = cur.fetchone()[0]

        cur.execute("SELECT account_name, encrypted_access_token FROM social_accounts WHERE user_id = %s AND platform = 'INSTAGRAM';", (self.user1_id,))
        aname, enc_token = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(count, 1)
        self.assertEqual(aname, "Creator Title V2 (Updated)")
        self.assertEqual(decrypt_token(enc_token), "EAA_token_v2_updated")

    @patch("requests.get")
    def test_09_callback_handles_no_linked_instagram_account(self, mock_get):
        """Test callback returns friendly error code if Facebook page has no linked Instagram professional account."""
        mock_token = MagicMock()
        mock_token.status_code = 200
        mock_token.json.return_value = {"access_token": "EAA_test_token_no_ig", "expires_in": 7200}

        # Page with NO instagram_business_account
        mock_accounts = MagicMock()
        mock_accounts.status_code = 200
        mock_accounts.json.return_value = {
            "data": [{
                "id": "page_standalone",
                "name": "Standalone Facebook Page"
            }]
        }

        mock_me = MagicMock()
        mock_me.status_code = 200
        mock_me.json.return_value = {}

        mock_get.side_effect = [mock_token, MagicMock(status_code=400), mock_accounts, mock_me]

        auth_data = get_instagram_authorization_url(user_id=self.user1_id)
        res = self.app.get(f"/api/social-media/oauth/instagram/callback?state={auth_data['state']}&code=code_no_ig")
        self.assertEqual(res.status_code, 302)
        self.assertIn("code=instagram_account_not_found", res.location)

    @patch("requests.get")
    def test_10_accounts_endpoint_lists_both_youtube_and_instagram(self, mock_get):
        """Test GET /api/social-media/accounts returns both YouTube and Instagram connected accounts."""
        # Connect an Instagram account
        mock_token = MagicMock()
        mock_token.status_code = 200
        mock_token.json.return_value = {"access_token": "EAA_token_list_test", "expires_in": 7200}
        mock_accounts = MagicMock()
        mock_accounts.status_code = 200
        mock_accounts.json.return_value = {
            "data": [{
                "id": "page_333",
                "name": "LifeOS Page",
                "instagram_business_account": {
                    "id": "17841400000000333",
                    "username": "lifeos_ig_test",
                    "name": "LifeOS IG Test",
                    "profile_picture_url": "https://instagram.com/pic3.jpg"
                }
            }]
        }
        mock_get.side_effect = [mock_token, MagicMock(status_code=400), mock_accounts]

        auth_data = get_instagram_authorization_url(user_id=self.user1_id)
        self.app.get(f"/api/social-media/oauth/instagram/callback?state={auth_data['state']}&code=code_list")

        # Also insert a YouTube account for user1
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                encrypted_access_token, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_list_test_yt', 'My YouTube Channel', 'yt_username', %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO NOTHING;
        """, (self.user1_id, encrypt_token("mock_yt_token")))
        conn.commit()
        cur.close()
        conn.close()

        # Query /api/social-media/accounts
        res = self.app.get("/api/social-media/accounts", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertTrue(data["success"])
        accounts = data["accounts"]

        platforms = [a["platform"] for a in accounts]
        self.assertIn("YOUTUBE", platforms)
        self.assertIn("INSTAGRAM", platforms)

        ig_acc = next(a for a in accounts if a["platform"] == "INSTAGRAM")
        self.assertEqual(ig_acc["account_username"], "lifeos_ig_test")
        self.assertEqual(ig_acc["connection_status"], "ACTIVE")

    def test_11_disconnect_instagram_account_scrubs_tokens(self):
        """Test DELETE /api/social-media/accounts/<id> safely disconnects and scrubs Instagram token."""
        # Insert active Instagram account
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                encrypted_access_token, connection_status
            )
            VALUES (%s, 'INSTAGRAM', '17841400000000555', 'IG To Disconnect', 'disconnect_me', %s, 'ACTIVE')
            RETURNING id;
        """, (self.user1_id, encrypt_token("token_to_scrub")))
        account_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # Disconnect account via API endpoint
        res = self.app.delete(f"/api/social-media/accounts/{account_id}", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        # Verify token is scrubbed and status is DISCONNECTED in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status, encrypted_access_token FROM social_accounts WHERE id = %s;", (account_id,))
        status, enc_token = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(status, "DISCONNECTED")
        self.assertIsNone(enc_token)


if __name__ == "__main__":
    unittest.main()
