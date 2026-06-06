"""
question_service.py
Pure execution layer. Receives a strategy from interview_agent, executes it.

Responsibilities:
  - Build retrieval queries from strategy + candidate profile
  - Retrieve relevant chunks from FAISS
  - Call LLM to generate one question grounded in retrieved context
  - Return structured question dict with source traceability

Does NOT:
  - Decide topic, difficulty, or question type (that's interview_agent)
  - Evaluate answers (that's evaluator)
  - Write to DB (that's routes)
  - Know about session state (that's routes)
"""
from typing import List

from backend.core.config import TOP_K_RETRIEVE
from backend.prompts.prompts import QUERY_CONSTRUCTION_PROMPT, QUESTION_GENERATION_PROMPT
from backend.services.llm_service import call_llm_json
from backend.services.knowledge_service import load_faiss_for_role, get_all_chunks_for_role
from backend.services.interview_agent import InterviewStrategy
from backend.rag_core.retrieval import multi_query_retrieve


async def _build_retrieval_queries(
    strategy: InterviewStrategy,
    role: str,
    experience_level: str,
    skills: List[str],
    domains: List[str],
    projects: List[str],
) -> List[str]:
    """
    Build targeted retrieval queries using strategy + candidate profile.
    Queries are topic-focused — no project names, no resume specifics.
    """
    prompt = QUERY_CONSTRUCTION_PROMPT.format(
    role=role,
    experience_level=experience_level,
    topic=strategy.topic,
    resume_evidence=strategy.resume_evidence,
    difficulty=strategy.difficulty,
    skills=", ".join(skills[:8]),
    domains=", ".join(domains[:5]),
    projects=", ".join(projects),
    num_queries=4,
)
    result = await call_llm_json(prompt)
    if isinstance(result, list) and result:
        return result[:4]

    # Fallback — build basic queries from topic if LLM fails
    # return [
    #     f"{strategy.topic} {role}",
    #     f"{strategy.topic} {strategy.difficulty}",
    #     f"{strategy.topic} tradeoffs",
    #     f"{strategy.topic} implementation",
    # ]
    return [
    f"{strategy.topic} concepts",
    f"{strategy.topic} implementation",
    f"{strategy.topic} tradeoffs",
    f"{strategy.topic} evaluation",
]


def _retrieve_chunks(
    queries: List[str],
    faiss_index,
    all_chunks: List[str],
    experience_level: str,
) -> List[str]:
    """
    Run retrieval for each query, deduplicate results.
    Uses backend.rag_core.retrieval which handles reranking internally.
    """
    retrieved: List[str] = []

    for query in queries:
        docs = multi_query_retrieve(
            query,
            faiss_index,
            k=TOP_K_RETRIEVE,
            all_chunks=all_chunks,
            query_type="CONCEPTUAL",
            experience_level=experience_level,
        )
        for d in docs:
            text = d.page_content if hasattr(d, "page_content") else str(d)
            if text not in retrieved:
                retrieved.append(text)

    return retrieved
async def generate_next_question(
    strategy: InterviewStrategy,
    role: str,
    experience_level: str,
    skills: List[str],
    domains: List[str],
    projects: List[str],
    covered_topics: List[str],
) -> dict:
    """
    Execute the strategy — retrieve context, generate one grounded question.

    Args:
        strategy:         Decided by interview_agent
        role:             From session
        experience_level: From resume parse
        skills:           From resume parse
        domains:          From resume parse
        covered_topics:   Topics already asked — avoid repeating

    Returns dict with:
        question_text, question_type, topic, difficulty,
        is_follow_up, source_chunks (for traceability)
    """
    # ── Step 1: Load knowledge base ──────────────────────────────
    faiss_index = load_faiss_for_role(role)
    all_chunks  = get_all_chunks_for_role(role)
    # print("\n========== QUESTION DEBUG ==========")
    # print("PROJECTS:", projects)
    # print("STRATEGY TOPIC:", strategy.topic)
    # print("QUESTION TYPE:", strategy.question_type)
    # print("DIFFICULTY:", strategy.difficulty)
    # print("====================================")
    # ── Step 2: Build retrieval queries ──────────────────────────
    queries = await _build_retrieval_queries(
    strategy,
    role,
    experience_level,
    skills,
    domains,
    projects,
)
    # print("\n========== RETRIEVAL QUERIES ==========")
    # for q in queries:
    #     print(q)
    # print("=======================================")
    # ── Step 3: Retrieve chunks ──────────────────────────────────
    retrieved_chunks = _retrieve_chunks(
        queries, faiss_index, all_chunks, experience_level
    )
    # print("\n========== RETRIEVED CHUNKS ==========")

    # for i, chunk in enumerate(retrieved_chunks[:5], start=1):
    #     print(f"\n----- CHUNK {i} -----")

    #     if isinstance(chunk, str):
    #         print(chunk[:800])
    #     else:
    #         print(str(chunk)[:800])

    # print("======================================")

    context_text = "\n\n---\n\n".join(retrieved_chunks[:8])

    # ── Step 4: Generate question ────────────────────────────────
    prompt = QUESTION_GENERATION_PROMPT.format(
        role=role,
        experience_level=experience_level,
        resume_evidence=strategy.resume_evidence,
        skills=", ".join(skills[:8]),
        domains=", ".join(domains[:5]),
        projects=", ".join(projects),
        topic=strategy.topic,
        difficulty=strategy.difficulty,
        question_type=strategy.question_type,
        is_follow_up=str(strategy.is_follow_up).lower(),
        strategy_reason=strategy.reason,
        context=context_text[:3000],
        covered_topics=", ".join(covered_topics) or "None yet",
    )

    result = await call_llm_json(prompt, temperature=0.3)

    # ── Safety fallback ──────────────────────────────────────────
    if not result or "question_text" not in result:
        result = {
            "question_text": (
                f"What tradeoffs would you consider when implementing "
                f"{strategy.topic} in a {role} system?"
            ),
            "question_type": strategy.question_type,
            "topic":         strategy.topic,
            "difficulty":    strategy.difficulty,
        }

    # ── Attach traceability ──────────────────────────────────────
    result["source_chunks"]   = [c[:300] for c in retrieved_chunks[:3]]
    result["is_follow_up"]    = strategy.is_follow_up
    result["strategy_reason"] = strategy.reason

    return result















# """
# question_service.py
# Orchestrates: retrieve → generate question → store traceability.
# """
# import json
# from typing import List, Optional

# from backend.core.config import TOP_K_RETRIEVE
# from backend.prompts.prompts import (
#     QUERY_CONSTRUCTION_PROMPT,
#     QUESTION_GENERATION_PROMPT,
# )
# from backend.services.llm_service import call_llm_json
# from backend.services.knowledge_service import (
#     load_faiss_for_role,
#     get_all_chunks_for_role,
# )

# from backend.rag_core.retrieval import multi_query_retrieve


# async def _build_retrieval_queries(
#     role: str,
#     experience_level: str,
#     skills: List[str],
#     domains: List[str],
#     projects: List[str],
#     previous_questions: List[str],

#     target_topic: str,
#     target_difficulty: str,

#     num_queries: int = 4,
# ) -> List[str]:
#     """
#     Use LLM to construct targeted retrieval queries
#     from resume profile while avoiding repetitive topics.
#     """

#     covered_topics = "\n".join(previous_questions[-5:])

#     prompt = QUERY_CONSTRUCTION_PROMPT.format(
#     role=role,
#     experience_level=experience_level,
#     skills=", ".join(skills[:8]),
#     domains=", ".join(domains[:5]),
#     projects=", ".join(projects[:5]),
#     previous_questions=covered_topics,

#     target_topic=target_topic,
#     target_difficulty=target_difficulty,

#     num_queries=num_queries,
# )

#     result = await call_llm_json(prompt)

#     if isinstance(result, list):
#         return result[:num_queries]

#     return (
#     projects[:2]
#     or skills[:2]
#     or [
#         f"{role} fundamentals",
#         f"{role} practical concepts"
#     ]
# )


# async def generate_next_question(
#     role: str,
#     experience_level: str,
#     skills: List[str],
#     domains: List[str],
#     projects: List[str],
#     previous_questions: List[str],
#     last_answer: Optional[str] = None,

#     strategy: str = "new_topic",
#     target_topic: str = "",
#     target_difficulty: str = "medium",

# ) -> dict:
#     """
#     Full pipeline:
#     1. Build retrieval queries from candidate profile
#     2. Retrieve relevant chunks from role knowledge base
#     3. Generate one targeted interview question
#     Returns structured question dict.
#     """

#     # ── Step 1: retrieval ───────────────────────────────────────

#     faiss_index = load_faiss_for_role(role)
#     all_chunks = get_all_chunks_for_role(role)

#     queries = await _build_retrieval_queries(
#     role,
#     experience_level,
#     skills,
#     domains,
#     projects,
#     previous_questions,

#     target_topic,
#     target_difficulty,
# )

#     retrieved_chunks: List[str] = []

#     for query in queries:

#         docs = multi_query_retrieve(
#             query,
#             faiss_index,
#             k=TOP_K_RETRIEVE,
#             all_chunks=all_chunks,
#             query_type="FACTUAL_QA",
#             experience_level=experience_level,
#         )

#         for d in docs:

#             text = (
#                 d.page_content
#                 if hasattr(d, "page_content")
#                 else str(d)
#             )

#             if text not in retrieved_chunks:
#                 retrieved_chunks.append(text)

#     # ── Diversity filter to avoid repeated semantic regions ─────

#     filtered_chunks = []

#     for chunk in retrieved_chunks:

#         chunk_lower = chunk.lower()

#         overlap = any(
#             prev.lower()[:50] in chunk_lower
#             for prev in previous_questions[-3:]
#         )

#         if not overlap:
#             filtered_chunks.append(chunk)

#     retrieved_chunks = filtered_chunks or retrieved_chunks

#     # ── Build context ────────────────────────────────────────────

#     context_text = "\n\n---\n\n".join(
#         retrieved_chunks[:8]
#     )

#     # ── Previous questions context ───────────────────────────────

#     prev_q_text = (
#         "\n".join(
#             f"{i+1}. {q}"
#             for i, q in enumerate(previous_questions[-5:])
#         )
#         if previous_questions
#         else "None yet."
#     )

#     # ── Step 2: generate question ───────────────────────────────

#     prompt = QUESTION_GENERATION_PROMPT.format(

#     role=role,

#     experience_level=experience_level,

#     skills=", ".join(skills[:8]),

#     domains=", ".join(domains[:5]),
#     projects=", ".join(projects[:5]),

#     context=context_text[:3000],

#     previous_questions=prev_q_text,

#     last_answer=last_answer or "No answer yet.",

#     strategy=strategy,

#     target_topic=target_topic,

#     target_difficulty=target_difficulty,
# )

#     result = await call_llm_json(
#         prompt,
#         temperature=0.3,
#     )

#     # ── Defaults / safety ───────────────────────────────────────

#     if not result or "question_text" not in result:

#         result = {
#             "question_text":
#                 f"Explain a core concept in {role} "
#                 f"that you've applied in a project.",

#             "question_type": "applied",
#             "topic": role,
#             "difficulty": "medium",
#             "is_follow_up": False,
#             "keywords_expected": [],
#             "source_chunk_preview": "",
#         }

#     # ── Traceability ─────────────────────────────────────────────

#     result["source_chunks"] = [
#         c[:300]
#         for c in retrieved_chunks[:3]
#     ]

#     return result