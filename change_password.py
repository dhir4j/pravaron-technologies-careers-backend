#!/usr/bin/env python3
"""
Script to change user password.
Usage: python change_password.py
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app import create_app
from app.auth import hash_password, normalize_email
from app.models import User
from app.extensions import db


def change_password(email: str, new_password: str):
    """Change password for a user."""
    app = create_app()

    with app.app_context():
        user = User.query.filter_by(email=normalize_email(email)).first()

        if not user:
            print(f"❌ User not found: {email}")
            return False

        # Update password
        user.password_hash = hash_password(new_password)
        db.session.commit()

        print(f"✅ Password changed successfully for: {email}")
        print(f"   New password: {new_password}")
        print(f"   User: {user.full_name}")
        print(f"   Role: {user.role}")
        return True


if __name__ == "__main__":
    # Change password for jayeshbutiya2008@gmail.com
    email = "jayeshbutiya2008@gmail.com"
    new_password = "test@123"

    print("=" * 60)
    print("Password Change Script")
    print("=" * 60)
    print(f"\n📧 Email: {email}")
    print(f"🔑 New Password: {new_password}\n")

    success = change_password(email, new_password)

    if success:
        print("\n✅ Password change successful!")
        print(f"\nYou can now login with:")
        print(f"  Email: {email}")
        print(f"  Password: {new_password}")
    else:
        print("\n❌ Password change failed!")
        print("User might not exist in the database.")

    print("\n" + "=" * 60)
