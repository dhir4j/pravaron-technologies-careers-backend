from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.applicant_details import create_or_update_applicant_detail
from app.auth import hash_password
from app.extensions import db
from app.models import Application, ApplicationEvent, CandidateProfile, Job, Resume, User
from app.services import save_resume_bytes


ROLE_JOB_CODES = {
    "AI ML Backend Developer": "PRV-AIML-BE-INTERN",
    "Full Stack Software Developer": "PRV-FS-DEV",
    "UI UX Designer": "PRV-UIUX-DES",
}

RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMPORT_DOMAIN = "linkedin.import.pravarontechnologies.com"


def clean_name(value: str) -> str:
    value = Path(value).stem
    value = re.sub(r"^\d{1,4}-\d{6,}-", "", value)
    value = re.sub(r"^\d{1,4}-", "", value)
    value = re.sub(r"[_-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return (value or "LinkedIn Applicant")[:160]


def manifest_rows(folder: Path) -> dict[str, dict]:
    manifest = folder / "manifest.jsonl"
    rows: dict[str, dict] = {}
    if not manifest.exists():
        return rows
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = ((row.get("result") or {}).get("target") or "")
        if target:
            rows[Path(target).name] = row
        application_id = str((row.get("applicant") or {}).get("applicationId") or "").strip()
        if application_id:
            rows.setdefault(application_id, row)
    return rows


def application_id_from_file(path: Path, row: dict | None, checksum: str) -> str:
    if row:
        application_id = str((row.get("applicant") or {}).get("applicationId") or "").strip()
        if application_id:
            return application_id
    match = re.match(r"^\d{1,4}-(\d{6,})-", path.name)
    if match:
        return match.group(1)
    return f"checksum-{checksum[:24]}"


def linkedin_text(row: dict | None) -> str:
    return str(((row or {}).get("applicant") or {}).get("text") or "").strip()


def linkedin_href(row: dict | None) -> str | None:
    value = str(((row or {}).get("applicant") or {}).get("href") or "").strip()
    return value[:500] or None


def existing_linkedin_application_ids() -> set[str]:
    ids: set[str] = set()
    for application in Application.query.filter_by(source="linkedin").all():
        answers = application.answers if isinstance(application.answers, dict) else {}
        linkedin = answers.get("linkedin") if isinstance(answers, dict) else None
        if isinstance(linkedin, dict) and linkedin.get("application_id"):
            ids.add(str(linkedin["application_id"]))
    return ids


def existing_resume_checksums() -> set[str]:
    return {checksum for (checksum,) in db.session.query(Resume.checksum_sha256).all() if checksum}


def get_or_create_candidate(application_id: str, full_name: str, href: str | None) -> User:
    email = f"linkedin-{application_id.lower()}@{IMPORT_DOMAIN}"
    full_name = (full_name or "LinkedIn Applicant")[:160]
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password(hashlib.sha256(email.encode()).hexdigest() + "A1"),
            full_name=full_name,
            role="candidate",
            is_verified=True,
        )
        user.profile = CandidateProfile(extra_metadata={"source": "linkedin_import", "linkedin_application_id": application_id})
        db.session.add(user)
        db.session.flush()
    elif not user.profile:
        user.profile = CandidateProfile(extra_metadata={"source": "linkedin_import", "linkedin_application_id": application_id})
    if full_name and user.full_name != full_name:
        user.full_name = full_name
    metadata = dict(user.profile.extra_metadata or {})
    metadata.update({"source": "linkedin_import", "linkedin_application_id": application_id})
    user.profile.extra_metadata = metadata
    if href and "linkedin.com" in href:
        user.profile.linkedin_url = href
    return user


def import_resumes(root: Path, dry_run: bool = False) -> dict:
    stats = {
        "found": 0,
        "imported": 0,
        "skipped_test": 0,
        "skipped_unknown_role": 0,
        "skipped_duplicate": 0,
        "skipped_existing_application": 0,
        "errors": [],
    }
    seen_linkedin_ids = existing_linkedin_application_ids()
    seen_resume_checksums = existing_resume_checksums()
    jobs = {job.public_code: job for job in Job.query.filter(Job.public_code.in_(ROLE_JOB_CODES.values())).all()}

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        if folder.name.startswith("_"):
            stats["skipped_test"] += len([p for p in folder.iterdir() if p.suffix.lower() in RESUME_EXTENSIONS])
            continue
        job_code = ROLE_JOB_CODES.get(folder.name)
        job = jobs.get(job_code or "")
        if not job:
            stats["skipped_unknown_role"] += len([p for p in folder.iterdir() if p.suffix.lower() in RESUME_EXTENSIONS])
            continue
        rows = manifest_rows(folder)
        for path in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in RESUME_EXTENSIONS):
            stats["found"] += 1
            try:
                raw = path.read_bytes()
                checksum = hashlib.sha256(raw).hexdigest()
                row = rows.get(path.name)
                application_id = application_id_from_file(path, row, checksum)
                if application_id in seen_linkedin_ids or checksum in seen_resume_checksums:
                    stats["skipped_duplicate"] += 1
                    continue
                full_name = (str(((row or {}).get("applicant") or {}).get("name") or "").strip() or clean_name(path.name))[:160]
                if dry_run:
                    stats["imported"] += 1
                    seen_linkedin_ids.add(application_id)
                    continue
                candidate = get_or_create_candidate(application_id, full_name, linkedin_href(row))
                existing = Application.query.filter_by(candidate_id=candidate.id, job_id=job.id).first()
                if existing:
                    stats["skipped_existing_application"] += 1
                    seen_linkedin_ids.add(application_id)
                    continue
                resume = save_resume_bytes(candidate, path.name, raw, "application/pdf" if path.suffix.lower() == ".pdf" else None)
                application = Application(
                    candidate_id=candidate.id,
                    job_id=job.id,
                    resume_id=resume.id,
                    cover_message=linkedin_text(row) or f"Imported from LinkedIn for {folder.name}.",
                    answers={
                        "linkedin": {
                            "source": "linkedin",
                            "application_id": application_id,
                            "job_title": folder.name,
                            "job_code": job.public_code,
                            "linkedin_job_id": str(((row or {}).get("job") or {}).get("jobId") or ""),
                            "applicant_href": linkedin_href(row),
                            "applicant_text": linkedin_text(row),
                            "manifest_at": (row or {}).get("at"),
                            "original_path": str(path),
                            "checksum_sha256": checksum,
                        }
                    },
                    declarations={"accuracy": False, "privacy": False, "imported_from_linkedin": True},
                    source="linkedin",
                )
                db.session.add(application)
                db.session.flush()
                db.session.add(
                    ApplicationEvent(
                        application_id=application.id,
                        actor_id=None,
                        event_type="linkedin_imported",
                        note=f"Imported LinkedIn resume for {folder.name}.",
                        visible_to_candidate=False,
                    )
                )
                create_or_update_applicant_detail(application)
                db.session.commit()
                seen_linkedin_ids.add(application_id)
                seen_resume_checksums.add(checksum)
                stats["imported"] += 1
            except Exception as exc:
                db.session.rollback()
                stats["errors"].append({"file": str(path), "error": str(exc)[:300]})
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import LinkedIn applicant resumes into the careers backend.")
    parser.add_argument("root", type=Path, help="Root folder containing role-specific resume folders.")
    parser.add_argument("--dry-run", action="store_true", help="Count importable files without writing to the database.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = import_resumes(args.root, dry_run=args.dry_run)
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
