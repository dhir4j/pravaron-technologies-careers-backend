from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import db
from .routes import api


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
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}},
        supports_credentials=True,
    )
    app.register_blueprint(api, url_prefix="/api/v1")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "pravaron-careers-api"}

    register_cli(app)
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

