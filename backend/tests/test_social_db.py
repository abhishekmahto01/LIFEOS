import os
import sys
import unittest
import datetime
import hashlib

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database.db import get_connection, init_db
from database.social_media_schema import create_social_media_schema
from utils.crypto import encrypt_token, decrypt_token

class TestSocialMediaDatabase(unittest.TestCase):

    def setUp(self):
        # Run database initialization
        init_db()

    def test_01_schema_creation_and_double_execution_idempotency(self):
        """Test that schema migration runs cleanly and is completely idempotent on repeated executions."""
        conn = get_connection()
        try:
            # Run migration first time
            create_social_media_schema(conn)
            conn.commit()

            # Run migration second time (idempotency check)
            create_social_media_schema(conn)
            conn.commit()

            # Verify all 6 required tables exist
            required_tables = [
                "social_accounts",
                "social_content",
                "social_content_platforms",
                "social_publish_attempts",
                "social_analytics",
                "oauth_states"
            ]

            cur = conn.cursor()
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s);
            """, (required_tables,))
            existing_tables = [r[0] for r in cur.fetchall()]
            cur.close()

            for tbl in required_tables:
                self.assertIn(tbl, existing_tables, f"Table {tbl} must exist in database.")
        finally:
            conn.close()

    def test_02_fernet_token_encryption_security(self):
        """Test Fernet authenticated token encryption, key validation, and failure modes."""
        from cryptography.fernet import Fernet
        valid_key_1 = Fernet.generate_key().decode()
        valid_key_2 = Fernet.generate_key().decode()

        sample_oauth_token = "ya29.a0AfH6SMD_secret_google_oauth_token_example_12345"

        # 1. Valid encryption and decryption
        encrypted = encrypt_token(sample_oauth_token, key=valid_key_1)
        self.assertIsInstance(encrypted, str)
        self.assertNotEqual(encrypted, sample_oauth_token)

        # 2. Plaintext token is not present in ciphertext
        self.assertNotIn("ya29", encrypted)
        self.assertNotIn("secret_google", encrypted)

        # Decrypt with correct key
        decrypted = decrypt_token(encrypted, key=valid_key_1)
        self.assertEqual(decrypted, sample_oauth_token)

        # 3. Missing encryption key is rejected with clear error
        with self.assertRaises(ValueError) as ctx:
            encrypt_token(sample_oauth_token, key="")
        self.assertIn("missing", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            decrypt_token(encrypted, key="")
        self.assertIn("missing", str(ctx.exception).lower())

        # 4. Invalid encryption key is rejected with clear error
        with self.assertRaises(ValueError) as ctx:
            encrypt_token(sample_oauth_token, key="invalid_non_base64_arbitrary_string")
        self.assertIn("invalid", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            decrypt_token(encrypted, key="invalid_non_base64_arbitrary_string")
        self.assertIn("invalid", str(ctx.exception).lower())

        # 5. Wrong key cannot decrypt existing ciphertext
        with self.assertRaises(ValueError) as ctx:
            decrypt_token(encrypted, key=valid_key_2)
        self.assertIn("invalid encryption key or corrupted data", str(ctx.exception).lower())

        # Empty/None token handling
        self.assertEqual(encrypt_token(""), "")
        self.assertEqual(decrypt_token(""), "")

    def test_03_platform_check_constraints(self):
        """Test that only allowed platform values ('YOUTUBE', 'INSTAGRAM', 'FACEBOOK') are accepted."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            # 1. Valid platforms in social_accounts
            for plat in ['YOUTUBE', 'INSTAGRAM', 'FACEBOOK']:
                cur.execute("""
                    INSERT INTO social_accounts (user_id, platform, platform_account_id, account_name)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (user_id, plat, f"test_{plat.lower()}_123", f"Test {plat}"))
                acc_id = cur.fetchone()[0]
                cur.execute("DELETE FROM social_accounts WHERE id = %s;", (acc_id,))

            # 2. Invalid platform in social_accounts must fail
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_accounts (user_id, platform, platform_account_id)
                    VALUES (%s, 'TIKTOK', 'tiktok_123');
                """, (user_id,))
            conn.rollback()

            # 3. Valid platforms in social_content_platforms
            cur.execute("INSERT INTO social_content (user_id, title) VALUES (%s, 'Test Post') RETURNING id;", (user_id,))
            content_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO social_accounts (user_id, platform, platform_account_id)
                VALUES (%s, 'YOUTUBE', 'yt_temp_id') RETURNING id;
            """, (user_id,))
            account_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO social_content_platforms (content_id, account_id, platform)
                VALUES (%s, %s, 'YOUTUBE') RETURNING id;
            """, (content_id, account_id))
            scp_id = cur.fetchone()[0]

            # Invalid platform in social_content_platforms must fail
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_content_platforms (content_id, account_id, platform)
                    VALUES (%s, %s, 'TWITTER');
                """, (content_id, account_id))
            conn.rollback()

            # Clean up
            cur.execute("DELETE FROM social_content WHERE id = %s;", (content_id,))
            cur.execute("DELETE FROM social_accounts WHERE id = %s;", (account_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_04_status_check_constraints(self):
        """Test check constraints on overall_status, connection_status, and platform_status."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            # 1. Valid connection_status in social_accounts
            for st in ['ACTIVE', 'EXPIRED', 'REVOKED', 'DISCONNECTED', 'ERROR']:
                cur.execute("""
                    INSERT INTO social_accounts (user_id, platform, platform_account_id, connection_status)
                    VALUES (%s, 'YOUTUBE', %s, %s)
                    RETURNING id;
                """, (user_id, f"acc_{st}", st))
                aid = cur.fetchone()[0]
                cur.execute("DELETE FROM social_accounts WHERE id = %s;", (aid,))

            # 2. Invalid connection_status must fail
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_accounts (user_id, platform, platform_account_id, connection_status)
                    VALUES (%s, 'YOUTUBE', 'acc_bad', 'INVALID_STATUS');
                """, (user_id,))
            conn.rollback()

            # 3. Valid overall_status in social_content
            for st in ['DRAFT', 'SCHEDULED', 'PROCESSING', 'PUBLISHED', 'PARTIALLY_PUBLISHED', 'FAILED', 'DELETED']:
                cur.execute("""
                    INSERT INTO social_content (user_id, title, overall_status)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                """, (user_id, f"Title {st}", st))
                cid = cur.fetchone()[0]
                cur.execute("DELETE FROM social_content WHERE id = %s;", (cid,))

            # 4. Invalid overall_status must fail
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_content (user_id, title, overall_status)
                    VALUES (%s, 'Bad Post', 'UNKNOWN_STATUS');
                """, (user_id,))
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    def test_05_expiry_and_timezone_fields(self):
        """Test presence and behavior of original_timezone and temp_file_expires_at fields."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            future_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)

            cur.execute("""
                INSERT INTO social_content (user_id, title, original_timezone, temp_file_expires_at)
                VALUES (%s, 'Timezone Test', 'Asia/Kolkata', %s)
                RETURNING id, original_timezone, temp_file_expires_at;
            """, (user_id, future_expiry))
            row = cur.fetchone()
            cid, tz, exp = row

            self.assertEqual(tz, 'Asia/Kolkata')
            self.assertIsNotNone(exp)

            # Clean up
            cur.execute("DELETE FROM social_content WHERE id = %s;", (cid,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_06_idempotency_key_uniqueness_in_publish_attempts(self):
        """Test that publish attempts enforce uniqueness on idempotency_key."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            cur.execute("INSERT INTO social_content (user_id, title) VALUES (%s, 'Idempotency Test') RETURNING id;", (user_id,))
            cid = cur.fetchone()[0]
            cur.execute("INSERT INTO social_accounts (user_id, platform, platform_account_id) VALUES (%s, 'FACEBOOK', 'fb_idem_1') RETURNING id;", (user_id,))
            aid = cur.fetchone()[0]
            cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform) VALUES (%s, %s, 'FACEBOOK') RETURNING id;", (cid, aid))
            scpid = cur.fetchone()[0]

            idempotency_key = "unique-uuid-publish-attempt-12345"

            # First attempt with idempotency key succeeds
            cur.execute("""
                INSERT INTO social_publish_attempts (content_platform_id, attempt_number, status, idempotency_key, error_code)
                VALUES (%s, 1, 'STARTED', %s, 'NONE')
                RETURNING id;
            """, (scpid, idempotency_key))
            conn.commit()

            # Second attempt with same idempotency key must fail unique constraint
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_publish_attempts (content_platform_id, attempt_number, status, idempotency_key)
                    VALUES (%s, 2, 'STARTED', %s);
                """, (scpid, idempotency_key))
            conn.rollback()

            # Clean up
            cur.execute("DELETE FROM social_content WHERE id = %s;", (cid,))
            cur.execute("DELETE FROM social_accounts WHERE id = %s;", (aid,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_07_analytics_constraints_and_negative_rejection(self):
        """Test that analytics rejects negative counts, invalid engagement rates, and duplicate snapshots."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            cur.execute("INSERT INTO social_content (user_id, title) VALUES (%s, 'Analytics Test') RETURNING id;", (user_id,))
            cid = cur.fetchone()[0]
            cur.execute("INSERT INTO social_accounts (user_id, platform, platform_account_id) VALUES (%s, 'INSTAGRAM', 'ig_analytics_1') RETURNING id;", (user_id,))
            aid = cur.fetchone()[0]
            cur.execute("INSERT INTO social_content_platforms (content_id, account_id, platform) VALUES (%s, %s, 'INSTAGRAM') RETURNING id;", (cid, aid))
            scpid = cur.fetchone()[0]

            snapshot_time = datetime.datetime.now(datetime.timezone.utc)

            # 1. Valid analytics insert
            cur.execute("""
                INSERT INTO social_analytics (content_platform_id, views_count, likes_count, comments_count, shares_count, engagement_rate, fetched_at)
                VALUES (%s, 1000, 50, 10, 5, 6.5000, %s)
                RETURNING id;
            """, (scpid, snapshot_time))
            conn.commit()

            # 2. Duplicate snapshot timestamp for same content_platform_id must fail unique constraint
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_analytics (content_platform_id, views_count, fetched_at)
                    VALUES (%s, 1050, %s);
                """, (scpid, snapshot_time))
            conn.rollback()

            # 3. Negative views_count must fail check constraint
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_analytics (content_platform_id, views_count)
                    VALUES (%s, -5);
                """, (scpid,))
            conn.rollback()

            # 4. Invalid engagement rate > 100 must fail check constraint
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO social_analytics (content_platform_id, engagement_rate)
                    VALUES (%s, 150.0000);
                """, (scpid,))
            conn.rollback()

            # Clean up
            cur.execute("DELETE FROM social_content WHERE id = %s;", (cid,))
            cur.execute("DELETE FROM social_accounts WHERE id = %s;", (aid,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_08_oauth_states_hash_and_consumed_timestamp(self):
        """Test SHA-256 hashed state storage, single-use consumed_at, and platform constraints."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM user_master LIMIT 1;")
            user_id = cur.fetchone()[0]

            raw_state = "raw_random_oauth_state_string_xyz789"
            state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

            # 1. Valid state insert
            cur.execute("""
                INSERT INTO oauth_states (state_hash, user_id, platform, redirect_uri, expires_at)
                VALUES (%s, %s, 'YOUTUBE', 'http://localhost:5000/callback', %s)
                RETURNING id;
            """, (state_hash, user_id, expires_at))
            state_id = cur.fetchone()[0]
            conn.commit()

            # 2. Mark state as consumed (single-use)
            consumed_now = datetime.datetime.now(datetime.timezone.utc)
            cur.execute("UPDATE oauth_states SET consumed_at = %s WHERE id = %s;", (consumed_now, state_id))
            conn.commit()

            # 3. Duplicate state_hash must fail
            with self.assertRaises(Exception):
                cur.execute("""
                    INSERT INTO oauth_states (state_hash, user_id, platform, expires_at)
                    VALUES (%s, %s, 'YOUTUBE', %s);
                """, (state_hash, user_id, expires_at))
            conn.rollback()

            # Clean up
            cur.execute("DELETE FROM oauth_states WHERE id = %s;", (state_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_09_existing_lifeos_data_preservation(self):
        """Verify that existing LifeOS core tables and rows are completely preserved."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            core_tables = [
                "user_master",
                "module_master",
                "user_module_permission",
                "job_apply_mt",
                "job_apply_dt",
                "discipline_daily"
            ]

            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s);
            """, (core_tables,))
            found_core_tables = [r[0] for r in cur.fetchall()]

            for tbl in core_tables:
                self.assertIn(tbl, found_core_tables, f"Core table {tbl} must be preserved.")

            cur.execute("SELECT COUNT(*) FROM user_master;")
            user_count = cur.fetchone()[0]
            self.assertGreater(user_count, 0, "user_master must have existing users.")
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    unittest.main()
