"""
One-time migration script for LifeOS
Converts all legacy plaintext passwords in `user_master` to secure bcrypt hashes in place.
Existing passwords continue to work without any user disruption.
"""
import os
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.auth_service import migrate_all_plaintext_passwords

if __name__ == "__main__":
    print("Starting LifeOS user password migration...")
    res = migrate_all_plaintext_passwords()
    print(f"Migration completed successfully:")
    print(f"  - Total users scanned: {res['total_users']}")
    print(f"  - Passwords converted to bcrypt: {res['migrated_count']}")
    print(f"  - Already bcrypt-hashed: {res['already_hashed_count']}")
