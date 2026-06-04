"""
evaluator.py
Single responsibility: take a question + answer, return rubric evaluation.
Nothing else. No retrieval. No session logic. No routing.

The agent consumes this. Routes never calls this directly.
"""
from dataclasses import dataclass
from typing import List

from backend.prompts.prompts import ANSWER_EVALUATION_PROMPT
from backend.services.llm_service import call_llm_json


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class EvaluationResult:
    rubric_level: int           # 1-5
    performance: str            # weak | adequate | strong
    reasoning: str              # one sentence
    topics_demonstrated: List[str]
    gaps_detected: List[str]

    def is_weak(self) -> bool:
        return self.performance == "weak"

    def is_strong(self) -> bool:
        return self.performance == "strong"

    def is_adequate(self) -> bool:
        return self.performance == "adequate"

    def to_dict(self) -> dict:
        return {
            "rubric_level":        self.rubric_level,
            "performance":         self.performance,
            "reasoning":           self.reasoning,
            "topics_demonstrated": self.topics_demonstrated,
            "gaps_detected":       self.gaps_detected,
        }


# ============================================================
# MAIN EVALUATION FUNCTION
# ============================================================

async def evaluate_answer(
    question: str,
    answer: str,
    role: str,
) -> EvaluationResult:
    """
    Evaluate a candidate's answer using rubric-based LLM scoring.

    Returns EvaluationResult with:
    - rubric_level (1-5)
    - performance (weak | adequate | strong)
    - reasoning
    - topics_demonstrated
    - gaps_detected
    """

    # Handle empty / very short answers immediately — no LLM call needed
    clean_answer = answer.strip()

    words = clean_answer.split()

    # ============================================================
    # Reject extremely short / gibberish answers immediately
    # ============================================================

    if (
        not clean_answer
        or len(words) < 8
    ):

        return EvaluationResult(
            rubric_level=1,
            performance="weak",
            reasoning="Answer was too short to demonstrate understanding.",
            topics_demonstrated=[],
            gaps_detected=["No substantive response provided"],
        )

    # ============================================================
    # Detect gibberish / keyboard spam
    # ============================================================

    alpha_ratio = (
        sum(c.isalpha() for c in clean_answer)
        / max(len(clean_answer), 1)
    )

    unique_words = len(set(words))

    if (
        alpha_ratio < 0.6
        or unique_words <= 2
    ):

        return EvaluationResult(
            rubric_level=1,
            performance="weak",
            reasoning="Answer appeared irrelevant or nonsensical.",
            topics_demonstrated=[],
            gaps_detected=["Irrelevant or gibberish response"],
        )

    prompt = ANSWER_EVALUATION_PROMPT.format(
        role=role,
        question=question,
        answer=clean_answer,
    )

    raw = await call_llm_json(prompt, temperature=0.0)

    # ── Parse and validate ───────────────────────────────────────
    rubric_level = int(raw.get("rubric_level", 2))
    rubric_level = max(1, min(5, rubric_level))   # clamp to 1-5

    # Derive performance from rubric level if LLM didn't return it cleanly
    performance = raw.get("performance", "")
    if performance not in ("weak", "adequate", "strong"):
        if rubric_level <= 2:
            performance = "weak"
        elif rubric_level == 3:
            performance = "adequate"
        else:
            performance = "strong"

    return EvaluationResult(
        rubric_level=rubric_level,
        performance=performance,
        reasoning=raw.get("reasoning", ""),
        topics_demonstrated=raw.get("topics_demonstrated", []),
        gaps_detected=raw.get("gaps_detected", []),
    )
