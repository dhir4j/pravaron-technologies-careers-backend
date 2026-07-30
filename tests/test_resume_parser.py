from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.resume_parser import extract_resume_text


def _two_page_pdf() -> bytes:
    writer = PdfWriter()
    for text in ("PAGE_ONE_ALPHA Python Flask", "PAGE_TWO_BETA React PostgreSQL"):
        page = writer.add_blank_page(width=360, height=180)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 40 120 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extract_resume_text_reads_all_pdf_pages():
    text, status, error = extract_resume_text("resume.pdf", _two_page_pdf(), "application/pdf")

    assert status == "extracted"
    assert error is None
    assert "PAGE_ONE_ALPHA" in text
    assert "PAGE_TWO_BETA" in text
    assert "React PostgreSQL" in text

from app.applicant_details import parse_resume_fields, resume_location_priority
from app.models import User


def test_resume_location_priority_uses_resume_text_only():
    candidate = User(email="candidate@example.com", full_name="Candidate", password_hash="x")
    parsed = parse_resume_fields(
        "Harsh Kumar\nAI ML Intern\nLocation: Bhilai, Chhattisgarh\nPython Flask React\nNotice period: Immediate",
        candidate,
        {"subject": "Application for Noida onsite role"},
    )

    assert parsed["detected_location"] == "Bhilai"
    assert parsed["location_priority"] == "Low"
    assert parsed["current_role_detected"] == "AI ML Intern"
    assert parsed["notice_period_detected"] == "Immediate"
    assert resume_location_priority("Noida") == "High"
    assert resume_location_priority(None) == "Unknown"
