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
def _topics_path(role: str) -> str:
    safe = role.replace(" ", "_").replace("/", "_")
    return os.path.join(FAISS_INDEX_DIR, f"{safe}_topics.json")


def save_role_topics(role: str, topics: dict):
    import json
    with open(_topics_path(role), "w") as f:
        json.dump(topics, f, indent=2)


def load_role_topics(role: str) -> dict:
    import json
    path = _topics_path(role)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

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
    all_summary_chunks: List[str] = []
    per_pdf_summaries: dict = {}

    for fname in pdf_files:
        pdf_path = os.path.join(KNOWLEDGE_BASE_DIR, fname)
        if not os.path.exists(pdf_path):
            print(f"[Ingest] WARNING: {fname} not found in knowledge_base/")
            continue

        print(f"[Ingest] Processing {fname} for role '{role}'...")

        text, _ = extract_pdf_parallel(pdf_path)
        summary_chunks, rag_chunks = semantic_chunk(text)
        print(f"[DEBUG] Summary chunks sample: {summary_chunks[:2]}")
        all_chunks.extend(rag_chunks)
        all_summary_chunks.extend(summary_chunks)
        per_pdf_summaries[fname] = summary_chunks
        print(f"[Ingest] {fname} → {len(rag_chunks)} chunks")

    if not all_chunks:
        return {"status": "no_docs", "chunk_count": 0}

    # Build FAISS index
    fake_hash = hashlib.md5(role.encode()).hexdigest()
    index = build_faiss_index(all_chunks, fake_hash)

    save_faiss_for_role(role, index)
    print(f"[Ingest] Role '{role}' indexed — {len(all_chunks)} total chunks")
    topics = await extract_kb_topics(role, per_pdf_summaries, pdf_files)
    import asyncio
    await asyncio.sleep(10)  # wait 10 seconds before topic extraction
    save_role_topics(role, topics)
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
async def extract_kb_topics(role: str, per_pdf_summaries: dict, pdf_files: List[str]) -> dict:
    from datetime import datetime
    from backend.prompts.prompts import KB_TOPIC_EXTRACTION_PROMPT
    from backend.services.llm_service import call_llm_json
    import json

    # Even sampling across all summary chunks
    MAX_CHUNKS = 40
    PER_PDF_LIMIT = 15
    SKIP_FRONT_MATTER = 3  # skip copyright/preface chunks
    sampled = []
    for fname, chunks in per_pdf_summaries.items():
        useful = chunks[SKIP_FRONT_MATTER:]  # skip front matter
        step = max(1, len(useful) // PER_PDF_LIMIT)
        sampled.extend(useful[::step][:PER_PDF_LIMIT])
    # print(f"[DEBUG] Sampled {len(sampled)} chunks from {len(per_pdf_summaries)} PDFs")
    # print(f"[DEBUG] First sampled chunk preview: {sampled[0][:300] if sampled else 'EMPTY'}")
    summary_context = "\n\n---\n\n".join(sampled)

    prompt = KB_TOPIC_EXTRACTION_PROMPT.format(
        role=role,
        summary_context=summary_context[:8000],
        generated_at=datetime.utcnow().isoformat(),
        pdfs=json.dumps(pdf_files),
    )

    try:
        result = await call_llm_json(prompt, temperature=0.0, max_tokens=2000)
    except Exception as e:
        print(f"[DEBUG] extract_kb_topics LLM error: {e}")
        result = None
    print(f"[DEBUG] LLM result keys: {list(result.keys()) if result else 'NULL'}")
    if not result or "concepts" not in result:
        return {"role": role, "pdfs": pdf_files, "concepts": []}
    return result