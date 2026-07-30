from __future__ import annotations

from datetime import datetime, timezone

from .extensions import db
from .models import AssessmentAttempt, AssessmentQuestion, AssessmentResponse


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def auto_grade_attempt(attempt: AssessmentAttempt) -> None:
    """Grade all auto-gradeable responses and update attempt scores."""
    total_auto_marks = 0.0
    max_auto_marks = 0.0

    for response in attempt.responses:
        question: AssessmentQuestion = response.question
        if question.question_type in ("mcq", "multi_select"):
            max_auto_marks += question.marks
            awarded = _grade_response(response, question)
            response.auto_marks = awarded
            response.is_correct = awarded >= question.marks
            total_auto_marks += awarded
        else:
            response.auto_marks = 0.0

    attempt.auto_score = total_auto_marks
    attempt.max_auto_score = max_auto_marks

    _recalculate_final_score(attempt)
    db.session.commit()


def _grade_response(response: AssessmentResponse, question: AssessmentQuestion) -> float:
    if question.correct_answer is None or response.response is None:
        return 0.0

    correct = question.correct_answer
    given = response.response

    if question.question_type == "mcq":
        correct_val = correct if isinstance(correct, str) else str(correct)
        given_val = given if isinstance(given, str) else str(given)
        return float(question.marks) if correct_val.strip().lower() == given_val.strip().lower() else 0.0

    if question.question_type == "multi_select":
        correct_set = set(str(x).strip().lower() for x in (correct if isinstance(correct, list) else [correct]))
        given_set = set(str(x).strip().lower() for x in (given if isinstance(given, list) else [given]))
        if not correct_set:
            return 0.0
        return float(question.marks) if correct_set == given_set else 0.0

    return 0.0


def _recalculate_final_score(attempt: AssessmentAttempt) -> None:
    manual = attempt.manual_score or 0.0
    auto = attempt.auto_score or 0.0
    attempt.final_score = auto + manual

    total_marks = sum(q.marks for q in attempt.assessment.questions)
    if total_marks > 0:
        attempt.percentage = round((attempt.final_score / total_marks) * 100, 1)
    else:
        attempt.percentage = 0.0

    attempt.is_passed = attempt.percentage >= (attempt.assessment.pass_score or 60)


def submit_manual_grade(attempt: AssessmentAttempt, grader_id: str, grader_notes: str | None, response_grades: list[dict]) -> None:
    """
    response_grades: [{response_id, manual_marks, reviewer_comment}]
    """
    for item in response_grades:
        response = AssessmentResponse.query.get(item.get("response_id"))
        if response and response.attempt_id == attempt.id:
            response.manual_marks = float(item.get("manual_marks", 0))
            response.reviewer_comment = item.get("reviewer_comment")
            response.reviewed_by_id = grader_id

    manual_total = sum(
        (r.manual_marks or 0.0)
        for r in attempt.responses
        if r.question.question_type in ("text", "code", "file_upload")
    )
    attempt.manual_score = manual_total
    attempt.graded_by_id = grader_id
    attempt.graded_at = _utcnow()
    attempt.grader_notes = grader_notes
    attempt.status = "graded"

    _recalculate_final_score(attempt)
    db.session.commit()


def expire_timed_out_attempts() -> int:
    """Mark in_progress attempts as timed_out if expires_at has passed. Returns count."""
    now = _utcnow()
    stale = AssessmentAttempt.query.filter(
        AssessmentAttempt.status == "in_progress",
        AssessmentAttempt.expires_at <= now,
    ).all()
    for attempt in stale:
        attempt.status = "timed_out"
        attempt.submitted_at = attempt.expires_at
        auto_grade_attempt(attempt)
    db.session.commit()
    return len(stale)
