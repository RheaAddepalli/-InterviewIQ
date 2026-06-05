import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Integer,
    Float, ForeignKey, JSON, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    role         = Column(String(100), nullable=False)
    status       = Column(String(30), default="active")   # active | completed | aborted

    # Resume data
    resume_path      = Column(String(500))
    candidate_name   = Column(String(200))
    resume_skills    = Column(JSON, default=list)       # ["Python", "FastAPI", ...]
    resume_experience_level = Column(String(30))        # junior | mid | senior
    resume_domains   = Column(JSON, default=list)       # ["NLP", "CV", ...]
    resume_projects = Column(JSON, default=list)
    resume_raw_text  = Column(Text)

    # Interview config
    total_questions   = Column(Integer, default=0)
    questions_asked   = Column(Integer, default=0)
    interview_plan    = Column(JSON, default=list)
    current_plan_index = Column(Integer, default=0)

    # Relations
    questions = relationship("Question", back_populates="session",
                             cascade="all, delete-orphan", order_by="Question.order_index")

    def to_dict(self):
        return {
            "id": str(self.id),
            "role": self.role,
            "status": self.status,
            "candidate_name": self.candidate_name,
            "resume_skills": self.resume_skills or [],
            "resume_experience_level": self.resume_experience_level,
            "resume_domains": self.resume_domains or [],
            "questions_asked": self.questions_asked,
            "total_questions": self.total_questions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Question(Base):
    __tablename__ = "questions"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id  = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Question content
    question_text  = Column(Text, nullable=False)
    question_type  = Column(String(50))            # conceptual | applied | scenario | follow_up
    topic          = Column(String(200))
    difficulty     = Column(String(20))            # easy | medium | hard
    resume_evidence = Column(String(300))
    concept_family = Column(String(300))

    # Traceability — which chunks generated this question
    source_chunks  = Column(JSON, default=list)    # list of chunk text snippets
    source_docs    = Column(JSON, default=list)    # which knowledge base files

    # Answer
    answer_text    = Column(Text)
    answered_at    = Column(DateTime)
    answer_duration_sec = Column(Float)
    rubric_level = Column(Integer)

    performance = Column(String(20))

    evaluation_reasoning = Column(Text)

    topics_demonstrated = Column(JSON, default=list)

    gaps_detected = Column(JSON, default=list)

    # Analysis
    keywords_expected = Column(JSON, default=list)
    is_follow_up   = Column(Boolean, default=False)
    follow_up_of   = Column(UUID(as_uuid=True), nullable=True)

    session = relationship("Session", back_populates="questions")

    def to_dict(self):
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "order_index": self.order_index,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "answer_text": self.answer_text,
            "source_chunks": self.source_chunks or [],
            "is_follow_up": self.is_follow_up,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
        }


class KnowledgeIndex(Base):
    """Tracks which PDFs have been ingested so we don't reprocess."""
    __tablename__ = "knowledge_indices"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name   = Column(String(500), unique=True, nullable=False)
    file_hash   = Column(String(64), nullable=False)
    role        = Column(String(100))
    indexed_at  = Column(DateTime, default=datetime.utcnow)
    chunk_count = Column(Integer, default=0)
    status      = Column(String(20), default="ready")   # ready | processing | failed
