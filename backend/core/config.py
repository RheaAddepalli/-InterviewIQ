import os
# from dotenv import load_dotenv

# load_dotenv()
from dotenv import load_dotenv
import os

BASE_PATH = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_PATH, ".env")

load_dotenv(ENV_PATH)

# ── LLM ────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:latest")
EMBED_MODEL = os.getenv(
    "EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
# EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# ── Database ────────────────────────────────────────────────────
# DATABASE_URL = os.getenv(
#     "DATABASE_URL",
#     "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interviewer"
# )
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./ai_interviewer.db"
)

# ── RAG ─────────────────────────────────────────────────────────
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", 600))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", 100))
TOP_K_RETRIEVE    = int(os.getenv("TOP_K_RETRIEVE", 8))
RERANK_TOP_K      = int(os.getenv("RERANK_TOP_K", 5))
MAX_WORKERS       = int(os.getenv("MAX_WORKERS", 4))

# ── Interview ───────────────────────────────────────────────────
MAX_QUESTIONS_PER_SESSION = int(os.getenv("MAX_QUESTIONS", 10))

# ── Paths ───────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")
UPLOADS_DIR       = os.path.join(BASE_DIR, "uploads")
FAISS_INDEX_DIR   = os.path.join(BASE_DIR, "faiss_indices")

os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FAISS_INDEX_DIR, exist_ok=True)

# ── Roles ────────────────────────────────────────────────────────
# ── Supported interview roles ──────────────────────────────────

SUPPORTED_ROLES = [

    "AI/ML Engineer",

    "Data Scientist",

    "Deep Learning Engineer",
]

# ── Role → knowledge base file mapping ──────────────────────────
ROLE_KNOWLEDGE_MAP = {

    # ============================================================
    # AI / ML Engineer
    # ============================================================

    "AI/ML Engineer": [

        "ml_mitchell.pdf",

        "ml_absolute_beginners.pdf",

        "ai_ml_dl.pdf",
    ],

    # ============================================================
    # Data Scientist
    # ============================================================

    "Data Scientist": [

        "intro_ml_python.pdf",

        "master_ml_algorithms.pdf",
    ],

    # ============================================================
    # Deep Learning Engineer
    # ============================================================

    "Deep Learning Engineer": [

        "ai_ml_dl.pdf",

        "ml_mitchell.pdf",
    ],
}