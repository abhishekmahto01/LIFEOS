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
from services.youtube_oauth_service import (
    get_youtube_authorization_url,
    handle_youtube_oauth_callback,
    get_user_social_accounts,
    disconnect_social_account,
    get_valid_youtube_access_token
)

class TestYouTubeOAuth(unittest.TestCase):

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
        conn.commit()
        cur.close()
        conn.close()

        self.token_user1 = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")

        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Mock Google Config for tests
        Config.FRONTEND_URL = "http://localhost:5173"
        Config.GOOGLE_CLIENT_ID = "mock_client_id.apps.googleusercontent.com"
        Config.GOOGLE_CLIENT_SECRET = "mock_client_secret_xyz"
        Config.GOOGLE_REDIRECT_URI = "http://localhost:5000/api/social-media/oauth/youtube/callback"

    def test_01_jwt_required_on_protected_endpoints(self):
        """Test that connect, accounts list, and disconnect require valid JWT token."""
        # 1. Connect without JWT
        res1 = self.app.get("/api/social-media/connect/youtube")
        self.assertEqual(res1.status_code, 401)

        # 2. Accounts list without JWT
        res2 = self.app.get("/api/social-media/accounts")
        self.assertEqual(res2.status_code, 401)

        # 3. Disconnect without JWT
        res3 = self.app.delete("/api/social-media/accounts/1")
        self.assertEqual(res3.status_code, 401)

    def test_02_connect_youtube_generates_valid_auth_url_and_state(self):
        """Test authorization URL contains correct scopes, offline access, and stores hashed state."""
        res = self.app.get("/api/social-media/connect/youtube", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertTrue(data["success"])
        auth_url = data["authorization_url"]

        self.assertIn("accounts.google.com", auth_url)
        self.assertIn(Config.GOOGLE_CLIENT_ID, auth_url)
        self.assertIn("youtube.readonly", auth_url)
        self.assertNotIn("youtube.upload", auth_url)  # Stage 5 strictly read-only
        self.assertIn("access_type=offline", auth_url)
        self.assertIn("prompt=consent", auth_url)

        # Verify state is stored hashed in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, platform, consumed_at, expires_at FROM oauth_states WHERE user_id = %s ORDER BY id DESC LIMIT 1;", (self.user1_id,))
        state_row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(state_row)
        self.assertEqual(state_row[1], "YOUTUBE")
        self.assertIsNone(state_row[2])  # Not consumed yet

    @patch("requests.post")
    @patch("requests.get")
    def test_03_callback_without_jwt_using_valid_state(self, mock_get, mock_post):
        """Test OAuth callback does not require JWT, exchanges code, fetches channel, and encrypts tokens."""
        # 1. Start connect to generate valid state
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]

        # 2. Mock Google token exchange response
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.headers = {"content-type": "application/json"}
        mock_token_resp.json.return_value = {
            "access_token": "ya29.mock_access_token_12345",
            "refresh_token": "1//mock_refresh_token_67890",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/youtube.readonly"
        }
        mock_post.return_value = mock_token_resp

        # 3. Mock YouTube channels.list response
        mock_yt_resp = MagicMock()
        mock_yt_resp.status_code = 200
        mock_yt_resp.json.return_value = {
            "items": [{
                "id": "UC_mock_channel_id_123",
                "snippet": {
                    "title": "My Test YouTube Channel",
                    "customUrl": "mytestchannel",
                    "thumbnails": {"default": {"url": "https://yt3.ggpht.com/mock_thumb.jpg"}}
                }
            }]
        }
        mock_get.return_value = mock_yt_resp

        # 4. Call OAuth callback endpoint without JWT
        callback_url = f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=mock_auth_code_123"
        res = self.app.get(callback_url)

        self.assertEqual(res.status_code, 302)
        redirect_loc = res.headers["Location"]
        self.assertTrue(redirect_loc.startswith(Config.FRONTEND_URL))
        self.assertIn("status=success", redirect_loc)
        self.assertIn("platform=youtube", redirect_loc)

        # 5. Verify database storage & encryption
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, platform, platform_account_id, account_name, encrypted_access_token, encrypted_refresh_token, connection_status
            FROM social_accounts
            WHERE user_id = %s AND platform_account_id = 'UC_mock_channel_id_123';
        """, (self.user1_id,))
        acc = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(acc)
        aid, plat, paid, aname, enc_access, enc_refresh, status = acc
        self.assertEqual(plat, "YOUTUBE")
        self.assertEqual(aname, "My Test YouTube Channel")
        self.assertEqual(status, "ACTIVE")
        self.assertNotEqual(enc_access, "ya29.mock_access_token_12345")
        self.assertEqual(decrypt_token(enc_access), "ya29.mock_access_token_12345")
        self.assertEqual(decrypt_token(enc_refresh), "1//mock_refresh_token_67890")

    def test_04_missing_expired_and_reused_oauth_state(self):
        """Test that missing, expired, or already-consumed states redirect safely to fixed error codes."""
        # 1. Missing state
        res1 = self.app.get("/api/social-media/oauth/youtube/callback?code=mock_code")
        self.assertEqual(res1.status_code, 302)
        self.assertIn("code=invalid_state", res1.headers["Location"])

        # 2. Expired state
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]
        state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE oauth_states SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 hour' WHERE state_hash = %s;", (state_hash,))
        conn.commit()
        cur.close()
        conn.close()

        res2 = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=mock_code")
        self.assertEqual(res2.status_code, 302)
        self.assertIn("code=state_expired", res2.headers["Location"])

        # 3. Already consumed state
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE oauth_states SET expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour', consumed_at = CURRENT_TIMESTAMP WHERE state_hash = %s;", (state_hash,))
        conn.commit()
        cur.close()
        conn.close()

        res3 = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=mock_code")
        self.assertEqual(res3.status_code, 302)
        self.assertIn("code=state_already_used", res3.headers["Location"])

    def test_05_oauth_denial_handling(self):
        """Test that user cancellation or error from Google redirects with safe oauth_denied code."""
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]

        res = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&error=access_denied")
        self.assertEqual(res.status_code, 302)
        self.assertIn("status=error", res.headers["Location"])
        self.assertIn("code=oauth_denied", res.headers["Location"])

    def test_06_trusted_frontend_url_and_redirect_uri_mismatch(self):
        """Test callback redirects only to Config.FRONTEND_URL and detects redirect URI mismatch."""
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]
        state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()

        # Alter stored redirect URI in DB to simulate mismatch
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE oauth_states SET redirect_uri = 'http://attacker-site.com/callback' WHERE state_hash = %s;", (state_hash,))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=mock_code")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].startswith(Config.FRONTEND_URL))
        self.assertIn("code=redirect_uri_mismatch", res.headers["Location"])

    @patch("requests.post")
    def test_07_missing_required_scope_and_missing_access_token(self, mock_post):
        """Test rejection when required scope is not granted or access token is missing."""
        # 1. Missing required YouTube scope
        auth_res1 = get_youtube_authorization_url(user_id=self.user1_id)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "mock_token", "scope": "email profile"}
        )
        res1 = self.app.get(f"/api/social-media/oauth/youtube/callback?state={auth_res1['state']}&code=code1")
        self.assertEqual(res1.status_code, 302)
        self.assertIn("code=scope_not_granted", res1.headers["Location"])

        # 2. Missing access token from Google token exchange
        auth_res2 = get_youtube_authorization_url(user_id=self.user1_id)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"expires_in": 3600}
        )
        res2 = self.app.get(f"/api/social-media/oauth/youtube/callback?state={auth_res2['state']}&code=code2")
        self.assertEqual(res2.status_code, 302)
        self.assertIn("code=token_exchange_failed", res2.headers["Location"])

    @patch("requests.post")
    @patch("requests.get")
    def test_08_channel_with_no_result_and_missing_channel_id(self, mock_get, mock_post):
        """Test account with zero YouTube channels returns safe channel_not_found code."""
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]

        mock_token_resp = MagicMock(status_code=200)
        mock_token_resp.json.return_value = {
            "access_token": "ya29.valid",
            "scope": "https://www.googleapis.com/auth/youtube.readonly",
            "expires_in": 3600
        }
        mock_post.return_value = mock_token_resp

        # Empty items from channels.list
        mock_yt_resp = MagicMock(status_code=200)
        mock_yt_resp.json.return_value = {"items": []}
        mock_get.return_value = mock_yt_resp

        res = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=code_123")
        self.assertEqual(res.status_code, 302)
        self.assertIn("status=error", res.headers["Location"])
        self.assertIn("code=channel_not_found", res.headers["Location"])

    @patch("requests.post")
    @patch("requests.get")
    def test_09_missing_refresh_token_preservation_and_upsert(self, mock_get, mock_post):
        """Test reconnecting channel preserves existing refresh token when Google omits it."""
        conn = get_connection()
        cur = conn.cursor()
        original_refresh = "1//original_secret_refresh_token_123"
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_preserve_test_channel', 'Preserve Channel', %s, %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token
            RETURNING id;
        """, (self.user1_id, encrypt_token("old_access"), encrypt_token(original_refresh)))
        existing_acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # Reconnect without refresh token in response
        auth_res = get_youtube_authorization_url(user_id=self.user1_id)
        raw_state = auth_res["state"]

        mock_token_resp = MagicMock(status_code=200)
        mock_token_resp.json.return_value = {
            "access_token": "ya29.new_reconnected_access_token",
            "scope": "https://www.googleapis.com/auth/youtube.readonly",
            "expires_in": 3600
        }
        mock_post.return_value = mock_token_resp

        mock_yt_resp = MagicMock(status_code=200)
        mock_yt_resp.json.return_value = {
            "items": [{
                "id": "UC_preserve_test_channel",
                "snippet": {"title": "Preserve Channel Updated", "customUrl": "preserve", "thumbnails": {}}
            }]
        }
        mock_get.return_value = mock_yt_resp

        res = self.app.get(f"/api/social-media/oauth/youtube/callback?state={raw_state}&code=code_123")
        self.assertEqual(res.status_code, 302)

        # Verify refresh token was preserved
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, encrypted_refresh_token, account_name FROM social_accounts WHERE id = %s;", (existing_acc_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertEqual(row[0], existing_acc_id)
        self.assertEqual(row[2], "Preserve Channel Updated")
        self.assertEqual(decrypt_token(row[1]), original_refresh)

    def test_10_accounts_api_never_exposes_tokens(self):
        """Test that GET /api/social-media/accounts returns safe fields and zero tokens."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_safe_test_channel', 'Safe Channel', %s, %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO NOTHING
            RETURNING id;
        """, (self.user1_id, encrypt_token("secret_access_token"), encrypt_token("secret_refresh_token")))
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.get("/api/social-media/accounts", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertTrue(data["success"])
        accounts = data["accounts"]
        self.assertGreater(len(accounts), 0)

        res_str = json.dumps(data)
        self.assertNotIn("secret_access_token", res_str)
        self.assertNotIn("secret_refresh_token", res_str)
        self.assertNotIn("encrypted_access_token", res_str)
        self.assertNotIn("encrypted_refresh_token", res_str)
        self.assertNotIn("gAAAAA", res_str)

    def test_11_cross_user_protection(self):
        """Test User 2 cannot view or disconnect User 1's social accounts."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_user1_private_channel', 'User 1 Channel', %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET account_name = EXCLUDED.account_name
            RETURNING id;
        """, (self.user1_id, encrypt_token("user1_token")))
        user1_acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # User 2 lists accounts -> does not see User 1's channel
        res_list = self.app.get("/api/social-media/accounts", headers=self.headers_user2)
        self.assertEqual(res_list.status_code, 200)
        u2_accounts = res_list.get_json()["accounts"]
        self.assertFalse(any(a["id"] == user1_acc_id for a in u2_accounts))

        # User 2 attempts to delete User 1's account -> 404
        res_del = self.app.delete(f"/api/social-media/accounts/{user1_acc_id}", headers=self.headers_user2)
        self.assertEqual(res_del.status_code, 404)

    @patch("requests.post")
    def test_12_token_refresh_lifecycle_and_missing_expiry(self, mock_post):
        """Test automatic token refresh when access token is expired or token_expires_at is missing."""
        conn = get_connection()
        cur = conn.cursor()
        # Account with NULL token_expires_at
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, token_expires_at, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_refresh_test_null_exp', 'Refresh Channel', %s, %s, NULL, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                token_expires_at = NULL
            RETURNING id;
        """, (
            self.user1_id,
            encrypt_token("old_access_to_refresh"),
            encrypt_token("valid_refresh_token")
        ))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        mock_refresh_resp = MagicMock(status_code=200)
        mock_refresh_resp.json.return_value = {
            "access_token": "ya29.refreshed_access_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_refresh_resp

        fresh_token = get_valid_youtube_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertEqual(fresh_token, "ya29.refreshed_access_token")

    @patch("requests.post")
    def test_13_token_refresh_rotation(self, mock_post):
        """Test that if Google rotates refresh_token, the new refresh token is encrypted and saved."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, token_expires_at, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_rotation_channel', 'Rotation Channel', %s, %s, %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                token_expires_at = EXCLUDED.token_expires_at,
                connection_status = 'ACTIVE'
            RETURNING id;
        """, (
            self.user1_id,
            encrypt_token("old_acc"),
            encrypt_token("initial_refresh_token"),
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        ))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        mock_refresh_resp = MagicMock(status_code=200)
        mock_refresh_resp.json.return_value = {
            "access_token": "ya29.rotated_access",
            "refresh_token": "1//brand_new_rotated_refresh_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_refresh_resp

        fresh_token = get_valid_youtube_access_token(account_id=acc_id, user_id=self.user1_id)
        self.assertEqual(fresh_token, "ya29.rotated_access")

        # Verify new refresh token in DB
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT encrypted_refresh_token FROM social_accounts WHERE id = %s;", (acc_id,))
        new_enc_ref = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(decrypt_token(new_enc_ref), "1//brand_new_rotated_refresh_token")

    @patch("requests.post")
    def test_14_token_refresh_permanent_vs_transient_failures(self, mock_post):
        """Test permanent invalid_grant marks account EXPIRED, while transient 5xx does not."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, token_expires_at, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_perm_fail_channel', 'Fail Channel', %s, %s, %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                token_expires_at = EXCLUDED.token_expires_at,
                connection_status = 'ACTIVE'
            RETURNING id;
        """, (
            self.user1_id,
            encrypt_token("old_acc"),
            encrypt_token("invalid_refresh"),
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        ))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # 1. Transient 503 Service Unavailable -> should raise without marking EXPIRED
        mock_post.return_value = MagicMock(status_code=503, json=lambda: {"error": "backend_error"})
        with self.assertRaises(ValueError):
            get_valid_youtube_access_token(account_id=acc_id, user_id=self.user1_id)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        self.assertEqual(cur.fetchone()[0], "ACTIVE")
        cur.close()
        conn.close()

        # 2. Permanent invalid_grant -> should mark EXPIRED
        mock_post.return_value = MagicMock(status_code=400, json=lambda: {"error": "invalid_grant"})
        with self.assertRaises(ValueError):
            get_valid_youtube_access_token(account_id=acc_id, user_id=self.user1_id)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        self.assertEqual(cur.fetchone()[0], "EXPIRED")
        cur.close()
        conn.close()

    def test_15_mandatory_user_ownership_for_token_refresh(self):
        """Test token retrieval strictly requires user_id and blocks cross-user token access."""
        # 1. Missing user_id
        with self.assertRaises(ValueError):
            get_valid_youtube_access_token(account_id=1, user_id=None)

        # 2. User 2 trying to fetch User 1's token
        with self.assertRaises(ValueError):
            get_valid_youtube_access_token(account_id=1, user_id=self.user2_id)

    @patch("requests.post")
    def test_16_revocation_post_body_and_idempotent_disconnect(self, mock_post):
        """Test disconnecting account sends token in POST body and scrubs DB idempotently."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, encrypted_refresh_token, connection_status
            )
            VALUES (%s, 'YOUTUBE', 'UC_disconnect_body_test', 'Disconnect Body Channel', %s, %s, 'ACTIVE')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                connection_status = 'ACTIVE'
            RETURNING id;
        """, (self.user1_id, encrypt_token("access_to_revoke"), encrypt_token("refresh_to_revoke")))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        mock_post.return_value = MagicMock(status_code=200)

        # Disconnect
        res1 = self.app.delete(f"/api/social-media/accounts/{acc_id}", headers=self.headers_user1)
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.get_json()["success"])

        # Verify revocation was called via POST body (data={'token': ...})
        mock_post.assert_called()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs.get("data", {}).get("token"), "refresh_to_revoke")
        self.assertNotIn("params", call_kwargs)  # Not in URL query params

        # Verify DB state
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT encrypted_access_token, encrypted_refresh_token, connection_status FROM social_accounts WHERE id = %s;", (acc_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertEqual(row[2], "DISCONNECTED")

        # Duplicate disconnect call -> idempotent success
        res2 = self.app.delete(f"/api/social-media/accounts/{acc_id}", headers=self.headers_user1)
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.get_json()["success"])

    def test_17_missing_google_configuration_rejection(self):
        """Test that attempting connection without Google credentials configured returns clear error."""
        with patch.object(Config, "GOOGLE_CLIENT_ID", ""):
            res = self.app.get("/api/social-media/connect/youtube", headers=self.headers_user1)
            self.assertEqual(res.status_code, 400)
            self.assertIn("not configured", res.get_json().get("error", "").lower())

if __name__ == "__main__":
    unittest.main()
