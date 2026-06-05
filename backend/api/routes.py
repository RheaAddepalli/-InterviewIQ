"""
routes.py — all API endpoints for the AI Interviewer.
"""
import os
import uuid
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import get_db
from backend.db.models import Session as InterviewSession, Question, KnowledgeIndex
from backend.core.config import UPLOADS_DIR, SUPPORTED_ROLES, MAX_QUESTIONS_PER_SESSION
from backend.services.resume_service import parse_resume
from backend.services.question_service import generate_next_question
from backend.services.knowledge_service import ingest_role_knowledge, load_faiss_for_role,load_role_topics
from backend.services.report_service import generate_session_report
from backend.services.evaluator import evaluate_answer,EvaluationResult

from backend.services.interview_agent import (
    InterviewAgent,
    InterviewState,
    QuestionRecord,
    InterviewStrategy,
    agent
)

router = APIRouter(prefix="/api")


# ════════════════════════════════════════════════════════════════
# HEALTH
# ════════════════════════════════════════════════════════════════

@router.get("/health")
async def health():
    return {"status": "ok", "service": "ai-interviewer"}


# ════════════════════════════════════════════════════════════════
# ROLES
# ════════════════════════════════════════════════════════════════

@router.get("/roles")
async def get_roles():
    return {"roles": SUPPORTED_ROLES}


# ════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE — ingest PDFs
# ════════════════════════════════════════════════════════════════

@router.post("/knowledge/ingest")
async def ingest_knowledge(role: str, db: AsyncSession = Depends(get_db)):
    """
    Trigger ingestion of knowledge base PDFs for a role.
    Call once per role before interviews start.
    """
    if role not in SUPPORTED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unsupported role: {role}")

    result = await ingest_role_knowledge(role)
    return {"role": role, **result}


@router.get("/knowledge/status")
async def knowledge_status(db: AsyncSession = Depends(get_db)):
    """Check which roles have a FAISS index ready."""
    statuses = {}
    for role in SUPPORTED_ROLES:
        idx = load_faiss_for_role(role)
        statuses[role] = "ready" if idx is not None else "not_indexed"
    return {"statuses": statuses}


# ════════════════════════════════════════════════════════════════
# SESSION — upload resume + start interview
# ════════════════════════════════════════════════════════════════

@router.post("/sessions/start")
async def start_session(
    resume: UploadFile = File(...),
    role: str = Form(...),
    experience_level: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Upload resume PDF, select role → returns session_id.
    """
    if role not in SUPPORTED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unsupported role: {role}")

    # Save resume to disk
    ext = os.path.splitext(resume.filename)[1] or ".pdf"
    fname = f"{uuid.uuid4()}{ext}"
    fpath = os.path.join(UPLOADS_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(resume.file, f)

    # Parse resume
    parsed = await parse_resume(fpath)
    print("\n===== PARSED RESUME =====")
    print("NAME:", parsed.get("candidate_name"))
    print("SKILLS:", parsed.get("skills"))
    print("DOMAINS:", parsed.get("domains"))
    print("PROJECTS:", parsed.get("notable_projects"))
    print("=========================\n")

    # Create session in DB
    session = InterviewSession(
    role=role,
    resume_path=fpath,
    candidate_name=parsed.get("candidate_name", ""),
    resume_skills=parsed.get("skills", []) + parsed.get("technologies", []),
    resume_experience_level=experience_level,
    resume_domains=parsed.get("domains", []),
    resume_projects=parsed.get("notable_projects", []),
    resume_raw_text=parsed.get("raw_text", "")[:5000],
    total_questions=MAX_QUESTIONS_PER_SESSION,
    status="active",
)
    db.add(session)
    # Build interview plan
    plan = await agent.build_resume_interview_plan(
    role=role,
    candidate_name=parsed.get("candidate_name", ""),
    experience_level=experience_level,
    skills=parsed.get("skills", []),
    domains=parsed.get("domains", []),
    projects=parsed.get("notable_projects", []),
    total_questions=MAX_QUESTIONS_PER_SESSION,
)
    session.interview_plan = plan
    print(f"\n===== INTERVIEW PLAN =====")
    for slot in plan:
        print(f"  Slot {slot.get('slot')}: {slot.get('topic')} [{slot.get('difficulty')}] — {slot.get('resume_evidence')}")
    print("==========================\n")
    await db.flush()

    return {
        "session_id": str(session.id),
        "candidate_name": session.candidate_name,
        "experience_level": session.resume_experience_level,
        "skills": session.resume_skills,
        "domains": session.resume_domains,
        "role": role,
        "total_questions": MAX_QUESTIONS_PER_SESSION,
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_session_or_404(session_id, db)
    return session.to_dict()


# ════════════════════════════════════════════════════════════════
# INTERVIEW — generate next question
# ════════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/next-question")
async def next_question(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Generate the next interview question for this session.
    Uses resume profile + previous Q&A for context-aware generation.
    """
    session = await _get_session_or_404(session_id, db)

    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    if session.questions_asked >= session.total_questions:
        return {"done": True, "message": "All questions have been asked"}

    # Load previous questions + last answer for adaptive follow-up
    result = await db.execute(
        select(Question)
        .where(Question.session_id == session.id)
        .order_by(Question.order_index)
    )
    existing_questions: list[Question] = result.scalars().all()

    previous_q_texts = [q.question_text for q in existing_questions]
    last_answer = None
    if existing_questions:
        last_q = existing_questions[-1]
        last_answer = last_q.answer_text  # may be None if not yet answered

    # Generate question
#     q_data = await generate_next_question(

#     role=session.role,

#     experience_level=
#         session.resume_experience_level or "mid",

#     skills=
#         session.resume_skills or [],

#     domains=
#         session.resume_domains or [],
#     projects=
#         session.resume_projects or [],

#     previous_questions=
#         previous_q_texts,

#     last_answer=
#         last_answer,

#     # ============================================================
#     # Initial interview defaults
#     # ============================================================

#     strategy="new_topic",

#     target_topic="core fundamentals",

#     target_difficulty="easy",
# )

  

    # Build history from existing questions
    history = []
    for q in existing_questions:
        eval_result = None
        if q.rubric_level is not None:
            eval_result = EvaluationResult(
                rubric_level=q.rubric_level,
                performance=q.performance or "weak",
                reasoning=q.evaluation_reasoning or "",
                topics_demonstrated=q.topics_demonstrated or [],
                gaps_detected=q.gaps_detected or [],
            )
        history.append(QuestionRecord(
            question_text=q.question_text,
            topic=q.topic or "",
            difficulty=q.difficulty or "easy",
            question_type=q.question_type or "conceptual",
            is_follow_up=q.is_follow_up or False,
            answer_text=q.answer_text,
            evaluation=eval_result,
            resume_evidence=q.resume_evidence or "",
            concept_family=q.concept_family or "",
        ))

    state = InterviewState(
        role=session.role,
        experience_level=session.resume_experience_level,
        skills=session.resume_skills or [],
        domains=session.resume_domains or [],
        projects=session.resume_projects or [],
        questions_asked=len(existing_questions),
        total_questions=session.total_questions,
        history=history,
        interview_plan=session.interview_plan or [],
        current_plan_index=session.current_plan_index or 0,
    )

    last_eval = history[-1].evaluation if history else EvaluationResult(
        rubric_level=1, performance="weak", reasoning="", 
        topics_demonstrated=[], gaps_detected=[]
    )

    initial_strategy = await agent.decide_strategy(state, last_eval)
    print("=" * 50)
    print("NEXT QUESTION CALLED")
    print("session:", session.id)
    print("existing questions:", len(existing_questions))
    print("=" * 50)

    q_data = await generate_next_question(
    strategy=initial_strategy,
    role=session.role,
    experience_level=session.resume_experience_level or "mid",
    skills=session.resume_skills or [],
    domains=session.resume_domains or [],
    projects=session.resume_projects or [],
    covered_topics=[
        q.topic
        for q in existing_questions
        if q.topic
    ],
)

    # Persist question
    order = len(existing_questions) + 1
    question = Question(
        session_id=session.id,
        order_index=order,
        question_text=q_data["question_text"],
        question_type=q_data.get("question_type"),
        resume_evidence=initial_strategy.resume_evidence,
        concept_family=initial_strategy.concept_family,
        topic=q_data.get("topic"),
        difficulty=q_data.get("difficulty"),
        source_chunks=q_data.get("source_chunks", []),
        keywords_expected=q_data.get("keywords_expected", []),
        is_follow_up=q_data.get("is_follow_up", False),
    )
    db.add(question)
    session.current_plan_index = (session.current_plan_index or 0) + 1

    session.questions_asked = order
    session.current_plan_index = (session.current_plan_index or 0) + 1
    await db.flush()

    return {
        "done": False,
        "question_id": str(question.id),
        "order_index": order,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "topic": question.topic,
        "difficulty": question.difficulty,
        "is_follow_up": question.is_follow_up,
        "questions_remaining": session.total_questions - order,
    }


# ════════════════════════════════════════════════════════════════
# INTERVIEW — submit answer
# ════════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Store candidate's answer to a question.
    payload: {"question_id": "...", "answer_text": "...", "duration_sec": 45}
    """
    session = await _get_session_or_404(session_id, db)

    question_id = payload.get("question_id")
    answer_text = payload.get("answer_text", "").strip()
    duration    = payload.get("duration_sec")

    result = await db.execute(
        select(Question).where(
            Question.id == uuid.UUID(question_id),
            Question.session_id == session.id
        )
    )
    question: Optional[Question] = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.answer_text       = answer_text
    question.answered_at       = datetime.utcnow()
    question.answer_duration_sec = duration

    await db.flush()
        # ============================================================
    # STEP 1: Evaluate candidate answer
    # ============================================================

    evaluation = await evaluate_answer(
        question=question.question_text,
        answer=answer_text,
        role=session.role,
    )

    # ============================================================
    # STEP 2: Persist evaluation
    # ============================================================

    question.rubric_level = evaluation.rubric_level
    question.performance = evaluation.performance
    question.evaluation_reasoning = evaluation.reasoning

    question.topics_demonstrated = (
        evaluation.topics_demonstrated
    )

    question.gaps_detected = (
        evaluation.gaps_detected
    )

    # ============================================================
    # STEP 3: Build interview history
    # ============================================================

    result = await db.execute(

    select(Question)

    .where(Question.session_id == session.id)

    .order_by(Question.order_index)

)

    all_questions = result.scalars().all()

    history = []

    for q in all_questions:

        eval_obj = None

        if q.performance:
            eval_obj = EvaluationResult(
                rubric_level=q.rubric_level or 0,
                performance=q.performance,
                reasoning=q.evaluation_reasoning or "",
                topics_demonstrated=q.topics_demonstrated or [],
                gaps_detected=q.gaps_detected or [],
            )

        history.append(
            QuestionRecord(
                question_text=q.question_text,
                topic=q.topic or "",

                resume_evidence=
                    q.resume_evidence or "",

                concept_family=
                    q.concept_family or "",

                difficulty=q.difficulty or "medium",
                question_type=q.question_type or "conceptual",
                is_follow_up=q.is_follow_up or False,
                answer_text=q.answer_text or "",
                evaluation=eval_obj,
            )
        )

    # ============================================================
    # STEP 4: Build adaptive interview state
    # ============================================================

    state = InterviewState(
    role=session.role,
    experience_level=session.resume_experience_level,
    skills=session.resume_skills or [],
    domains=session.resume_domains or [],
    projects=session.resume_projects or [],
    questions_asked=session.questions_asked,
    total_questions=session.total_questions,
    history=history,
)

    # ============================================================
    # STEP 5: Ask agent what to do next
    # ============================================================

    agent = InterviewAgent()

    strategy = await agent.decide_strategy(
        state=state,
        latest_evaluation=evaluation,
    )

    # ============================================================
    # STEP 6: Generate next question
    # ============================================================
    if session.questions_asked >= session.total_questions:
        session.status = "completed"
        await db.flush()

        return {
            "status": "completed"
        }

    # question_data = await generate_next_question(
    #     role=session.role,
    #     experience_level=session.resume_experience_level or "mid",
    #     skills=session.resume_skills or [],
    #     domains=session.resume_domains or [],
    #     projects=session.resume_projects or [],
    #     previous_questions=[
    #         q.question_text
    #         for q in all_questions
    #     ],
    #     last_answer=answer_text,

    #     strategy=strategy.question_type,
    #     target_topic=strategy.topic,
    #     target_difficulty=strategy.difficulty,
    # )
    question_data = await generate_next_question(
    strategy=strategy,
    role=session.role,
    experience_level=session.resume_experience_level or "mid",
    skills=session.resume_skills or [],
    domains=session.resume_domains or [],
    projects=session.resume_projects or [],
    covered_topics=[
        q.topic
        for q in all_questions
        if q.topic
    ],
)

    # ============================================================
    # STEP 7: Save next question
    # ============================================================

    new_question = Question(
        session_id=session.id,
        order_index=session.questions_asked + 1,

        question_text=question_data["question_text"],
        question_type=question_data.get("question_type"),
        resume_evidence=strategy.resume_evidence,
        concept_family=strategy.concept_family,
        topic=question_data.get("topic"),
        difficulty=question_data.get("difficulty"),

        source_chunks=question_data.get(
            "source_chunks",
            []
        ),

        keywords_expected=question_data.get(
            "keywords_expected",
            []
        ),

        is_follow_up=question_data.get(
            "is_follow_up",
            False
        ),
    )

    db.add(new_question)

    session.questions_asked += 1

    await db.flush()

    # ============================================================
    # STEP 8: Return adaptive response
    # ============================================================

    return {

        "status": "saved",

        "evaluation": evaluation.to_dict(),

        "strategy": {
            "topic": strategy.topic,
            "difficulty": strategy.difficulty,
            "question_type": strategy.question_type,
            "is_follow_up": strategy.is_follow_up,
            "reason": strategy.reason,
        },

        "next_question": {
    "question_id": str(new_question.id),
    "order_index": session.questions_asked,
    "question_text": new_question.question_text,
    "difficulty": new_question.difficulty,
    "topic": new_question.topic,
    "question_type": new_question.question_type,
    "is_follow_up": new_question.is_follow_up,
}
    }


# ════════════════════════════════════════════════════════════════
# SESSION — complete + get report
# ════════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark session as completed."""

    session = await _get_session_or_404(
        session_id,
        db
    )

    session.status = "completed"

    await db.flush()

    return {
        "status": "completed",
        "session_id": session_id,
    }


@router.get("/sessions/{session_id}/report")
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return the full session report with AI analysis."""
    session = await _get_session_or_404(session_id, db)

    result = await db.execute(
        select(Question)
        .where(Question.session_id == session.id)
        .order_by(Question.order_index)
    )
    questions: list[Question] = result.scalars().all()

    # Build Q&A transcript for analysis
    qa_list = [
        {
            "question": q.question_text,
            "answer": q.answer_text or "",
            "topic": q.topic or "",
        }
        for q in questions
    ]

    analysis = await generate_session_report(
        role=session.role,
        candidate_name=session.candidate_name or "Candidate",
        experience_level=session.resume_experience_level or "mid",
        questions_and_answers=qa_list,
    )

    return {
        "session": session.to_dict(),
        "questions": [q.to_dict() for q in questions],
        "analysis": analysis,
    }


# ════════════════════════════════════════════════════════════════
# HELPER
# ════════════════════════════════════════════════════════════════

async def _get_session_or_404(session_id: str, db: AsyncSession) -> InterviewSession:
    try:
        uid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == uid)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
