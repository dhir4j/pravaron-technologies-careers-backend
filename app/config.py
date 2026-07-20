import os
from datetime import timedelta


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
