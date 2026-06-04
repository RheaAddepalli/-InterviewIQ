from typing import List
from backend.prompts.prompts import SESSION_ANALYSIS_PROMPT
from backend.services.llm_service import call_llm_json


async def generate_session_report(
    role: str,
    candidate_name: str,
    experience_level: str,
    questions_and_answers: List[dict],
) -> dict:
    """
    Takes the full Q&A transcript and returns structured analysis.
    questions_and_answers: [{"question": "...", "answer": "...", "topic": "..."}, ...]
    """
    transcript_lines = []
    for i, qa in enumerate(questions_and_answers, 1):
        transcript_lines.append(

            f"Q{i} [{qa.get('topic', '')}]: "
            f"{qa['question']}\n"

            f"A{i}: "
            f"{qa.get('answer', '(no answer given)')}\n"

            f"Rubric Level: "
            f"{qa.get('rubric_level', 'N/A')}\n"

            f"Performance: "
            f"{qa.get('performance', 'N/A')}\n"

            f"Gaps: "
            f"{', '.join(qa.get('gaps_detected', []))}\n"
        )
    transcript = "\n".join(transcript_lines)

    prompt = SESSION_ANALYSIS_PROMPT.format(
        role=role,
        candidate_name=candidate_name or "Candidate",
        experience_level=experience_level,
        transcript=transcript[:5000],
    )

    result = await call_llm_json(prompt, temperature=0.2)

    defaults = {
        "overall_assessment": "Session completed.",
        "strengths": [],
        "gaps": [],
        "topics_covered": [],
        "depth_score": 5,
        "communication_score": 5,
        "recommendation": "consider",
        "follow_up_areas": [],
    }
    return {**defaults, **result}
