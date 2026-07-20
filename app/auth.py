from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from typing import Callable

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User

ADMIN_ROLES = {"super_admin", "people_ops_admin", "hiring_manager"}
REVIEWER_ROLES = ADMIN_ROLES | {"technical_reviewer", "read_only_reviewer"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def password_is_valid(password: str) -> bool:
    return len(password) >= 8 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pravaron-careers")


def create_token(user: User, purpose: str = "access") -> str:
    return _serializer().dumps({"sub": user.id, "role": user.role, "purpose": purpose})


def load_token(token: str, purpose: str = "access") -> User | None:
    max_age = int(current_app.config["ACCESS_TOKEN_AGE"].total_seconds())
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if data.get("purpose") != purpose:
        return None
    return db.session.get(User, data.get("sub"))


def create_action_token(user: User, purpose: str) -> str:
    return _serializer().dumps({"sub": user.id, "purpose": purpose})


def load_action_token(token: str, purpose: str, max_age_seconds: int) -> User | None:
    try:
        data = _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if data.get("purpose") != purpose:
        return None
    return db.session.get(User, data.get("sub"))


def current_user() -> User | None:
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None
    user = load_token(token)
    if not user or not user.is_active:
        return None
    return user


def set_auth_cookie(response, user: User):
    token = create_token(user)
    response.set_cookie(
        "access_token",
        token,
        max_age=int(current_app.config["ACCESS_TOKEN_AGE"].total_seconds()),
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite=current_app.config["COOKIE_SAMESITE"],
        path="/",
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie("access_token", path="/")
    return response


def require_auth(fn: Callable):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_roles(*roles: str):
    allowed = set(roles)

    def decorator(fn: Callable):
        @wraps(fn)
        @require_auth
        def wrapper(*args, **kwargs):
            if g.user.role not in allowed:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_verified": user.is_verified,
    }


def mark_login(user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
