import os
import sys
import unittest
import json

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
from database.db import get_connection, init_db
from utils.jwt_handler import generate_token
from utils.helpers import hash_password


class TestModulePermissions(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        init_db()

        conn = get_connection()
        cur = conn.cursor()

        # Create/reset test users
        # 1. admin (user_id = 1)
        # 2. ayush (user_id = 201)
        # 3. neha (user_id = 202)
        # 4. restricted_user (user_id = 203)
        self.admin_id = 1
        self.ayush_id = 201
        self.neha_id = 202
        self.restricted_id = 203

        test_users = [
            (self.admin_id, "admin", hash_password("admin123"), True),
            (self.ayush_id, "ayush", hash_password("ayush123"), True),
            (self.neha_id, "neha", hash_password("neha123"), True),
            (self.restricted_id, "restricted_user", hash_password("restricted123"), True)
        ]

        for uid, uname, pwd, active in test_users:
            cur.execute("""
                INSERT INTO user_master (user_id, user_name, password, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE 
                SET user_name = EXCLUDED.user_name, password = EXCLUDED.password, is_active = EXCLUDED.is_active;
            """, (uid, uname, pwd, active))

        # Clear permissions for test users 201, 202, 203
        cur.execute("DELETE FROM user_module_permission WHERE user_id IN (%s, %s, %s);", (self.ayush_id, self.neha_id, self.restricted_id))

        # Fetch module IDs
        cur.execute("SELECT id, module_code FROM module_master WHERE is_active = TRUE;")
        self.module_map = {row[1]: row[0] for row in cur.fetchall()}

        disc_id = self.module_map.get("discipline")
        career_id = self.module_map.get("career")

        # Assign Ayush: Discipline only
        if disc_id:
            cur.execute("""
                INSERT INTO user_module_permission (user_id, module_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (self.ayush_id, disc_id))

        # Assign Neha: Discipline + Career
        if disc_id and career_id:
            cur.execute("""
                INSERT INTO user_module_permission (user_id, module_id)
                VALUES (%s, %s), (%s, %s) ON CONFLICT DO NOTHING;
            """, (self.neha_id, disc_id, self.neha_id, career_id))

        conn.commit()
        cur.close()
        conn.close()

        # Auth Tokens & Headers
        self.token_admin = generate_token(user_id=self.admin_id, username="admin")
        self.token_ayush = generate_token(user_id=self.ayush_id, username="ayush")
        self.token_neha = generate_token(user_id=self.neha_id, username="neha")
        self.token_restricted = generate_token(user_id=self.restricted_id, username="restricted_user")

        self.headers_admin = {"Authorization": f"Bearer {self.token_admin}"}
        self.headers_ayush = {"Authorization": f"Bearer {self.token_ayush}"}
        self.headers_neha = {"Authorization": f"Bearer {self.token_neha}"}
        self.headers_restricted = {"Authorization": f"Bearer {self.token_restricted}"}

    def test_01_admin_gets_all_active_modules(self):
        """1. Admin automatically receives all active modules without manual assignment."""
        res = self.app.get("/api/me/modules", headers=self.headers_admin)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        codes = [m["module_code"] for m in data["modules"]]
        self.assertIn("admin", codes)
        self.assertIn("discipline", codes)
        self.assertIn("career", codes)
        self.assertIn("social_media", codes)

    def test_02_ayush_gets_only_assigned_modules(self):
        """2. Ayush receives only assigned modules (Discipline only), and never Admin."""
        res = self.app.get("/api/me/modules", headers=self.headers_ayush)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        codes = [m["module_code"] for m in data["modules"]]
        self.assertEqual(codes, ["discipline"])
        self.assertNotIn("admin", codes)
        self.assertNotIn("career", codes)
        self.assertNotIn("social_media", codes)

    def test_03_neha_gets_discipline_and_career(self):
        """Neha receives only Discipline and Career modules."""
        res = self.app.get("/api/me/modules", headers=self.headers_neha)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        codes = [m["module_code"] for m in data["modules"]]
        self.assertIn("discipline", codes)
        self.assertIn("career", codes)
        self.assertNotIn("social_media", codes)
        self.assertNotIn("admin", codes)

    def test_04_user_without_permission_cannot_access_career(self):
        """3. Ayush (who only has Discipline) cannot access Career APIs (403 Forbidden)."""
        res = self.app.get("/api/jobs/history", headers=self.headers_ayush)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn("You do not have access to this module", data.get("error", ""))

    def test_05_user_without_permission_cannot_access_social_media(self):
        """4. Ayush and Neha cannot access Social Media APIs (403 Forbidden)."""
        res_ayush = self.app.get("/api/social-media/accounts", headers=self.headers_ayush)
        self.assertEqual(res_ayush.status_code, 403)
        self.assertIn("You do not have access to this module", res_ayush.get_json().get("error", ""))

        res_neha = self.app.get("/api/social-media/dashboard", headers=self.headers_neha)
        self.assertEqual(res_neha.status_code, 403)
        self.assertIn("You do not have access to this module", res_neha.get_json().get("error", ""))

    def test_06_normal_user_cannot_access_admin_endpoints(self):
        """5. Normal users cannot access Admin APIs (403 Forbidden)."""
        res_users = self.app.get("/api/admin/users", headers=self.headers_ayush)
        self.assertEqual(res_users.status_code, 403)
        self.assertIn("Admin access required", res_users.get_json().get("error", ""))

        res_modules = self.app.get("/api/admin/modules", headers=self.headers_neha)
        self.assertEqual(res_modules.status_code, 403)

    def test_07_admin_can_assign_module_to_user(self):
        """6. Admin can assign Career & Social Media to Ayush."""
        career_id = self.module_map["career"]
        disc_id = self.module_map["discipline"]
        sm_id = self.module_map["social_media"]

        # Update Ayush permissions to Discipline + Career + Social Media
        res = self.app.put(
            f"/api/admin/users/{self.ayush_id}/modules",
            headers=self.headers_admin,
            json={"module_ids": [disc_id, career_id, sm_id]}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Verify Ayush now has access
        res_me = self.app.get("/api/me/modules", headers=self.headers_ayush)
        codes = [m["module_code"] for m in res_me.get_json()["modules"]]
        self.assertIn("career", codes)
        self.assertIn("social_media", codes)
        self.assertIn("discipline", codes)

        # Ayush can now query career
        res_career = self.app.get("/api/jobs/history", headers=self.headers_ayush)
        self.assertEqual(res_career.status_code, 200)

    def test_08_admin_can_remove_module_from_user(self):
        """7. Admin can revoke Career from Neha so she only has Discipline."""
        disc_id = self.module_map["discipline"]

        res = self.app.put(
            f"/api/admin/users/{self.neha_id}/modules",
            headers=self.headers_admin,
            json={"module_ids": [disc_id]}
        )
        self.assertEqual(res.status_code, 200)

        # Verify Neha now lacks Career
        res_me = self.app.get("/api/me/modules", headers=self.headers_neha)
        codes = [m["module_code"] for m in res_me.get_json()["modules"]]
        self.assertEqual(codes, ["discipline"])

        # Neha gets 403 on Career
        res_career = self.app.get("/api/jobs/history", headers=self.headers_neha)
        self.assertEqual(res_career.status_code, 403)

    def test_09_duplicate_mappings_are_prevented(self):
        """8. Duplicate module IDs in payload or database are safely handled."""
        disc_id = self.module_map["discipline"]

        # Send duplicate module IDs [disc_id, disc_id, disc_id]
        res = self.app.put(
            f"/api/admin/users/{self.restricted_id}/modules",
            headers=self.headers_admin,
            json={"module_ids": [disc_id, disc_id, disc_id]}
        )
        self.assertEqual(res.status_code, 200)
        assigned = res.get_json()["assigned_module_ids"]
        self.assertEqual(assigned, [disc_id])

        # Verify DB has exactly 1 row
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_module_permission WHERE user_id = %s;", (self.restricted_id,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(count, 1)

    def test_10_disabled_module_is_not_returned(self):
        """9. Deactivated module is not returned in user modules or admin assignable list."""
        conn = get_connection()
        cur = conn.cursor()

        # Temporarily deactivate Career module
        cur.execute("UPDATE module_master SET is_active = FALSE WHERE module_code = 'career';")
        conn.commit()
        cur.close()
        conn.close()

        try:
            # Neha had career, but it's now inactive
            res = self.app.get("/api/me/modules", headers=self.headers_neha)
            codes = [m["module_code"] for m in res.get_json()["modules"]]
            self.assertNotIn("career", codes)

            # Admin assignable list does not show inactive module
            res_admin = self.app.get("/api/admin/modules", headers=self.headers_admin)
            admin_codes = [m["module_code"] for m in res_admin.get_json()["modules"]]
            self.assertNotIn("career", admin_codes)
        finally:
            # Restore active status
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE module_master SET is_active = TRUE WHERE module_code = 'career';")
            conn.commit()
            cur.close()
            conn.close()

    def test_11_user_cannot_change_own_permissions(self):
        """10. Non-admin user cannot change their own permissions."""
        disc_id = self.module_map["discipline"]
        career_id = self.module_map["career"]

        res = self.app.put(
            f"/api/admin/users/{self.ayush_id}/modules",
            headers=self.headers_ayush,
            json={"module_ids": [disc_id, career_id]}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Admin access required", res.get_json().get("error", ""))

    def test_12_non_admin_cannot_change_another_user_permissions(self):
        """11. Non-admin user cannot change another user's permissions."""
        disc_id = self.module_map["discipline"]
        career_id = self.module_map["career"]

        res = self.app.put(
            f"/api/admin/users/{self.neha_id}/modules",
            headers=self.headers_ayush,
            json={"module_ids": [disc_id, career_id]}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Admin access required", res.get_json().get("error", ""))

    def test_13_existing_login_and_auth_continues_working(self):
        """12. Existing login endpoints and profile retrieval work smoothly."""
        res_login = self.app.post("/api/auth/login", json={"username": "ayush", "password": "ayush123"})
        self.assertEqual(res_login.status_code, 200)
        token = res_login.get_json()["token"]

        res_profile = self.app.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_profile.status_code, 200)
        self.assertEqual(res_profile.get_json()["user"]["username"], "ayush")

    def test_14_admin_module_never_assignable_to_normal_user(self):
        """Admin module can never be assigned via PUT /api/admin/users/<id>/modules."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM module_master WHERE module_code = 'admin';")
        admin_mod_row = cur.fetchone()
        cur.close()
        conn.close()

        if admin_mod_row:
            admin_mod_id = admin_mod_row[0]
            # Try to assign admin module to Ayush
            res = self.app.put(
                f"/api/admin/users/{self.ayush_id}/modules",
                headers=self.headers_admin,
                json={"module_ids": [admin_mod_id]}
            )
            self.assertEqual(res.status_code, 200)
            assigned = res.get_json()["assigned_module_ids"]
            self.assertNotIn(admin_mod_id, assigned)

            # Verify Ayush still cannot access Admin
            res_admin_access = self.app.get("/api/admin/users", headers=self.headers_ayush)
            self.assertEqual(res_admin_access.status_code, 403)

if __name__ == '__main__':
    unittest.main()
