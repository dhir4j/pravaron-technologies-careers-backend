from __future__ import annotations

from .extensions import db

CANDIDATE_ANALYSIS_COLUMNS = {
    "graduation_year": "INTEGER",
    "recommended_track": "VARCHAR(80)",
    "location_priority": "VARCHAR(80)",
    "detected_location": "VARCHAR(160)",
    "job_family": "VARCHAR(120)",
}

AI_INTERVIEW_COLUMNS = {
    "mcq_config": "JSON DEFAULT '{}'",
    "proctoring_summary": "JSON DEFAULT '{}'",
    "security_events": "JSON DEFAULT '[]'",
    "admin_messages": "JSON DEFAULT '[]'",
    "latest_frame_data_url": "TEXT",
    "latest_frame_at": "DATETIME",
    "recording_path": "VARCHAR(700)",
}

AI_INTERVIEW_QUESTION_COLUMNS = {
    "category": "VARCHAR(40) DEFAULT 'technical' NOT NULL",
    "options": "JSON DEFAULT '[]' NOT NULL",
    "correct_answer": "TEXT",
    "marks": "INTEGER DEFAULT 1 NOT NULL",
}

AI_INTERVIEW_RESPONSE_COLUMNS = {
    "is_correct": "BOOLEAN",
}


def _dialect_columns(columns: dict[str, str]) -> dict[str, str]:
    if db.engine.dialect.name != "postgresql":
        return columns
    replacements = {
        "JSON": "JSONB",
        "DATETIME": "TIMESTAMP WITH TIME ZONE",
    }
    adapted: dict[str, str] = {}
    for name, ddl_type in columns.items():
        for source, target in replacements.items():
            ddl_type = ddl_type.replace(source, target)
        adapted[name] = ddl_type
    return adapted


def _add_missing_columns(table_name: str, columns: dict[str, str]) -> None:
    inspector = db.inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    with db.engine.begin() as connection:
        for name, ddl_type in _dialect_columns(columns).items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl_type}")


def ensure_runtime_schema() -> None:
    _add_missing_columns("candidate_analyses", CANDIDATE_ANALYSIS_COLUMNS)
    _add_missing_columns("ai_interviews", AI_INTERVIEW_COLUMNS)
    _add_missing_columns("ai_interview_questions", AI_INTERVIEW_QUESTION_COLUMNS)
    _add_missing_columns("ai_interview_responses", AI_INTERVIEW_RESPONSE_COLUMNS)
