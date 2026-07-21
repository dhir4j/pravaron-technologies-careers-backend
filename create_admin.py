from __future__ import annotations

import argparse
import getpass
import os
import sys

from app import create_app
from app.auth import ADMIN_ROLES, hash_password, normalize_email, password_is_valid
from app.extensions import db
from app.models import User


def prompt_value(label: str, env_key: str, *, secret: bool = False) -> str:
    value = os.getenv(env_key)
    if value:
        return value.strip()
    prompt = f"{label}: "
    return (getpass.getpass(prompt) if secret else input(prompt)).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a Pravaron Careers admin user.")
    parser.add_argument("--email", help="Admin email. Defaults to ADMIN_EMAIL or an interactive prompt.")
    parser.add_argument("--full-name", help="Admin full name. Defaults to ADMIN_FULL_NAME or the email local part.")
    parser.add_argument(
        "--role",
        default=os.getenv("ADMIN_ROLE", "super_admin"),
        choices=sorted(ADMIN_ROLES),
        help="Admin role to assign.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update role/name/password if the user already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    email = normalize_email(args.email or prompt_value("Admin email", "ADMIN_EMAIL"))
    if not email:
        print("Admin email is required.", file=sys.stderr)
        return 2

    password = prompt_value("Admin password", "ADMIN_PASSWORD", secret=True)
    confirm = os.getenv("ADMIN_PASSWORD") or prompt_value("Confirm admin password", "ADMIN_PASSWORD_CONFIRM", secret=True)
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if not password_is_valid(password):
        print("Password must be at least 8 characters and include a letter and a number.", file=sys.stderr)
        return 2

    full_name = (
        args.full_name
        or os.getenv("ADMIN_FULL_NAME")
        or email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    )

    app = create_app("production")
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(email=email).first()
        if user:
            if not args.update_existing:
                print(f"Admin already exists: {email}. Use --update-existing to reset it.", file=sys.stderr)
                return 1
            user.password_hash = hash_password(password)
            user.full_name = full_name
            user.role = args.role
            user.is_verified = True
            user.is_active = True
            action = "updated"
        else:
            user = User(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=args.role,
                is_verified=True,
                is_active=True,
            )
            db.session.add(user)
            action = "created"
        db.session.commit()
    print(f"Admin {action}: {email} ({args.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
