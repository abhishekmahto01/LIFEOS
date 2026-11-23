import os
import sys
import datetime
import unittest
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
from utils.crypto import encrypt_token, decrypt_token
from services.instagram_oauth_service import get_instagram_authorization_url


class TestFacebookPagePublishing(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        init_db()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_master (user_id, user_name, password, is_active)
            VALUES
                (1, 'admin', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE),
                (2, 'user2_test', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE)
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE;
        """)
        cur.execute("DELETE FROM social_publish_attempts;")
        cur.execute("DELETE FROM social_content_platforms;")
        cur.execute("DELETE FROM social_content;")
        cur.execute("DELETE FROM social_accounts;")
        cur.execute("DELETE FROM oauth_states;")
        conn.commit()
        cur.close()
        conn.close()

        self.headers_user1 = {"Authorization": f"Bearer {generate_token(user_id=1, username='admin')}"}
        self.headers_user2 = {"Authorization": f"Bearer {generate_token(user_id=2, username='user2_test')}"}

        Config.INSTAGRAM_CLIENT_ID = "mock_meta_app_id"
        Config.INSTAGRAM_CLIENT_SECRET = "mock_meta_app_secret"
        Config.INSTAGRAM_REDIRECT_URI = "http://localhost:5000/api/social-media/oauth/instagram/callback"
        Config.META_GRAPH_API_VERSION = "v21.0"
        Config.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"

        os.makedirs(Config.TEMP_UPLOAD_DIR, exist_ok=True)
        self.media_filename = "test_fb_video_1.mp4"
        self.media_path = os.path.join(Config.TEMP_UPLOAD_DIR, self.media_filename)
        with open(self.media_path, "wb") as f:
            f.write(b"mock_mp4_video_data_for_facebook")

    def tearDown(self):
        if os.path.exists(self.media_path):
            os.remove(self.media_path)

    def _insert_fb_page(self, user_id=1, page_id="page_fb_1", token="page_token_abc", status="ACTIVE"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name,
                encrypted_access_token, connection_status
            )
            VALUES (%s, 'FACEBOOK', %s, 'Test Page', %s, %s)
            RETURNING id;
        """, (user_id, page_id, encrypt_token(token), status))
        acc_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return acc_id

    def _insert_content(self, user_id=1):
        conn = get_connection()
        cur = conn.cursor()
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        cur.execute("""
            INSERT INTO social_content (
                user_id, title, common_caption, hashtags, media_type,
                temp_media_path, temp_file_deleted, temp_file_expires_at, overall_status
            )
            VALUES (%s, 'Gym Day 1', 'Leg day progress', '#gym #lifeos', 'VIDEO', %s, FALSE, %s, 'DRAFT')
            RETURNING id;
        """, (user_id, self.media_filename, exp))
        cid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return cid

    def _platform_row(self, cid):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT platform, platform_status, platform_post_id, platform_post_url, error_message
            FROM social_content_platforms WHERE content_id = %s;
        """, (cid,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    # ------------------------------------------------------------------ connect

    @patch("requests.get")
    def test_01_meta_connect_stores_facebook_pages_with_page_token(self, mock_get):
        """One Meta login connects the IG account and every managed Page (with its own Page token)."""
        short = MagicMock(status_code=200)
        short.json.return_value = {"access_token": "EAA_user_short", "expires_in": 7200}
        long_ = MagicMock(status_code=200)
        long_.json.return_value = {"access_token": "EAA_user_long", "expires_in": 5184000}
        pages = MagicMock(status_code=200)
        pages.json.return_value = {"data": [
            {"id": "page_brand", "name": "Brand Page", "access_token": "EAA_page_brand",
             "picture": {"data": {"url": "https://example.com/brand.jpg"}},
             "instagram_business_account": {"id": "1784_brand", "username": "archive_abhi"}},
            {"id": "page_plain", "name": "Plain Page", "access_token": "EAA_page_plain"},
        ]}
        mock_get.side_effect = [short, long_, pages]

        state = get_instagram_authorization_url(user_id=1)["state"]
        res = self.app.get(f"/api/social-media/oauth/instagram/callback?state={state}&code=c1")
        self.assertEqual(res.status_code, 302)
        self.assertIn("status=success", res.location)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT platform, platform_account_id, account_name, profile_image_url,
                   encrypted_access_token, token_expires_at
            FROM social_accounts WHERE user_id = 1 ORDER BY platform, platform_account_id;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        fb = [r for r in rows if r[0] == "FACEBOOK"]
        ig = [r for r in rows if r[0] == "INSTAGRAM"]
        self.assertEqual([r[1] for r in fb], ["page_brand", "page_plain"])
        self.assertEqual(len(ig), 1)
        brand = fb[0]
        self.assertEqual(brand[2], "Brand Page")
        self.assertEqual(brand[3], "https://example.com/brand.jpg")
        self.assertEqual(decrypt_token(brand[4]), "EAA_page_brand")  # Page token, not user token
        self.assertIsNone(brand[5])
        self.assertEqual(decrypt_token(ig[0][4]), "EAA_user_long")

    # ------------------------------------------------------------------ publish

    @patch("requests.get")
    @patch("requests.post")
    def test_02_publish_uploads_video_and_records_success(self, mock_post, mock_get):
        acc_id = self._insert_fb_page()
        cid = self._insert_content()

        upload = MagicMock(status_code=200)
        upload.json.return_value = {"id": "vid_123"}
        mock_post.return_value = upload
        perma = MagicMock(status_code=200)
        perma.json.return_value = {"permalink_url": "/page_fb_1/videos/vid_123/"}
        mock_get.return_value = perma

        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook",
                            json={"account_id": acc_id}, headers=self.headers_user1)
        body = res.get_json()
        self.assertEqual(res.status_code, 200, body)
        self.assertTrue(body["success"])
        self.assertEqual(body["publish_id"], "vid_123")
        self.assertEqual(body["publish_url"], "https://www.facebook.com/page_fb_1/videos/vid_123/")

        # Uploaded to the graph-video host with the Page token and a multipart file
        url = mock_post.call_args.args[0]
        self.assertEqual(url, "https://graph-video.facebook.com/v21.0/page_fb_1/videos")
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["data"]["access_token"], "page_token_abc")
        self.assertEqual(kwargs["data"]["title"], "Gym Day 1")
        self.assertIn("#gym", kwargs["data"]["description"])
        self.assertIn("source", kwargs["files"])

        self.assertEqual(self._platform_row(cid)[:4],
                         ("FACEBOOK", "PUBLISHED", "vid_123", "https://www.facebook.com/page_fb_1/videos/vid_123/"))
        # Source file is preserved for other platforms
        self.assertTrue(os.path.exists(self.media_path))

    @patch("requests.get")
    @patch("requests.post")
    def test_03_already_published_does_not_post_again(self, mock_post, mock_get):
        acc_id = self._insert_fb_page()
        cid = self._insert_content()
        upload = MagicMock(status_code=200)
        upload.json.return_value = {"id": "vid_once"}
        mock_post.return_value = upload
        mock_get.return_value = MagicMock(status_code=500)

        self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": acc_id}, headers=self.headers_user1)
        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": acc_id}, headers=self.headers_user1)

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("already_published"))
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.post")
    def test_04_meta_error_is_recorded_without_leaking_token(self, mock_post):
        acc_id = self._insert_fb_page(token="EAAsecretPageToken")
        cid = self._insert_content()
        err = MagicMock(status_code=403)
        err.json.return_value = {"error": {"message": "(#200) pages_manage_posts permission required EAAsecretPageToken"}}
        mock_post.return_value = err

        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": acc_id}, headers=self.headers_user1)
        body = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertFalse(body["success"])
        self.assertIn("pages_manage_posts", body["error"])
        self.assertNotIn("EAAsecretPageToken", body["error"])

        platform, status, _, _, error_message = self._platform_row(cid)
        self.assertEqual((platform, status), ("FACEBOOK", "FAILED"))
        self.assertNotIn("EAAsecretPageToken", error_message)

    @patch("requests.post")
    def test_05_rejects_other_users_page_and_non_facebook_account(self, mock_post):
        other_page = self._insert_fb_page(user_id=2, page_id="page_user2")
        cid = self._insert_content(user_id=1)

        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": other_page}, headers=self.headers_user1)
        self.assertEqual(res.status_code, 404)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, encrypted_access_token, connection_status)
            VALUES (1, 'INSTAGRAM', 'ig_x', %s, 'ACTIVE') RETURNING id;
        """, (encrypt_token("t"),))
        ig_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": ig_id}, headers=self.headers_user1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("not a Facebook Page account", res.get_json()["error"])
        mock_post.assert_not_called()

    def test_06_account_id_validation(self):
        cid = self._insert_content()
        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={}, headers=self.headers_user1)
        self.assertEqual(res.status_code, 400)
        res = self.app.post(f"/api/social-media/content/{cid}/publish/facebook", json={"account_id": "7"}, headers=self.headers_user1)
        self.assertEqual(res.status_code, 400)

    @patch("requests.get")
    @patch("requests.post")
    def test_07_unified_publish_supports_facebook(self, mock_post, mock_get):
        acc_id = self._insert_fb_page()
        cid = self._insert_content()
        upload = MagicMock(status_code=200)
        upload.json.return_value = {"id": "vid_unified"}
        mock_post.return_value = upload
        mock_get.return_value = MagicMock(status_code=500)

        res = self.app.post("/api/social-media/publish",
                            json={"content_id": cid, "targets": [{"platform": "FACEBOOK", "account_id": acc_id}]},
                            headers=self.headers_user1)
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self._platform_row(cid)[1], "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
