from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.db.database import init_db
from backend.api.routes import router

from backend.core.config import SUPPORTED_ROLES
from backend.services.knowledge_service import (
    ingest_role_knowledge
)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # ============================================================
    # Database startup
    # ============================================================

    await init_db()

    print("[Startup] Database tables created")

    # ============================================================
    # Preload knowledge bases
    # ============================================================

    for role in SUPPORTED_ROLES:

        print(f"[Startup] Loading knowledge base for: {role}")

        try:

            result = await ingest_role_knowledge(role)

            print(
                f"[Startup] {role} ready "
                f"({result.get('chunk_count', 0)} chunks)"
            )

        except Exception as e:

            print(
                f"[Startup] Failed loading "
                f"{role}: {e}"
            )

    print("[Startup] All knowledge bases loaded")

    yield

    print("[Shutdown] Goodbye")


app = FastAPI(
    title="AI Interviewer API",
    version="1.0.0",
    description="Role-based AI candidate screening system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
