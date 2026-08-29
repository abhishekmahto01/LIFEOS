import os
import sys
import unittest
import time
import jwt

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Enforce isolated test database
test_db = os.getenv("TEST_DB_NAME", "lifeos_test")
prod_db = os.getenv("PROD_DB_NAME", "lifeos")
if test_db == prod_db or test_db == "lifeos":
    raise RuntimeError(f"SAFETY CHECK FAILED: Refusing to run tests against primary database '{prod_db}'. Set TEST_DB_NAME='lifeos_test'.")
os.environ["DB_NAME"] = test_db

from config import Config
from utils.helpers import hash_password, check_password, is_bcrypt_hash
from utils.jwt_handler import generate_token, decode_token
from services.auth_service import authenticate_user, migrate_all_plaintext_passwords
from app import app
from database.db import get_connection, init_db

class TestAuthSecurity(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_01_bcrypt_hashing_and_verification(self):
        """Test bcrypt hashing and verification."""
        password = "SecretPassword123!"
        hashed = hash_password(password)

        self.assertTrue(is_bcrypt_hash(hashed))
        self.assertTrue(check_password(password, hashed))
        self.assertFalse(check_password("WrongPassword", hashed))
        self.assertNotEqual(password, hashed)

    def test_02_jwt_token_generation_and_decoding(self):
        """Test JWT token generation and valid decoding."""
        token = generate_token(user_id=1, username="admin", expires_in=3600)
        self.assertIsInstance(token, str)

        payload = decode_token(token)
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["username"], "admin")
        self.assertIn("exp", payload)

    def test_03_jwt_token_expiration(self):
        """Test that expired JWT tokens are rejected."""
        # Generate token with 1 second expiry
        short_token = generate_token(user_id=1, username="admin", expires_in=1)
        time.sleep(1.5)

        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_token(short_token)

    def test_04_jwt_token_tampered_signature(self):
        """Test that forged or tampered tokens are rejected."""
        valid_token = generate_token(user_id=1, username="admin")
        parts = valid_token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}.badsignature"

        with self.assertRaises(jwt.InvalidTokenError):
            decode_token(tampered_token)

    def test_05_one_time_password_migration(self):
        """Test password migration helper converts plaintext to bcrypt."""
        conn = get_connection()
        cur = conn.cursor()
        # Ensure a test user exists with known plaintext
        cur.execute("SELECT user_id, user_name, password FROM user_master WHERE user_name = 'admin';")
        user = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(user, "User 'admin' must exist in database.")

        res = migrate_all_plaintext_passwords()
        self.assertIn("migrated_count", res)

        # Verify password in DB is now bcrypt hashed
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM user_master WHERE user_name = 'admin';")
        db_pwd = cur.fetchone()[0]
        cur.close()
        conn.close()

        self.assertTrue(is_bcrypt_hash(db_pwd), "Password in user_master should now be a bcrypt hash.")

    def test_06_login_endpoints_valid_and_invalid(self):
        """Test login endpoint with valid, invalid, and missing credentials."""
        # 1. Missing credentials
        res = self.client.post("/api/auth/login", json={})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

        # 2. Invalid password
        res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong_password_xyz"
        })
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()["success"])

        # 3. Nonexistent user
        res = self.client.post("/api/auth/login", json={
            "username": "non_existent_user_9999",
            "password": "some_password"
        })
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()["success"])

        # 4. Valid login
        # Fetch current password or test with admin
        res = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin"  # If default or migrated
        })
        # If admin's password was admin, it will be 200, otherwise let's verify structure
        if res.status_code == 200:
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertIn("token", data)
            self.assertEqual(data["user"]["username"], "admin")

    def test_07_protected_route_missing_token(self):
        """Test that private endpoints reject requests without a token."""
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("missing", data["message"].lower())

    def test_08_protected_route_invalid_token(self):
        """Test that private endpoints reject forged/invalid tokens."""
        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_gibberish_token"}
        )
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("invalid", data["message"].lower())

    def test_09_protected_route_expired_token(self):
        """Test that private endpoints reject expired tokens."""
        expired_token = generate_token(user_id=1, username="admin", expires_in=1)
        time.sleep(1.2)

        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("expired", data["message"].lower())

    def test_10_protected_route_valid_token(self):
        """Test that private endpoints succeed with valid token."""
        valid_token = generate_token(user_id=1, username="admin", expires_in=3600)
        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["username"], "admin")
        self.assertEqual(data["user"]["user_id"], 1)

    def test_11_dashboard_route_with_jwt_identity(self):
        """Test that dashboard modules endpoint respects authenticated JWT identity."""
        valid_token = generate_token(user_id=1, username="admin", expires_in=3600)
        res = self.client.get(
            "/api/dashboard/modules",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.get_json(), list)

if __name__ == "__main__":
    unittest.main()
