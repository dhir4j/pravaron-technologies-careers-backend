from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    from app.models import EmailTemplate

    old = "careers@example.com"
    new = "careers@pravarontechnologies.com"
    app = create_app(os.getenv("APP_ENV") or "production")
    with app.app_context():
        changed = 0
        for template in EmailTemplate.query.all():
            before = (template.subject, template.html_body, template.text_body)
            template.subject = (template.subject or "").replace(old, new)
            template.html_body = (template.html_body or "").replace(old, new)
            template.text_body = (template.text_body or "").replace(old, new)
            if before != (template.subject, template.html_body, template.text_body):
                changed += 1
                db.session.add(template)
        db.session.commit()
        print(f"email_templates_updated={changed}")


if __name__ == "__main__":
    main()
