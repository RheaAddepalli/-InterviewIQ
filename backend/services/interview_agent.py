"""
interview_agent.py
The brain of the interviewer. Decides strategy — does NOT retrieve or generate.

Responsibilities:
  - compute_interview_state()   → summarise what's happened so far
  - decide_strategy()           → decide topic, difficulty, type, follow-up
  - adjust_difficulty()         → based on performance history
  - should_follow_up()          → based on last eval + follow-up history
  - detect_weaknesses()         → aggregate gaps across session

Does NOT:
  - call FAISS
  - call LLM for generation
  - write to DB
  - know about HTTP
"""
from dataclasses import dataclass, field
from typing import List, Optional

from backend.prompts.prompts import STRATEGY_PROMPT
from backend.services.llm_service import call_llm_json
from backend.services.evaluator import EvaluationResult


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class QuestionRecord:
    """Lightweight record of one Q&A turn passed in from routes."""
    question_text: str
    topic: str
    difficulty: str
    question_type: str
    is_follow_up: bool
    answer_text: Optional[str]
    evaluation: Optional[EvaluationResult]   # None if not yet answered
    resume_evidence: str = ""
    concept_family: str = ""


@dataclass
class InterviewState:
    role: str
    experience_level: str
    skills: List[str]
    domains: List[str]
    projects: List[str]
    questions_asked: int
    total_questions: int
    history: List[QuestionRecord]
    current_difficulty: str = "medium"
    interview_plan: List[dict] = field(default_factory=list)
    current_plan_index: int = 0
    
@dataclass
class InterviewStrategy:
    """What the agent decided for the next question."""
    topic: str
    difficulty: str                 # easy | medium | hard
    question_type: str              # conceptual | applied | scenario | follow_up
    is_follow_up: bool
    reason: str                     # agent's one-sentence reasoning (for traceability)
    resume_evidence: str = ""
    concept_family: str = ""


# ============================================================
# AGENT
# ============================================================

class InterviewAgent:
    """
    Stateless agent — all state is passed in via InterviewState.
    Each method is a pure decision function.
    """

    # ── Public entry point ───────────────────────────────────────

    async def decide_strategy(
    self,
    state: InterviewState,
    latest_evaluation: EvaluationResult,
):
        """
        Main method called by routes each turn.
        Returns the strategy for the next question.
        """
        # First question — no history, no eval
        # ── Plan-based strategy ──────────────────────────────────
        if state.interview_plan:

            if state.history:

                last = state.history[-1]

                if self.should_follow_up(
                    last,
                    latest_evaluation
                ):
                    print("FOLLOWUP TRIGGERED")
                    print("TOPIC:", last.topic)
                    print("PERFORMANCE:", latest_evaluation.performance)
                    return self._follow_up_strategy(
                        state,
                        last,
                        latest_evaluation,
                    )

            return self._plan_based_strategy(
                state,
                latest_evaluation,
            )

        # ── Fallback: no plan, use LLM strategy ──────────────────
        if not state.history:
            return self._opening_strategy(state)

        last = state.history[-1]
        last_eval = latest_evaluation

        # If last question has no evaluation yet (shouldn't happen, but be safe)
        if last_eval is None:
            return self._opening_strategy(state)

        # Build inputs for LLM strategy call
        history_summary = self._summarise_history(state.history)
        covered_topics  = self._covered_topics(state.history)
        covered_evidence = list({
            q.resume_evidence
            for q in state.history
            if q.resume_evidence
        })

        covered_families = list({
            q.concept_family
            for q in state.history
            if q.concept_family
        })
        covered_concepts = {
            t.lower().strip()
            for t in covered_topics
        }
        last_eval_text  = self._format_eval(last_eval, last)
        coverage_summary = f"""
        Conceptual: {sum(1 for q in state.history if q.question_type == "conceptual")}
        Applied: {sum(1 for q in state.history if q.question_type == "applied")}
        Scenario: {sum(1 for q in state.history if q.question_type == "scenario")}
        Follow-up: {sum(1 for q in state.history if q.question_type == "follow_up")}
        """
        print("\n===== COVERAGE =====")
        print("EVIDENCE:", covered_evidence)
        print("FAMILIES:", covered_families)
        print("====================")
        prompt = STRATEGY_PROMPT.format(

            role=state.role,
            experience_level=state.experience_level,
            skills=", ".join(state.skills[:8]),
            domains=", ".join(state.domains[:5]),
            projects=", ".join(state.projects[:5]),
            coverage_summary=coverage_summary,
            history_summary=history_summary,resume_coverage_summary=
                ", ".join(covered_evidence) or "None yet",

            family_coverage_summary=
                ", ".join(covered_families) or "None yet",

            last_eval=last_eval_text,
            covered_topics=", ".join(covered_topics) or "None yet",
            current_difficulty=state.current_difficulty,
            questions_asked=state.questions_asked,
            total_questions=state.total_questions,
        )

        raw = await call_llm_json(prompt, temperature=0.0)

        # Validate and fall back gracefully
        if not raw or "topic" not in raw:
            return self._fallback_strategy(state)

        difficulty = raw.get("difficulty", state.current_difficulty)
        
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = state.current_difficulty

        question_type = raw.get("question_type", "conceptual")
        if question_type not in ("conceptual", "applied", "scenario", "follow_up"):
            question_type = "conceptual"
        # Rotate styles during normal interview flow

        if not bool(raw.get("is_follow_up", False)):

            styles = [
                "conceptual",
                "applied",
                "scenario",
            ]

            question_type = styles[
                state.questions_asked % len(styles)
            ]

        selected_topic = raw.get("topic", state.role)

        # ============================================================
        # Prevent semantic repetition across full interview
        # ============================================================

        if selected_topic.lower().strip() in covered_concepts:

            fallback_topics = [
                d for d in state.domains
                if d.lower().strip() not in covered_concepts
            ]

            if fallback_topics:
                selected_topic = fallback_topics[0]
        exp = state.experience_level.lower()

        if exp in ["fresher", "student", "intern"]:

            if difficulty == "hard":
                difficulty = "medium"

        elif exp in ["junior"]:

            if difficulty == "hard":
                difficulty = "medium"

        return InterviewStrategy(
            topic=selected_topic,

            resume_evidence=raw.get(
                "resume_evidence",
                ""
            ),

            concept_family=raw.get(
                "concept_family",
                ""
            ),

            difficulty=difficulty,
            question_type=question_type,
            is_follow_up=bool(raw.get("is_follow_up", False)),
            reason=raw.get("reason", ""),
        )
    # ── Difficulty helpers ───────────────────────────────────────

    def adjust_difficulty(
        self,
        current: str,
        recent_performances: List[str],
    ) -> str:
        """
        Rule-based difficulty adjustment (used as fallback / sanity check).
        recent_performances: last 2 performance strings ["strong", "adequate"]
        """
        if len(recent_performances) < 2:
            return current

        last_two = recent_performances[-2:]

        if all(p == "strong" for p in last_two):
            return self._harder(current)

        if all(p == "weak" for p in last_two):
            return current   # don't go easier — probe same level

        return current

    def _harder(self, difficulty: str) -> str:
        return {"easy": "medium", "medium": "hard", "hard": "hard"}[difficulty]

    def _easier(self, difficulty: str) -> str:
        return {"hard": "medium", "medium": "easy", "easy": "easy"}[difficulty]

    # ── Follow-up decision ───────────────────────────────────────

    def should_follow_up(
        self,
        last_record: QuestionRecord,
        last_eval: EvaluationResult,
    ) -> bool:
        """
        Follow up if:
        - last answer was weak
        - AND the last question was NOT already a follow-up
        (one follow-up allowed per topic — then move on)
        """
        print(
        "FOLLOWUP CHECK |",
        "performance=",
        last_eval.performance,
        "| already_followup=",
        last_record.is_follow_up,
    )
        if last_eval.is_weak() and not last_record.is_follow_up:
            return True
        return False

    # ── Weakness detection ───────────────────────────────────────

    def detect_weaknesses(self, history: List[QuestionRecord]) -> List[str]:
        """
        Aggregate gaps_detected across all evaluated answers.
        Used by report_service for deeper analysis.
        """
        all_gaps = []
        for record in history:
            if record.evaluation:
                all_gaps.extend(record.evaluation.gaps_detected)
        # Deduplicate while preserving order
        seen = set()
        unique_gaps = []
        for gap in all_gaps:
            if gap.lower() not in seen:
                seen.add(gap.lower())
                unique_gaps.append(gap)
        return unique_gaps

    def detect_strengths(self, history: List[QuestionRecord]) -> List[str]:
        """Aggregate topics_demonstrated from strong/adequate answers."""
        all_topics = []
        for record in history:
            if record.evaluation and not record.evaluation.is_weak():
                all_topics.extend(record.evaluation.topics_demonstrated)
        seen = set()
        unique = []
        for t in all_topics:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        return unique
    async def build_resume_interview_plan(
    self,
    role: str,
    candidate_name: str,
    experience_level: str,
    skills: List[str],
    domains: List[str],
    projects: List[str],
    total_questions: int,
) -> List[dict]:
        import json
        from backend.prompts.prompts import RESUME_INTERVIEW_PLAN_PROMPT
        from backend.services.llm_service import call_llm_json

     
        prompt = RESUME_INTERVIEW_PLAN_PROMPT.format(
            candidate_name=candidate_name,
            role=role,
            experience_level=experience_level,
            skills=", ".join(skills[:8]),
            domains=", ".join(domains[:5]),
            projects="\n".join(projects[:6]),
   
            total_questions=total_questions,
        )

        result = await call_llm_json(prompt, temperature=0.0, max_tokens=2000)

        if not result or "plan" not in result:
            return []

        return result["plan"]
    # ── State computation ────────────────────────────────────────

    def compute_performance_trend(self, history: List[QuestionRecord]) -> List[str]:
        """Return list of performance strings in order."""
        return [
            r.evaluation.performance
            for r in history
            if r.evaluation is not None
        ]

    def _covered_topics(self, history: List[QuestionRecord]) -> List[str]:
        seen, topics = set(), []
        for r in history:
            t = r.topic.lower()
            if t not in seen:
                seen.add(t)
                topics.append(r.topic)
        return topics

    # ── Private helpers ──────────────────────────────────────────

    def _opening_strategy(self, state: InterviewState) -> InterviewStrategy:

        exp = (state.experience_level or "").lower()

        if exp in ["fresher", "student", "intern", "junior"]:
            difficulty = "easy"
        elif exp in ["mid", "2 years", "3 years", "4 years", "5 years"]:
            difficulty = "medium"
        else:
            difficulty = "hard"

        if state.projects:
            topic = state.projects[0]
        elif state.skills:
            topic = state.skills[0]
        else:
            topic = f"{state.role} fundamentals"

        return InterviewStrategy(
            topic=topic,
            resume_evidence=topic,
            concept_family="Resume Introduction",
            difficulty=difficulty,
            question_type="applied",
            is_follow_up=False,
            reason="Starting interview from candidate resume.",
        )
    def _plan_based_strategy(
            self,
            state: InterviewState,
            latest_evaluation: EvaluationResult,
        ) -> InterviewStrategy:
            plan = state.interview_plan
            idx = state.current_plan_index

            # If plan exhausted, fall back to opening strategy
            if idx >= len(plan):
                return self._fallback_strategy(state)

            slot = plan[idx]

            # Adjust difficulty based on last answer performance
            difficulty = slot.get("difficulty", "easy")
            if state.history and latest_evaluation:
                perf = latest_evaluation.performance
                if perf == "strong":
                    difficulty = self._harder(difficulty)
                elif perf == "weak":
                    difficulty = self._easier(difficulty)

            # Enforce experience level caps
            exp = state.experience_level.lower()
            if exp in ["fresher", "student", "intern", "junior"]:
                if difficulty == "hard":
                    difficulty = "medium"

            resume_evidence = slot.get("resume_evidence", "")
            print("\n===== DIFFICULTY ADAPTATION =====")

            if latest_evaluation:
                print("LAST PERFORMANCE:", latest_evaluation.performance)
            else:
                print("LAST PERFORMANCE: NONE (first question)")

            print("FINAL DIFFICULTY:", difficulty)
            print("=================================")
            return InterviewStrategy(
                topic=resume_evidence or state.role,
                resume_evidence=resume_evidence,
                concept_family="resume",
                difficulty=difficulty,
                question_type=slot.get("question_type", "conceptual"),
                is_follow_up=False,
                reason=f"Testing resume evidence: {resume_evidence}",
            )
    def _follow_up_strategy(
    self,
    state: InterviewState,
    last_record: QuestionRecord,
    last_eval: EvaluationResult,
) -> InterviewStrategy:

        print("FOLLOWUP STRATEGY CREATED")

        return InterviewStrategy(
            topic=last_record.topic,
            resume_evidence=last_record.resume_evidence,
            concept_family=last_record.concept_family,
            difficulty=last_record.difficulty,
            question_type="follow_up",
            is_follow_up=True,
            reason=f"Candidate struggled with {last_record.topic}",
        )
    def _fallback_strategy(self, state: InterviewState) -> InterviewStrategy:
        """Used when LLM strategy call fails."""
        return InterviewStrategy(
            topic=state.role,
            difficulty=state.current_difficulty,
            question_type="applied",
            is_follow_up=False,
            reason="Fallback strategy — LLM strategy call failed.",
        )

    def _summarise_history(self, history: List[QuestionRecord]) -> str:
        if not history:
            return "No questions asked yet."
        lines = []
        for i, r in enumerate(history, 1):
            eval_str = ""
            if r.evaluation:
                eval_str = (
                    f"[Level {r.evaluation.rubric_level}/5 — {r.evaluation.performance}] "
                    f"{r.evaluation.reasoning}"
                )
            lines.append(
                f"Q{i} [{r.topic} | {r.difficulty}]: {r.question_text[:80]}...\n"
                f"   Answer eval: {eval_str or '(not yet evaluated)'}"
            )
        return "\n".join(lines)

    def _format_eval(
        self,
        eval_result: EvaluationResult,
        record: QuestionRecord,
    ) -> str:
        return (
            f"Question topic: {record.topic}\n"
            f"Rubric level: {eval_result.rubric_level}/5\n"
            f"Performance: {eval_result.performance}\n"
            f"Reasoning: {eval_result.reasoning}\n"
            f"Gaps detected: {', '.join(eval_result.gaps_detected) or 'none'}"
        )


# ── Singleton — routes imports this instance ─────────────────
agent = InterviewAgent()
