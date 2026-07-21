from __future__ import annotations

import getpass
import os
from pathlib import Path

from app import create_app
from app.auth import normalize_email, verify_password
from app.models import User


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env_file(Path.home() / "mysite" / ".env")
    load_env_file(Path.home() / ".env")
    load_env_file(Path(".env"))

    email = normalize_email(os.getenv("ADMIN_EMAIL") or input("Admin email: "))
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")

    app = create_app("production")
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"NOT_FOUND: {email}")
            return 1
        if not user.is_active:
            print(f"INACTIVE: {email} role={user.role} verified={user.is_verified}")
            return 1
        if not verify_password(user.password_hash, password):
            print(f"BAD_PASSWORD: {email} role={user.role} verified={user.is_verified} active={user.is_active}")
            return 1
        print(f"OK: {email} role={user.role} verified={user.is_verified} active={user.is_active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
