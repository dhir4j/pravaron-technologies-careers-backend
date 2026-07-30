from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime

from flask import current_app

from .extensions import db
from .models import AIInterview, AIInterviewQuestion, AIInterviewQuestionTemplate, AIInterviewResponse, utcnow

MCQ_CONFIG = {
    "round": 1,
    "format": "mcq",
    "total_questions": 30,
    "time_limit_minutes": 60,
    "composition": {"aptitude": 12, "gk": 6, "technical": 12},
    "common_question_percent": 60,
    "technical_question_percent": 40,
    "camera_required": True,
    "proctoring_required": True,
}

COMMON_APTITUDE = [
    ("A project task takes 8 people 12 days. If 4 more people join with the same efficiency, how many days should it take?", ["6 days", "8 days", "10 days", "12 days"], "8 days"),
    ("A number is increased by 20% and then decreased by 20%. What is the net change?", ["No change", "4% decrease", "4% increase", "2% decrease"], "4% decrease"),
    ("If the ratio of two numbers is 3:5 and their sum is 64, what is the larger number?", ["24", "32", "40", "48"], "40"),
    ("A train covers 180 km in 3 hours. What is its average speed?", ["45 km/h", "50 km/h", "55 km/h", "60 km/h"], "60 km/h"),
    ("Find the next term: 2, 6, 12, 20, 30, ?", ["36", "40", "42", "44"], "42"),
    ("If 15% of x is 45, what is x?", ["250", "275", "300", "350"], "300"),
    ("A shopkeeper marks an item at Rs. 1,000 and gives a 10% discount. What is the selling price?", ["Rs. 800", "Rs. 850", "Rs. 900", "Rs. 950"], "Rs. 900"),
    ("Which one is the odd one out: SQL, Python, JavaScript, React?", ["SQL", "Python", "JavaScript", "React"], "React"),
    ("If A is older than B, and B is older than C, which statement must be true?", ["A is older than C", "C is older than A", "B is oldest", "A and C are same age"], "A is older than C"),
    ("A candidate answered 18 out of 30 questions correctly. What percentage is correct?", ["50%", "55%", "60%", "65%"], "60%"),
    ("If 5 machines make 5 units in 5 minutes, how many units do 10 machines make in 10 minutes?", ["10", "15", "20", "25"], "20"),
    ("Which data interpretation step should come first?", ["Create charts", "Clean and validate data", "Write conclusions", "Ignore outliers"], "Clean and validate data"),
]

COMMON_GK = [
    ("What does API stand for in software development?", ["Application Programming Interface", "Applied Program Internet", "Automated Process Integration", "Application Protocol Index"], "Application Programming Interface"),
    ("Which Indian city is known as the National Capital Region's major technology hub near Sector 140A?", ["Noida", "Jaipur", "Kochi", "Indore"], "Noida"),
    ("Which organization maintains many open web standards used by browsers?", ["W3C", "WHO", "IMF", "FIFA"], "W3C"),
    ("What is the primary purpose of version control?", ["Track and manage code changes", "Design logos", "Compress images", "Replace testing"], "Track and manage code changes"),
    ("Which term refers to protecting systems from unauthorized access?", ["Cybersecurity", "Typography", "Animation", "Procurement"], "Cybersecurity"),
    ("In a startup engineering team, what is usually most important when reporting a blocker?", ["Clear context and impact", "Waiting silently", "Only sharing screenshots", "Changing scope without telling anyone"], "Clear context and impact"),
]

TECHNICAL_BANK = {
    "frontend": [
        ("In React, what is the main reason to use component state?", ["To store values that affect rendering", "To write CSS", "To rename files", "To deploy servers"], "To store values that affect rendering"),
        ("Which Next.js concept is used for file-system based routes in the app directory?", ["App Router", "Webpack Loader", "NPM Scope", "CSS Cascade"], "App Router"),
        ("What should a responsive layout prioritize?", ["Content readability across viewports", "Fixed desktop-only widths", "Hidden overflow everywhere", "Tiny text on mobile"], "Content readability across viewports"),
        ("Which tool is commonly used for runtime form validation with TypeScript?", ["Zod", "SQLite", "Nginx", "Pillow"], "Zod"),
        ("What does accessibility require for icon-only buttons?", ["An accessible label", "No hover state", "Random colors", "Disabled keyboard access"], "An accessible label"),
        ("Which HTTP method is most appropriate for partially updating a resource?", ["PATCH", "GET", "HEAD", "OPTIONS only"], "PATCH"),
        ("What is a good reason to use a loading skeleton?", ["Show layout while data loads", "Hide all content forever", "Avoid API calls", "Replace error handling"], "Show layout while data loads"),
        ("Which CSS layout system is best for two-dimensional page regions?", ["Grid", "Text-align", "Float only", "Letter spacing"], "Grid"),
        ("Why should frontend API calls handle non-2xx responses?", ["To show useful errors and avoid silent failure", "To disable authentication", "To skip validation", "To increase bundle size"], "To show useful errors and avoid silent failure"),
        ("What is hydration in a React/Next.js app?", ["Attaching client interactivity to server-rendered HTML", "Uploading images", "Encrypting cookies", "Formatting dates"], "Attaching client interactivity to server-rendered HTML"),
        ("Which practice helps avoid layout shift?", ["Reserve stable dimensions for media/components", "Load every asset late", "Use random sizes", "Avoid constraints"], "Reserve stable dimensions for media/components"),
        ("What should happen after a successful form save?", ["Show clear success feedback and update local UI state", "Do nothing", "Reload the browser always", "Erase all fields without confirmation"], "Show clear success feedback and update local UI state"),
    ],
    "ui_ux": [
        ("What is the purpose of a user flow?", ["Map steps a user takes to complete a goal", "Choose only colors", "Export images", "Write backend APIs"], "Map steps a user takes to complete a goal"),
        ("Which artifact best communicates clickable behavior before development?", ["Interactive prototype", "Plain logo", "Server log", "Database dump"], "Interactive prototype"),
        ("What does visual hierarchy help users do?", ["Understand importance and order", "Ignore key actions", "Add random decoration", "Hide errors"], "Understand importance and order"),
        ("Which is a strong dashboard design principle?", ["Dense but scannable information", "Oversized marketing hero on every page", "No table labels", "One color for every state"], "Dense but scannable information"),
        ("Why are empty states important?", ["They explain what happens next", "They replace all content", "They hide product limits", "They remove navigation"], "They explain what happens next"),
        ("What is a design system primarily for?", ["Reusable, consistent product decisions", "One-off decoration", "Backend encryption", "Database migration"], "Reusable, consistent product decisions"),
        ("Which accessibility concern matters for text on backgrounds?", ["Contrast", "File size only", "Border radius only", "Animation duration only"], "Contrast"),
        ("What should a developer handoff include?", ["States, spacing, assets, behavior, and constraints", "Only a screenshot", "Only a color name", "No edge cases"], "States, spacing, assets, behavior, and constraints"),
        ("Which method helps validate usability?", ["Observing representative users complete tasks", "Guessing from aesthetics only", "Removing labels", "Changing UI randomly"], "Observing representative users complete tasks"),
        ("What is the best way to handle complex forms?", ["Group related fields and show validation clearly", "Put every input in one long block", "Hide required fields", "Use unclear labels"], "Group related fields and show validation clearly"),
        ("What makes a product interface trustworthy?", ["Consistency, feedback, and clear affordances", "Surprise controls", "Invisible actions", "Decorative noise"], "Consistency, feedback, and clear affordances"),
        ("Why inspect implementation after design handoff?", ["To catch spacing, state, and responsiveness issues", "To avoid collaboration", "To skip testing", "To remove documentation"], "To catch spacing, state, and responsiveness issues"),
    ],
    "full_stack": [
        ("What is the purpose of REST API status codes?", ["Communicate request outcome", "Style web pages", "Store passwords", "Bundle frontend code"], "Communicate request outcome"),
        ("Which database concept prevents duplicate candidate-job applications?", ["Unique constraint", "CSS variable", "Media query", "SVG path"], "Unique constraint"),
        ("Why use server-side validation?", ["Clients can be bypassed", "It makes CSS faster", "It removes testing", "It replaces authentication"], "Clients can be bypassed"),
        ("Which is a secure way to store session tokens in a browser app?", ["HttpOnly cookie", "Plain local text file", "Console log", "URL query forever"], "HttpOnly cookie"),
        ("What does an ORM like SQLAlchemy help with?", ["Mapping database rows to application models", "Recording audio", "Drawing icons", "Compressing CSS"], "Mapping database rows to application models"),
        ("What should happen when an API dependency fails?", ["Return a controlled error and log context", "Crash silently", "Expose secrets", "Delete data"], "Return a controlled error and log context"),
        ("Why are database migrations important?", ["They evolve schema without wiping data", "They replace source control", "They avoid backups", "They only change CSS"], "They evolve schema without wiping data"),
        ("Which React pattern helps keep UI consistent across pages?", ["Reusable components", "Copy-paste every screen", "Inline random styles only", "No state management"], "Reusable components"),
        ("What is CORS used for?", ["Controlling cross-origin browser requests", "Hashing passwords", "Generating resumes", "Running SQL queries"], "Controlling cross-origin browser requests"),
        ("Which log is most useful for debugging production issues?", ["Action, entity id, actor, timestamp, context", "Only random emojis", "No timestamp", "Only success messages"], "Action, entity id, actor, timestamp, context"),
        ("What should be included in a pull request for risky changes?", ["Tests and behavior summary", "No explanation", "Only screenshots", "Unrelated refactors"], "Tests and behavior summary"),
        ("What is idempotency useful for?", ["Avoiding duplicate effects when requests retry", "Changing colors", "Breaking authentication", "Skipping validation"], "Avoiding duplicate effects when requests retry"),
    ],
    "ai_ml": [
        ("What is overfitting in machine learning?", ["A model performs well on training data but poorly on new data", "A database index", "A UI animation", "A network timeout"], "A model performs well on training data but poorly on new data"),
        ("What is the purpose of a validation set?", ["Estimate model performance during development", "Store passwords", "Render pages", "Compress videos"], "Estimate model performance during development"),
        ("What does RAG stand for in AI systems?", ["Retrieval-Augmented Generation", "Random API Gateway", "React App Generator", "Relational Access Graph"], "Retrieval-Augmented Generation"),
        ("Why are embeddings useful?", ["They represent semantic meaning for search/comparison", "They replace all databases", "They secure passwords", "They style buttons"], "They represent semantic meaning for search/comparison"),
        ("Which metric is commonly used for classification?", ["Precision", "Border radius", "Frame rate", "HTTP port"], "Precision"),
        ("What should you do when an LLM answer may be hallucinated?", ["Verify against reliable source data", "Trust it blindly", "Remove logs", "Increase font size"], "Verify against reliable source data"),
        ("What is data leakage?", ["Training with information that would not be available at prediction time", "A CSS overflow", "A browser reload", "A resume upload"], "Training with information that would not be available at prediction time"),
        ("Why use structured JSON outputs from an LLM?", ["Reliable parsing and downstream automation", "More decoration", "Less validation", "No schema needed"], "Reliable parsing and downstream automation"),
        ("What does a vector database typically store?", ["Embeddings and metadata", "Only CSS files", "Keyboard shortcuts", "Email passwords"], "Embeddings and metadata"),
        ("Which Python library is commonly used for tabular data processing?", ["Pandas", "React", "Tailwind", "Lucide"], "Pandas"),
        ("What is prompt evaluation used for?", ["Testing output quality across cases", "Changing monitor brightness", "Deleting logs", "Creating cookies"], "Testing output quality across cases"),
        ("Why should AI decisions in hiring stay human-reviewed?", ["To keep accountability and reduce unfair automated decisions", "To remove evidence", "To rank by appearance", "To avoid notes"], "To keep accountability and reduce unfair automated decisions"),
    ],
}


def _job_for_interview(interview: AIInterview):
    app = interview.application if hasattr(interview, "application") else None
    return app.job if app and hasattr(app, "job") else None


def _template_item(template: AIInterviewQuestionTemplate) -> tuple[str, list[str], str] | None:
    options = [str(option).strip() for option in (template.options or []) if str(option).strip()]
    answer = str(template.correct_answer or "").strip()
    content = str(template.content or "").strip()
    if not content or len(options) < 2 or answer not in options:
        return None
    return (content, options[:4], answer)


def _job_template_items(interview: AIInterview, role: str) -> dict[str, list[tuple[str, list[str], str]]]:
    job = _job_for_interview(interview)
    grouped: dict[str, list[tuple[str, list[str], str]]] = {"aptitude": [], "gk": [], "technical": []}
    if not job:
        return grouped
    templates = AIInterviewQuestionTemplate.query.filter_by(job_id=job.id, mode="mcq", is_active=True).order_by(AIInterviewQuestionTemplate.order.asc(), AIInterviewQuestionTemplate.created_at.asc()).all()
    for template in templates:
        category = template.category if template.category in grouped else "technical"
        item = _template_item(template)
        if item:
            grouped[category].append(item)
    return grouped


def _merge_question_items(custom_items: list[tuple[str, list[str], str]], fallback_items: list[tuple[str, list[str], str]], limit: int) -> list[tuple[str, list[str], str]]:
    merged: list[tuple[str, list[str], str]] = []
    seen: set[str] = set()
    for item in [*custom_items, *fallback_items]:
        key = item[0].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged

def _role_family(interview: AIInterview) -> str:
    app = interview.application if hasattr(interview, "application") else None
    job = app.job if app and hasattr(app, "job") else None
    metadata = job.source_metadata if job and isinstance(job.source_metadata, dict) else {}
    family = str(metadata.get("role_family") or "").lower()
    title = str(job.title if job else "").lower()
    if "ui" in family or "design" in title or "ux" in title:
        return "ui_ux"
    if "front" in family or "frontend" in title:
        return "frontend"
    if "full" in family or "full-stack" in title or "software developer" in title:
        return "full_stack"
    if "ai" in family or "ml" in family or "ai/ml" in title or "backend intern" in title:
        return "ai_ml"
    return "full_stack"


def _make_question(interview: AIInterview, order: int, category: str, item: tuple[str, list[str], str]) -> AIInterviewQuestion:
    content, options, answer = item
    return AIInterviewQuestion(
        interview_id=interview.id,
        order=order,
        question_type=category,
        category=category,
        content=content,
        options=options,
        correct_answer=answer,
        marks=1,
        context="Round 1 MCQ: 40% aptitude, 20% GK, 40% role-based technical.",
        asked_at=None,
    )


def generate_opening_questions(interview: AIInterview) -> list[AIInterviewQuestion]:
    """Generate the fixed 30-question first-round MCQ interview."""
    existing = list(interview.questions or [])
    existing_is_valid = len(existing) == MCQ_CONFIG["total_questions"] and all(q.options and q.correct_answer for q in existing)
    if existing_is_valid:
        return existing
    if existing and interview.responses:
        return existing
    for question in existing:
        db.session.delete(question)
    if existing:
        db.session.flush()

    role = _role_family(interview)
    technical = TECHNICAL_BANK.get(role, TECHNICAL_BANK["full_stack"])
    custom = _job_template_items(interview, role)
    aptitude_items = _merge_question_items(custom["aptitude"], COMMON_APTITUDE, MCQ_CONFIG["composition"]["aptitude"])
    gk_items = _merge_question_items(custom["gk"], COMMON_GK, MCQ_CONFIG["composition"]["gk"])
    technical_items = _merge_question_items(custom["technical"], technical, MCQ_CONFIG["composition"]["technical"])
    items = [("aptitude", item) for item in aptitude_items]
    items.extend(("gk", item) for item in gk_items)
    items.extend(("technical", item) for item in technical_items)

    existing_config = dict(interview.mcq_config or {})
    interview.mcq_config = dict(
        MCQ_CONFIG,
        access_code=existing_config.get("access_code"),
        role_family=role,
        source_counts={
            "aptitude_custom": min(len(custom["aptitude"]), MCQ_CONFIG["composition"]["aptitude"]),
            "gk_custom": min(len(custom["gk"]), MCQ_CONFIG["composition"]["gk"]),
            "technical_custom": min(len(custom["technical"]), MCQ_CONFIG["composition"]["technical"]),
        },
    )
    interview.proctoring_summary = interview.proctoring_summary or {
        "tab_switches": 0,
        "focus_losses": 0,
        "fullscreen_exits": 0,
        "copy_paste_events": 0,
        "face_not_detected": 0,
        "multiple_faces": 0,
        "mobile_detected": 0,
        "camera_disabled": 0,
        "look_away": 0,
        "suspicious_total": 0,
    }

    saved: list[AIInterviewQuestion] = []
    for idx, (category, item) in enumerate(items[:30], start=1):
        question = _make_question(interview, idx, category, item)
        db.session.add(question)
        saved.append(question)
    db.session.flush()
    return saved


def generate_followup_question(interview: AIInterview, last_question: AIInterviewQuestion, last_response: AIInterviewResponse) -> AIInterviewQuestion | None:
    return None


def _call_deepseek(messages: list[dict], max_tokens: int = 1200) -> dict:
    api_key = current_app.config["DEEPSEEK_API_KEY"]
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")
    body = {
        "model": current_app.config["DEEPSEEK_MODEL"],
        "messages": messages,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{current_app.config['DEEPSEEK_API_BASE_URL']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=current_app.config.get("DEEPSEEK_ANALYSIS_TIMEOUT_SECONDS", 60)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {exc.code}: {error_body[:500]}") from exc
    content = (data["choices"][0]["message"].get("content") or "{}").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _score_breakdown(interview: AIInterview) -> dict:
    questions = list(interview.questions or [])
    responses_by_question = {r.question_id: r for r in interview.responses}
    breakdown: dict[str, dict[str, int]] = {
        "aptitude": {"correct": 0, "total": 0},
        "gk": {"correct": 0, "total": 0},
        "technical": {"correct": 0, "total": 0},
    }
    for question in questions:
        category = question.category or question.question_type or "technical"
        if category not in breakdown:
            breakdown[category] = {"correct": 0, "total": 0}
        breakdown[category]["total"] += 1
        response = responses_by_question.get(question.id)
        is_correct = bool(response and response.response_text == question.correct_answer)
        if response:
            response.is_correct = is_correct
        if is_correct:
            breakdown[category]["correct"] += 1
    total_correct = sum(item["correct"] for item in breakdown.values())
    total_questions = sum(item["total"] for item in breakdown.values()) or 1
    return {
        "breakdown": breakdown,
        "correct": total_correct,
        "total": total_questions,
        "percentage": round(total_correct / total_questions * 100, 1),
    }


def generate_interview_summary(interview: AIInterview) -> dict:
    scoring = _score_breakdown(interview)
    proctoring = interview.proctoring_summary or {}
    suspicious_total = int(proctoring.get("suspicious_total") or 0)
    high_flags = len([event for event in (interview.security_events or []) if event.get("severity") == "high"])
    medium_flags = len([event for event in (interview.security_events or []) if event.get("severity") == "medium"])
    raw_percentage = scoring["percentage"]
    answered = len([response for response in interview.responses if response.response_text])
    completion_rate = round((answered / max(scoring["total"], 1)) * 100, 1)
    security_penalty = min(30.0, (high_flags * 4.0) + (medium_flags * 2.0) + max(0, suspicious_total - (high_flags * 4) - (medium_flags * 2)) * 0.7)
    final_percentage = round(max(0.0, raw_percentage - security_penalty), 1)
    security_score = round(max(0.0, 10 - (security_penalty / 3)), 1)

    if final_percentage >= 75 and high_flags <= 1:
        recommendation = "Proceed"
    elif final_percentage >= 55 and high_flags <= 3:
        recommendation = "Hold"
    else:
        recommendation = "Reject"

    concerns: list[str] = []
    if completion_rate < 100:
        concerns.append(f"Only {completion_rate}% of the interview was answered.")
    if suspicious_total:
        concerns.append(f"Review {suspicious_total} weighted security flag points before deciding.")
    if high_flags:
        concerns.append(f"{high_flags} high-severity proctoring event(s) need human review.")

    summary = {
        "overall": f"Candidate answered {scoring['correct']} of {scoring['total']} MCQ questions correctly ({raw_percentage}%). After a {security_penalty:g}-point security penalty, the final interview score is {final_percentage}/100.",
        "recommendation_rationale": "Final score combines objective MCQ marks, completion, and human-reviewable proctoring flags. Hiring decisions remain human-controlled.",
        "strengths": [f"Raw MCQ score: {raw_percentage}%", f"Completion rate: {completion_rate}%"],
        "concerns": concerns,
        "score_breakdown": scoring["breakdown"],
        "proctoring_summary": proctoring,
        "security_penalty": security_penalty,
        "completion_rate": completion_rate,
        "raw_percentage": raw_percentage,
        "final_percentage": final_percentage,
    }
    scores = {
        "aptitude": round((scoring["breakdown"].get("aptitude", {}).get("correct", 0) / max(scoring["breakdown"].get("aptitude", {}).get("total", 1), 1)) * 10, 1),
        "gk": round((scoring["breakdown"].get("gk", {}).get("correct", 0) / max(scoring["breakdown"].get("gk", {}).get("total", 1), 1)) * 10, 1),
        "technical": round((scoring["breakdown"].get("technical", {}).get("correct", 0) / max(scoring["breakdown"].get("technical", {}).get("total", 1), 1)) * 10, 1),
        "raw_overall": round(raw_percentage / 10, 1),
        "security": security_score,
        "overall": round(final_percentage / 10, 1),
        "score_out_of_100": final_percentage,
        "security_penalty": security_penalty,
        "completion_rate": completion_rate,
    }
    interview.ai_summary = summary
    interview.ai_scores = scores
    interview.recommendation = recommendation
    interview.status = "completed"
    interview.completed_at = utcnow()
    db.session.flush()
    return {"summary": summary, "scores": scores, "recommendation": recommendation}





