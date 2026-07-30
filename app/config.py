import os
from datetime import timedelta
from pathlib import Path


def load_local_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        os.environ.setdefault(key.strip(), raw.strip().strip('"').strip("'"))


load_local_env()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///pravaron_careers.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    CAREERS_PUBLIC_URL = os.getenv(
        "CAREERS_PUBLIC_URL",
        "https://careers.pravarontechnologies.com",
    ).rstrip("/")
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            (
                "http://localhost:3000,"
                "https://careers.pravarontechnologies.com,"
                "https://pravarontechnologies.com,"
                "https://www.pravarontechnologies.com"
            ),
        ).split(",")
        if origin.strip()
    ]
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "14"))
    ACCESS_TOKEN_AGE = timedelta(minutes=ACCESS_TOKEN_MINUTES)
    REFRESH_TOKEN_AGE = timedelta(days=REFRESH_TOKEN_DAYS)

    MAX_RESUME_SIZE_MB = int(os.getenv("MAX_RESUME_SIZE_MB", "8"))
    MAX_CONTENT_LENGTH = MAX_RESUME_SIZE_MB * 1024 * 1024
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "instance/uploads")
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx", "doc"}

    EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "careers@example.com")
    EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "careers@example.com")
    CAREERS_CATALOG_OWNER_EMAIL = os.getenv("CAREERS_CATALOG_OWNER_EMAIL", EMAIL_FROM_ADDRESS)
    CAREERS_MAIL_IMAP_HOST = os.getenv("CAREERS_MAIL_IMAP_HOST", "imappro.zoho.in")
    CAREERS_MAIL_IMAP_PORT = int(os.getenv("CAREERS_MAIL_IMAP_PORT", "993"))
    CAREERS_MAIL_USERNAME = os.getenv("CAREERS_MAIL_USERNAME", EMAIL_FROM_ADDRESS)
    CAREERS_MAIL_APP_PASSWORD = os.getenv("CAREERS_MAIL_APP_PASSWORD", "")
    CAREERS_MAIL_MAILBOX = os.getenv("CAREERS_MAIL_MAILBOX", "INBOX")
    CAREERS_MAIL_FETCH_LIMIT = int(os.getenv("CAREERS_MAIL_FETCH_LIMIT", "200"))

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE_URL = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com").rstrip("/")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_ANALYSIS_MAX_RESUME_CHARS = int(os.getenv("DEEPSEEK_ANALYSIS_MAX_RESUME_CHARS", "12000"))
    DEEPSEEK_ANALYSIS_TIMEOUT_SECONDS = int(os.getenv("DEEPSEEK_ANALYSIS_TIMEOUT_SECONDS", "60"))
