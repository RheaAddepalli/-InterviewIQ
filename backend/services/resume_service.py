import json
import re
import fitz  # PyMuPDF
from pathlib import Path
from backend.prompts.prompts import RESUME_PARSE_PROMPT
from backend.services.llm_service import call_llm_json


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a resume PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def extract_text_from_txt(txt_path: str) -> str:
    return Path(txt_path).read_text(encoding="utf-8", errors="ignore")


async def parse_resume(file_path: str) -> dict:
    """
    Main entry point.
    1. Extract raw text from PDF/TXT
    2. Call LLM to extract structured fields
    3. Return structured dict
    """
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        raw_text = extract_text_from_pdf(file_path)
    else:
        raw_text = extract_text_from_txt(file_path)

    # Trim to avoid context overflow (keep first ~4000 chars — enough for most resumes)
    raw_text_trimmed = raw_text[:4000]

    prompt = RESUME_PARSE_PROMPT.format(resume_text=raw_text_trimmed)
    parsed = await call_llm_json(prompt)
    print("RAW TEXT LENGTH =", len(raw_text))
    print("TRIMMED LENGTH =", len(raw_text_trimmed))
    print("PROMPT LENGTH =", len(prompt))

    # Ensure all required keys exist with defaults
    defaults = {
        "candidate_name": "",
        "experience_level": "mid",
        "skills": [],
        "technologies": [],
        "domains": [],
        "years_of_experience": 0,
        "education": "",
        "notable_projects": [],
    }
    result = {**defaults, **parsed}
    result["raw_text"] = raw_text

    return result
