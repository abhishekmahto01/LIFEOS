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
from services.upload_service import (
    get_safe_temp_path,
    safe_delete_temp_file,
    validate_and_save_upload,
    create_social_content_record,
    cleanup_content_media,
    cleanup_expired_and_orphan_files,
    parse_strict_bool,
    validate_timezone,
    probe_video_with_ffprobe
)

class TestUploadPipeline(unittest.TestCase):

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

        self.mock_probe_metadata = {
            "width": 1080,
            "height": 1920,
            "duration_seconds": 15.0,
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
        }

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

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_02_successful_video_upload(self, mock_probe):
        """Test valid video upload returns 201, sanitized metadata, and stores file in temp_uploads."""
        mock_probe.return_value = self.mock_probe_metadata

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

        # Verify no absolute system path leaked or sensitive filename in client response
        res_str = json.dumps(json_data)
        self.assertNotIn("/Users/", res_str)
        self.assertNotIn("temp_uploads/", res_str)
        self.assertNotIn("media_filename", res_str)

        # Verify file exists in temp directory via DB lookup
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT temp_media_path FROM social_content WHERE id = %s;", (content_id,))
        video_filename = cur.fetchone()[0]
        cur.close()
        conn.close()

        temp_path = get_safe_temp_path(video_filename)
        self.assertTrue(os.path.exists(temp_path))

        # Clean up created file
        safe_delete_temp_file(video_filename)

    def test_03_invalid_mime_and_extension_rejected(self):
        """Test that fake extension or invalid MIME types are rejected immediately (400)."""
        # 1. Invalid extension
        data1 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "malicious.exe", "video/mp4"),
            "title": "Malicious Executable"
        }
        res1 = self.app.post("/api/social-media/upload", data=data1, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res1.status_code, 400)
        self.assertIn("Invalid video file extension", res1.get_json().get("error", ""))

        # 2. Mismatched MIME type
        data2 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "text/plain"),
            "title": "Mismatched MIME"
        }
        res2 = self.app.post("/api/social-media/upload", data=data2, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Invalid video MIME type", res2.get_json().get("error", ""))

    def test_04_corrupt_video_header_rejected(self):
        """Test that arbitrary text bytes disguised as .mp4 are rejected by signature and ffprobe validation."""
        fake_bytes = b"NOT_A_REAL_VIDEO_HEADER_JUST_RANDOM_TEXT_DATA_12345"
        data = {
            "video": (io.BytesIO(fake_bytes), "corrupt.mp4", "video/mp4"),
            "title": "Corrupt Video Test"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid video file signature", res.get_json().get("error", ""))

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_05_oversized_request_and_thumbnail_limits(self, mock_probe):
        """Test separate limits for video (413/400) and thumbnail."""
        mock_probe.return_value = self.mock_probe_metadata

        # Test thumbnail limit enforcement (MAX_THUMBNAIL_SIZE_MB = 10)
        with patch.object(Config, "MAX_THUMBNAIL_SIZE_MB", 1):
            oversized_thumb = self.valid_png_bytes + b"0" * (1024 * 1024 + 100)  # > 1MB
            data = {
                "video": (io.BytesIO(self.valid_mp4_bytes), "valid_video.mp4", "video/mp4"),
                "thumbnail": (io.BytesIO(oversized_thumb), "thumb.png", "image/png"),
                "title": "Oversized Thumbnail Test"
            }
            res_thumb = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
            self.assertEqual(res_thumb.status_code, 400)
            self.assertIn("Thumbnail file size exceeds", res_thumb.get_json().get("error", ""))

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_06_video_cleanup_when_thumbnail_validation_fails(self, mock_probe):
        """Test that saved video file is cleaned up if thumbnail validation fails."""
        mock_probe.return_value = self.mock_probe_metadata

        fake_png = b"NOT_A_PNG"
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "good_video.mp4", "video/mp4"),
            "thumbnail": (io.BytesIO(fake_png), "bad_thumb.png", "image/png"),
            "title": "Thumb Fail Test"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid image file signature", res.get_json().get("error", ""))

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_07_platform_list_validation_and_cross_user_rejection(self, mock_probe):
        """Test platform list structure, duplicate checks, and cross-user account ownership verification."""
        mock_probe.return_value = self.mock_probe_metadata

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

        # 1. Invalid platform name
        bad_platform_data = [
            {"platform": "TIKTOK", "account_id": 1}
        ]
        data1 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "video/mp4"),
            "title": "Bad Platform",
            "platforms": json.dumps(bad_platform_data)
        }
        res1 = self.app.post("/api/social-media/upload", data=data1, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res1.status_code, 400)
        self.assertIn("Invalid platform", res1.get_json().get("error", ""))

        # 2. Cross-user account ownership rejection (User 1 trying to use User 2's account)
        cross_user_platform_data = [
            {"platform": "YOUTUBE", "account_id": user2_account_id}
        ]
        data2 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "video/mp4"),
            "title": "Cross User Test",
            "platforms": json.dumps(cross_user_platform_data)
        }
        res2 = self.app.post("/api/social-media/upload", data=data2, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("not found or does not belong", res2.get_json().get("error", ""))

        # 3. Duplicate platform rejection
        duplicate_platform_data = [
            {"platform": "YOUTUBE", "account_id": 999},
            {"platform": "YOUTUBE", "account_id": 999}
        ]
        data3 = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "video/mp4"),
            "title": "Duplicate Platform Test",
            "platforms": json.dumps(duplicate_platform_data)
        }
        res3 = self.app.post("/api/social-media/upload", data=data3, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res3.status_code, 400)
        self.assertIn("Duplicate platform", res3.get_json().get("error", ""))

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_08_iana_timezone_validation(self, mock_probe):
        """Test validation of IANA timezones and rejection of invalid strings."""
        mock_probe.return_value = self.mock_probe_metadata

        # Valid timezone
        self.assertEqual(validate_timezone("Asia/Kolkata"), "Asia/Kolkata")
        self.assertEqual(validate_timezone("America/New_York"), "America/New_York")
        self.assertEqual(validate_timezone("UTC"), "UTC")

        # Invalid timezone rejection via upload endpoint
        data = {
            "video": (io.BytesIO(self.valid_mp4_bytes), "sample.mp4", "video/mp4"),
            "title": "Invalid TZ Post",
            "original_timezone": "Invalid/Fake_Zone"
        }
        res = self.app.post("/api/social-media/upload", data=data, headers=self.headers_admin, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid IANA timezone", res.get_json().get("error", ""))

    @patch("services.upload_service.probe_video_with_ffprobe")
    def test_09_strict_force_boolean_handling(self, mock_probe):
        """Test that force parameter strictly parses booleans and 'false' string does not trigger forced deletion."""
        mock_probe.return_value = self.mock_probe_metadata

        self.assertFalse(parse_strict_bool("false"))
        self.assertFalse(parse_strict_bool("0"))
        self.assertFalse(parse_strict_bool(False))
        self.assertTrue(parse_strict_bool("true"))
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
            f.write(b"dummy_bytes")

        post = create_social_content_record(
            user_id=self.user1_id,
            title="Test Force Cleanup",
            common_caption="Caption",
            hashtags="",
            media_meta=media_meta,
            platforms=[{"platform": "FACEBOOK", "account_id": acc_id}]
        )
        content_id = post["content_id"]

        # Call cleanup endpoint with force="false" string -> should NOT delete because platform is PENDING
        res_no_force = self.app.post(f"/api/social-media/cleanup/{content_id}", headers=self.headers_admin, json={"force": "false"})
        self.assertEqual(res_no_force.status_code, 200)
        self.assertFalse(res_no_force.get_json()["deleted"])
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
        """Test that safe_delete_temp_file helper rejects path traversal and returns structured statuses."""
        # 1. Directory traversal rejected
        self.assertEqual(safe_delete_temp_file("../../../etc/passwd")["status"], "rejected")
        self.assertEqual(safe_delete_temp_file("sub/folder/file.mp4")["status"], "rejected")

        # 2. Missing file status
        self.assertEqual(safe_delete_temp_file(f"non_existent_{uuid.uuid4().hex}.mp4")["status"], "missing")

        # 3. Successful deletion status
        test_filename = f"test_delete_{uuid.uuid4().hex}.tmp"
        test_path = get_safe_temp_path(test_filename)
        with open(test_path, "wb") as f:
            f.write(b"to_delete")

        self.assertEqual(safe_delete_temp_file(test_filename)["status"], "deleted")
        self.assertFalse(os.path.exists(test_path))

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_12_mock_ffprobe_execution(self, mock_which, mock_subproc):
        """Test ffprobe output parsing with mock JSON return values."""
        mock_which.return_value = "/usr/local/bin/ffprobe"

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps({
            "streams": [{"width": 1080, "height": 1920, "codec_name": "h264"}],
            "format": {"duration": "30.5", "format_name": "mov,mp4"}
        })
        mock_subproc.return_value = mock_res

        meta = probe_video_with_ffprobe("/fake/path/video.mp4")
        self.assertEqual(meta["width"], 1080)
        self.assertEqual(meta["height"], 1920)
        self.assertEqual(meta["duration_seconds"], 30.5)

if __name__ == "__main__":
    unittest.main()
