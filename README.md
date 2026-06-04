# AI Technical Interviewer

A role-based AI candidate screening system powered by RAG.  
Built for the PGAGI AI/ML & Backend Intern Assignment.

## Architecture

```
Frontend (React + Vite + Tailwind)
    ↓ REST
Backend (FastAPI + SQLAlchemy)
    ↓
RAG Pipeline (dco_mind — your existing engine)
    ↓
FAISS vector store ← Role-specific PDFs (ML books)
    ↓
PostgreSQL (sessions, questions, answers)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL running locally
- Ollama running locally with `llama3` and `nomic-embed-text` pulled

### 1. Clone & set up Python env

```bash
# From the project root
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Add your existing dco_mind package to Python path
# Option A — install as editable package (recommended):
pip install -e /path/to/GenAI-Doc-old

# Option B — set PYTHONPATH in .env:
# PYTHONPATH=/path/to/GenAI-Doc-old
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your DB URL, Ollama URL, etc.
```

### 3. Create the database

```bash
psql -U postgres -c "CREATE DATABASE ai_interviewer;"
# Tables are auto-created on first backend start
```

### 4. Add knowledge base PDFs

Download the ML books from the assignment links and place them in:
```
backend/knowledge_base/
    ml_mitchell.pdf
    hundred_page_ml.pdf
    intro_ml_python.pdf
    master_ml_algorithms.pdf
    ml_absolute_beginners.pdf
```

### 5. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 6. Ingest knowledge base (one-time per role)

```bash
curl -X POST "http://localhost:8000/api/knowledge/ingest?role=AI/ML Engineer"
curl -X POST "http://localhost:8000/api/knowledge/ingest?role=Data Scientist"
# Repeat for other roles as needed
```

### 7. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/roles` | List supported roles |
| POST   | `/api/knowledge/ingest?role=X` | Ingest PDFs for a role |
| GET    | `/api/knowledge/status` | Check which roles are indexed |
| POST   | `/api/sessions/start` | Upload resume + start session |
| GET    | `/api/sessions/{id}` | Get session info |
| POST   | `/api/sessions/{id}/next-question` | Generate next question |
| POST   | `/api/sessions/{id}/answer` | Submit answer |
| POST   | `/api/sessions/{id}/complete` | Mark session done |
| GET    | `/api/sessions/{id}/report` | Full report + analysis |

## Project Structure

```
ai-interviewer/
├── backend/
│   ├── api/           routes.py           — all FastAPI endpoints
│   ├── core/          config.py           — settings & env vars
│   ├── db/            models.py           — SQLAlchemy ORM models
│   │                  database.py         — async engine + session
│   ├── prompts/       prompts.py          — all LLM prompts
│   ├── services/
│   │   ├── resume_service.py     — PDF parsing + LLM extraction
│   │   ├── llm_service.py        — Ollama async wrapper
│   │   ├── knowledge_service.py  — FAISS ingestion per role
│   │   ├── question_service.py   — RAG → question generation
│   │   └── report_service.py     — session analysis
│   ├── knowledge_base/           — place ML PDFs here
│   ├── uploads/                  — resume uploads (auto-created)
│   ├── faiss_indices/            — FAISS indexes (auto-created)
│   ├── main.py                   — FastAPI app entry point
│   └── requirements.txt
└── frontend/
    └── src/
        ├── api/       client.js           — axios API layer
        ├── store/     interviewStore.js   — Zustand global state
        ├── pages/
        │   ├── UploadPage.jsx     — resume upload + role select
        │   ├── InterviewPage.jsx  — Q&A interaction
        │   └── ReportPage.jsx     — final report + analysis
        └── App.jsx                — React Router setup
```

## How the RAG pipeline works

1. **Ingest** — PDF books are chunked (semantic_chunk from dco_mind) and stored in a FAISS index per role.
2. **Resume parse** — LLM extracts skills, domains, experience level from uploaded resume.
3. **Query construction** — LLM generates targeted retrieval queries from the candidate profile.
4. **Retrieval** — multi_query_retrieve + rerank_docs (your existing code) pull the most relevant chunks.
5. **Question generation** — LLM generates one question grounded in retrieved chunks, adapted to candidate level and prior answers.
6. **Storage** — every question, answer, and source chunk is stored in PostgreSQL for full traceability.
7. **Report** — session analysis via LLM over the full Q&A transcript.
