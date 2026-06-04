"""
knowledge_service.py
Handles ingestion of role-specific PDF books into FAISS vector stores.
Reuses your existing semantic_chunk + build_faiss_index from dco_mind.
"""
import os
import hashlib
import pickle
from pathlib import Path
from typing import List

from backend.core.config import (
    KNOWLEDGE_BASE_DIR, FAISS_INDEX_DIR,
    ROLE_KNOWLEDGE_MAP, CHUNK_SIZE, CHUNK_OVERLAP
)

# ── Lazy import from your existing dco_mind package ──────────────
# Point PYTHONPATH at the GenAI-Doc-old directory so these resolve.
from backend.rag_core.ingestion import (
    semantic_chunk,
    extract_pdf_parallel
)

from backend.rag_core.embeddings import (
    build_faiss_index
)
    # print("[KnowledgeService] dco_mind not found — using built-in fallback chunker")


# # ── Fallback chunker when dco_mind not on path ───────────────────
# def _simple_chunk(text: str, size: int = 600, overlap: int = 100) -> List[str]:
#     words = text.split()
#     chunks, i = [], 0
#     while i < len(words):
#         chunk = " ".join(words[i: i + size])
#         chunks.append(chunk)
#         i += size - overlap
#     return chunks


def _hash_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _index_path(role: str) -> str:
    safe = role.replace(" ", "_").replace("/", "_")
    return os.path.join(FAISS_INDEX_DIR, f"{safe}.pkl")


def load_faiss_for_role(role: str):
    """Load a pre-built FAISS index for a role. Returns None if not built yet."""
    path = _index_path(role)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def save_faiss_for_role(role: str, index):
    path = _index_path(role)
    with open(path, "wb") as f:
        pickle.dump(index, f)


async def ingest_role_knowledge(role: str) -> dict:
    """
    Ingest all PDFs for a role and build/update its FAISS index.
    Returns {"status": "ready", "chunk_count": N}
    """
    pdf_files = ROLE_KNOWLEDGE_MAP.get(role, [])
    all_chunks: List[str] = []

    for fname in pdf_files:
        pdf_path = os.path.join(KNOWLEDGE_BASE_DIR, fname)
        if not os.path.exists(pdf_path):
            print(f"[Ingest] WARNING: {fname} not found in knowledge_base/")
            continue

        print(f"[Ingest] Processing {fname} for role '{role}'...")

        text, _ = extract_pdf_parallel(pdf_path)
        _, rag_chunks = semantic_chunk(text)

        all_chunks.extend(rag_chunks)
        print(f"[Ingest] {fname} → {len(rag_chunks)} chunks")

    if not all_chunks:
        return {"status": "no_docs", "chunk_count": 0}

    # Build FAISS index
    fake_hash = hashlib.md5(role.encode()).hexdigest()
    index = build_faiss_index(all_chunks, fake_hash)

    save_faiss_for_role(role, index)
    print(f"[Ingest] Role '{role}' indexed — {len(all_chunks)} total chunks")
    return {"status": "ready", "chunk_count": len(all_chunks)}


def get_all_chunks_for_role(role: str) -> List[str]:
    """Return raw chunk strings for a role's FAISS index (for retrieval)."""
    idx = load_faiss_for_role(role)
    if idx is None:
        return []
    if isinstance(idx, dict):
        return idx.get("chunks", [])
    # If it's a real FAISS/LangChain index, pull stored docs
    try:
        docs = idx.docstore._dict.values()
        return [d.page_content for d in docs]
    except Exception:
        return []
