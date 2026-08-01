from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path, *, override: bool = True) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def configure_pythonanywhere_env() -> None:
    home = Path.home()
    load_env(home / "mysite" / ".env", override=True)
    load_env(home / ".env", override=False)
    os.environ.setdefault("APP_ENV", "production")
    os.environ.setdefault("COOKIE_SECURE", "true")


def main() -> None:
    configure_pythonanywhere_env()

    from app import create_app
    from app.extensions import db
    from app.models import Application, EmailTemplate
    from app.routes import DECISION_EMAIL_DEFAULTS, _decision_email_content

    app = create_app(os.getenv("APP_ENV") or "production")
    with app.app_context():
        for config in DECISION_EMAIL_DEFAULTS.values():
            key = config["template_key"]
            template = EmailTemplate.query.filter_by(key=key).first() or EmailTemplate(key=key, version=0)
            template.subject = config["subject"]
            template.html_body = config["html_body"]
            template.text_body = config["text_body"]
            template.version = (template.version or 0) + 1
            template.is_active = True
            db.session.add(template)
        db.session.commit()

        application = Application.query.order_by(Application.created_at.desc()).first()
        if application:
            for status in DECISION_EMAIL_DEFAULTS:
                with app.test_request_context("/api/v1/admin/applications/preview"):
                    email = _decision_email_content(application, status)
                combined = "\n".join([email["subject"], email["text_body"], email["html_body"]])
                if "{{" in combined or "}}" in combined:
                    raise RuntimeError(f"Unrendered variables remain in {status} preview")
                if not email["to_email"]:
                    raise RuntimeError(f"Missing recipient in {status} preview")

        print("decision_templates_upserted")


if __name__ == "__main__":
    main()
