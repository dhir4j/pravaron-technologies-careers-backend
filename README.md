# Pravaron Technologies Careers Backend

Flask API for the Phase 1 Pravaron Technologies Careers applicant tracking system.

## Public openings feed

The main `pravarontechnologies.com` frontend should consume:

```text
GET /api/v1/public/openings
```

`/api/v1/public/openings.json` is provided as an equivalent alias. Each published
opening includes a stable public `job_id` and a direct `url` containing both the
Job ID and SEO-friendly slug. Configure
`CAREERS_PUBLIC_URL` for the deployed careers domain.

## Local Setup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app app:create_app init-db
flask --app app:create_app seed-dev
flask --app app:create_app run --debug
```

By default the API uses SQLite at `backend/instance/pravaron_careers.sqlite3`.
For production PostgreSQL, set `DATABASE_URL` in the deployment environment:

```text
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```

## Admin Users

Create admin users with `create_admin.py`. Keep production credentials in the
deployment environment only.
