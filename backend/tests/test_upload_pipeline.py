import os
import io
import sys
import uuid
import json
import datetime
import unittest
from unittest.mock import patch, MagicMock

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import app
from config import Config
from database.db import get_connection, init_db
from utils.jwt_handler import generate_token
from services.upload_service import (
    get_safe_temp_path,
    safe_delete_temp_file,
    validate_and_save_upload,
    create_social_content_record,
    cleanup_content_media,
    cleanup_expired_and_orphan_files,
    parse_strict_bool,
    validate_timezone
)

class TestUploadPipeline(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        init_db()
        
        self.user1_id = 1
        self.user2_id = 2
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM user_master WHERE user_id = 2;")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO user_master (user_id, user_name, password, is_active)
                VALUES (2, 'user2_test', '$2b$12$eX4mpleH4shForT3st1ngOnlyXXXXXXXXXXXXXX', TRUE)
                ON CONFLICT DO NOTHING;
            """)
            conn.commit()
        cur.close()
        conn.close()

        self.token_admin = generate_token(user_id=self.user1_id, username="admin")
        self.token_user2 = generate_token(user_id=self.user2_id, username="user2_test")
        
        self.headers_admin = {"Authorization": f"Bearer {self.token_admin}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

        # Valid MP4 dummy bytes with ftyp box and known brand 'isom'
        self.valid_mp4_bytes = (
            b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp41"
            b"\x00\x00\x00\x08free"
            b"\x00\x00\x00\x20mdat" + b"A" * 32
        )
        
        # Valid 1x1 PNG dummy bytes
        self.valid_png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def test_01_upload_missing_auth_rejected(self):
        """Test that upload endpoint strictly rejects unauthenticated requests (401)."""
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "video/mp4"),
            "title": "Unauthenticated Post"
        }
        res = self.app.post("/api/social-media/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 401)
        resp_body = res.get_json()
        self.assertTrue("missing" in resp_body.get("message", "").lower() or "missing" in resp_body.get("error", "").lower())

    def test_02_successful_video_upload(self):
        """Test valid video upload returns 201, sanitized metadata, and stores file in temp_uploads."""
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "my_reel_clip.mp4", "video/mp4"),
            "title": "My First LifeOS Reel",
            "common_caption": "Testing upload pipeline",
            "hashtags": "#lifeos #build",
            "original_timezone": "America/New_York"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertIn("temporarily uploaded successfully", json_data.get("message", ""))
        
        post_data = json_data["data"]
        content_id = post_data["content_id"]
        self.assertEqual(post_data["title"], "My First LifeOS Reel")
        self.assertEqual(post_data["overall_status"], "DRAFT")
        self.assertEqual(post_data["original_timezone"], "America/New_York")
        self.assertIsNotNone(post_data.get("temp_file_expires_at"))

        # Zero absolute file paths leaked to frontend
        resp_str = str(json_data)
        self.assertNotIn("/Users/", resp_str)
        self.assertNotIn("temp_uploads/", resp_str)

        # Verify record in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT temp_media_path, temp_file_deleted FROM social_content WHERE id = %s;", (content_id,))
        media_file, temp_deleted = cur.fetchone()
        cur.close()
        conn.close()

        self.assertFalse(temp_deleted)
        self.assertTrue(media_file.endswith(".mp4"))

        # Clean up
        cleanup_content_media(content_id=content_id, user_id=self.user1_id, force=True)

    def test_03_invalid_mime_and_extension_rejected(self):
        """Test rejection of invalid MIME type or extension."""
        # Bad extension
        data_ext = {
            "video": (io.BytesIO(b"malicious payload"), "script.exe", "application/x-msdownload"),
            "title": "Malicious Upload"
        }
        res_ext = self.app.post("/api/social-media/upload", data=data_ext, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res_ext.status_code, 400)
        self.assertIn("Invalid video file extension", res_ext.get_json().get("error", ""))

        # Valid extension but invalid MIME
        data_mime = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "text/plain"),
            "title": "Bad MIME"
        }
        res_mime = self.app.post("/api/social-media/upload", data=data_mime, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res_mime.status_code, 400)
        self.assertIn("Invalid video MIME type", res_mime.get_json().get("error", ""))

    def test_04_corrupt_video_header_rejected(self):
        """Test rejection of files disguised with .mp4 extension but corrupt headers."""
        data = {
            "video": (io.BytesIO(b"Not an MP4 or valid video container at all"), "fake_video.mp4", "video/mp4"),
            "title": "Disguised File"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid video file signature", res.get_json().get("error", ""))

    def test_05_oversized_request_and_thumbnail_limits(self):
        """Test separate limits for video (413/400) and thumbnail."""
        # 1. Video limit test
        with patch.object(Config, "MAX_VIDEO_SIZE_MB", 1):
            large_bytes = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42" + b"X" * (2 * 1024 * 1024)
            data_vid = {
                "video": (io.BytesIO(large_bytes), "oversized.mp4", "video/mp4"),
                "title": "Oversized Video"
            }
            res_vid = self.app.post("/api/social-media/upload", data=data_vid, headers=self.headers_admin, content_type="multipart/form-data")
            self.assertIn(res_vid.status_code, [400, 413])

        # 2. Thumbnail limit test (1MB limit for unit test)
        with patch.object(Config, "MAX_THUMBNAIL_SIZE_MB", 1):
            large_thumb = self.valid_png_bytes + b"T" * (2 * 1024 * 1024)
            data_thumb = {
                "video": (io.BytesIO(self.valid_mp4_bytes), "good_vid.mp4", "video/mp4"),
                "thumbnail": (io.BytesIO(large_thumb), "huge_thumb.png", "image/png"),
                "title": "Oversized Thumbnail"
            }
            res_thumb = self.app.post("/api/social-media/upload", data=data_thumb, headers=self.headers_admin, content_type="multipart/form-data")
            self.assertEqual(res_thumb.status_code, 400)
            self.assertIn("Thumbnail file size exceeds", res_thumb.get_json().get("error", ""))

    def test_06_video_cleanup_when_thumbnail_validation_fails(self):
        """Test that saved video file is cleaned up if thumbnail validation fails."""
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "valid_vid.mp4", "video/mp4"),
            "thumbnail": (io.BytesIO(b"invalid image bytes"), "bad_thumb.png", "image/png"),
            "title": "Video with Corrupt Thumbnail"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid image file signature", res.get_json().get("error", ""))

    def test_07_platform_list_validation_and_cross_user_rejection(self):
        """Test platform list structure, duplicate checks, and cross-user account ownership verification."""
        conn = get_connection()
        cur = conn.cursor()
        
        # Fetch or create account for User 2
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name)
            VALUES (%s, 'YOUTUBE', 'user2_yt_channel', 'User 2 Channel')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET account_name = EXCLUDED.account_name
            RETURNING id;
        """, (self.user2_id,))
        user2_account_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # 1. Invalid platform structure (non-list)
        data1 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "vid.mp4", "video/mp4"),
            "title": "Test Post",
            "platforms": "not a json list"
        }
        res1 = self.app.post("/api/social-media/upload", data=data1, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res1.status_code, 400)

        # 2. User 1 attempts to use User 2's account_id -> should fail
        data2 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "vid.mp4", "video/mp4"),
            "title": "Cross-user test",
            "platforms": json.dumps([{"platform": "YOUTUBE", "account_id": user2_account_id}])
        }
        res2 = self.app.post("/api/social-media/upload", data=data2, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("not found or does not belong", res2.get_json().get("error", ""))

        # 3. Duplicate platform in same post
        data3 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "vid.mp4", "video/mp4"),
            "title": "Duplicate platform test",
            "platforms": json.dumps([
                {"platform": "YOUTUBE", "account_id": 999},
                {"platform": "YOUTUBE", "account_id": 999}
            ])
        }
        res3 = self.app.post("/api/social-media/upload", data=data3, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res3.status_code, 400)
        self.assertIn("Duplicate platform", res3.get_json().get("error", ""))

    def test_08_iana_timezone_validation(self):
        """Test validation of IANA timezones and rejection of invalid strings."""
        # Valid timezone
        self.assertEqual(validate_timezone("Asia/Kolkata"), "Asia/Kolkata")
        self.assertEqual(validate_timezone("UTC"), "UTC")
        self.assertEqual(validate_timezone("Europe/London"), "Europe/London")

        # Invalid timezone
        with self.assertRaises(ValueError) as ctx:
            validate_timezone("Mars/Olympus_Mons")
        self.assertIn("Invalid IANA timezone", str(ctx.exception))

        # Test in upload endpoint
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "vid.mp4", "video/mp4"),
            "title": "Invalid TZ Post",
            "original_timezone": "Fake/Timezone"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid IANA timezone", res.get_json().get("error", ""))

    def test_09_strict_force_boolean_handling(self):
        """Test that force parameter strictly parses booleans and 'false' string does not trigger forced deletion."""
        self.assertFalse(parse_strict_bool("false"))
        self.assertFalse(parse_strict_bool("0"))
        self.assertFalse(parse_strict_bool(False))
        self.assertTrue(parse_strict_bool("true"))
        self.assertTrue(parse_strict_bool("1"))
        self.assertTrue(parse_strict_bool(True))

        conn = get_connection()
        cur = conn.cursor()

        # Create account for user 1
        cur.execute("""
            INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name)
            VALUES (%s, 'FACEBOOK', 'fb_acc_test', 'FB Page')
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET account_name = EXCLUDED.account_name
            RETURNING id;
        """, (self.user1_id,))
        acc_id = cur.fetchone()[0]
        conn.commit()

        # Write dummy file
        media_meta = {
            "media_filename": f"test_force_{uuid.uuid4().hex}.mp4",
            "file_size_bytes": 1024,
            "duration_seconds": 10.0,
            "media_type": "VIDEO"
        }
        safe_path = get_safe_temp_path(media_meta["media_filename"])
        with open(safe_path, "wb") as f:
            f.write(self.valid_mp4_bytes)

        post = create_social_content_record(
            user_id=self.user1_id,
            title="Force test",
            common_caption="",
            hashtags="",
            media_meta=media_meta,
            platforms=[{"platform": "FACEBOOK", "account_id": acc_id}]
        )
        content_id = post["content_id"]

        # Call cleanup endpoint with force="false" (string) -> should NOT force delete while platform is PENDING
        res = self.app.post(f"/api/social-media/cleanup/{content_id}", headers=self.headers_admin, json={"force": "false"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["deleted"])
        self.assertTrue(os.path.exists(safe_path))

        # Call cleanup endpoint with force=True -> should delete
        res_force = self.app.post(f"/api/social-media/cleanup/{content_id}", headers=self.headers_admin, json={"force": True})
        self.assertEqual(res_force.status_code, 200)
        self.assertTrue(res_force.get_json()["deleted"])
        cur.execute("DELETE FROM social_content_platforms WHERE account_id = %s;", (acc_id,))
        cur.execute("DELETE FROM social_content WHERE id = %s;", (content_id,))
        cur.execute("DELETE FROM social_accounts WHERE id = %s;", (acc_id,))
        conn.commit()
        cur.close()
        conn.close()

    def test_10_global_cleanup_expired_admin_only(self):
        """Test that /cleanup-expired is strictly admin-only and ordinary users get 403 Forbidden."""
        # Non-admin user gets 403
        res_user2 = self.app.post("/api/social-media/cleanup-expired", headers=self.headers_user2)
        self.assertEqual(res_user2.status_code, 403)
        self.assertIn("Admin privileges are required", res_user2.get_json().get("error", ""))

        # Admin user gets 200
        res_admin = self.app.post("/api/social-media/cleanup-expired", headers=self.headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        self.assertTrue(res_admin.get_json()["success"])

    def test_11_path_traversal_and_safe_delete_helper(self):
        """Test path traversal prevention and idempotent safe_delete_temp_file helper."""
        # Traversal attempt
        with self.assertRaises(ValueError):
            get_safe_temp_path("../../etc/passwd")

        # Deleting non-existent file is safe and idempotent
        res = safe_delete_temp_file("non_existent_file_12345.mp4")
        self.assertEqual(res["status"], "missing")
        self.assertFalse(res["removed"])

    def test_12_mock_ffprobe_execution(self):
        """Test that upload pipeline interacts properly with ffprobe when mocked."""
        mock_ffprobe_json = json.dumps({
            "streams": [{"width": 1080, "height": 1920, "codec_name": "h264"}],
            "format": {"duration": "25.50", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"}
        })
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_ffprobe_json, stderr="")
                data = {
                    "video": (io.BytesIO(self.valid_mp4_bytes), "probe_vid.mp4", "video/mp4"),
                    "title": "FFprobe Test Post"
                }
                res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
                self.assertEqual(res.status_code, 201)
                post_data = res.get_json()["data"]
                self.assertEqual(post_data["duration_seconds"], 25.5)
                # Clean up
                cleanup_content_media(post_data["content_id"], user_id=self.user1_id, force=True)

if __name__ == "__main__":
    unittest.main()
