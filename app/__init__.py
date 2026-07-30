from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db
from .routes import api
from .schema import ensure_runtime_schema


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config.from_prefixed_env()

    if config_name == "testing":
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            WTF_CSRF_ENABLED=False,
            COOKIE_SECURE=False,
        )
    elif config_name == "production":
        app.config["COOKIE_SECURE"] = True

    db.init_app(app)

    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["1000 per day", "200 per hour"],
        storage_uri="memory://",
    )
    app.extensions['limiter'] = limiter

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}},
        supports_credentials=True,
    )
    app.register_blueprint(api, url_prefix="/api/v1")

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return {"error": e.description}, e.code or 500
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        return {"error": str(e) if app.config.get("DEBUG") or app.config.get("TESTING") else "Internal Server Error"}, 500

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "pravaron-careers-api"}

    register_cli(app)
    with app.app_context():
        db.create_all()
        ensure_runtime_schema()
        if not app.config.get("TESTING"):
            from .auth import normalize_email
            from .job_catalog import upsert_job_catalog
            from .models import User

            catalog_owner_email = app.config.get("CAREERS_CATALOG_OWNER_EMAIL") or app.config["EMAIL_FROM_ADDRESS"]
            admin = User.query.filter_by(email=normalize_email(catalog_owner_email)).first()
            upsert_job_catalog(admin)
            db.session.commit()
    return app


def register_cli(app: Flask) -> None:
    from .seed import seed_dev_data

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            db.create_all()
        print("Database initialized.")

    @app.cli.command("seed-dev")
    def seed_dev():
        with app.app_context():
            db.create_all()
            seed_dev_data()
        print("Development data seeded.")
