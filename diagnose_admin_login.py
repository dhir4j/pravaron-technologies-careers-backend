from __future__ import annotations

import getpass
import json
import os
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

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


def http_login(url: str, email: str, password: str) -> tuple[int, str, bool]:
    body = json.dumps({"email": email, "password": password}).encode()
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Origin": "https://careers.pravarontechnologies.com"},
        method="POST",
    )
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    try:
        response = opener.open(request, timeout=20)
        content = response.read().decode("utf-8", errors="replace")
        cookies = response.headers.get_all("Set-Cookie") or []
        return response.status, content, any("access_token=" in cookie for cookie in cookies)
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace"), False
    except URLError as error:
        return 0, str(error.reason), False


def print_result(label: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"{label}: {status} - {detail}")


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
            print_result("database user", False, f"{email} not found")
            return 1
        print_result(
            "database user",
            user.is_active and user.is_verified and verify_password(user.password_hash, password),
            f"role={user.role} verified={user.is_verified} active={user.is_active}",
        )

    client = app.test_client()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    print_result(
        "flask in-process login",
        response.status_code == 200,
        f"status={response.status_code} body={response.get_data(as_text=True).strip()}",
    )

    for label, url in [
        ("pythonanywhere http login", "http://server2careers.pravarontechnologies.com/api/v1/auth/login"),
        ("careers-domain proxy login", "https://careers.pravarontechnologies.com/api/v1/auth/login"),
    ]:
        status, body, set_cookie = http_login(url, email, password)
        print_result(label, status == 200 and set_cookie, f"status={status} set_cookie={set_cookie} body={body.strip()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
