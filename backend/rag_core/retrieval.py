
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
from langchain_core.documents import Document
from backend.rag_core.embeddings import reranker_model
_tfidf_cache = {}
def keyword_retrieve(question: str, all_chunks: list, k: int = 10) -> list:
    if not all_chunks:
        return []
    try:
        cache_key = len(all_chunks)

        if cache_key in _tfidf_cache:

            vectorizer, tfidf_matrix = _tfidf_cache[cache_key]

        else:

            vectorizer = TfidfVectorizer(
                stop_words=list(_get_dynamic_stopwords())
            )

            tfidf_matrix = vectorizer.fit_transform(all_chunks)

            _tfidf_cache[cache_key] = (
                vectorizer,
                tfidf_matrix
            )
        q_vec        = vectorizer.transform([question])
        scores       = sklearn_cosine(q_vec, tfidf_matrix).flatten()
        top_indices  = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(Document(
                    page_content=all_chunks[idx],
                    metadata={"chunk_id": int(idx), "keyword_score": float(scores[idx])}
                ))
        print(f"[KeywordSearch] '{question[:50]}' → {len(results)} chunks | "
              f"top score={scores[top_indices[0]]:.3f}")
        return results
    except Exception as e:
        print(f"[KeywordSearch] error: {e}")
        return []

def _get_dynamic_stopwords(chunks: list = None) -> set:
    """
    If chunks are provided, derive stopwords from the corpus:
    words appearing in >70% of chunks are document-level noise.
    Falls back to a minimal universal function-word set.
    """
    base = {
        "what", "which", "who", "where", "when", "why", "how",
        "is", "are", "was", "were", "be", "been", "the", "a", "an",
        "of", "in", "on", "at", "to", "for", "and", "or", "but",
        "this", "that", "it", "its", "do", "did", "does", "has",
        "have", "had", "will", "would", "could", "should", "with",
        "from", "by", "if", "not", "tell", "me", "give", "about",
    }
    return base
def exact_match_retrieve(question: str, all_chunks: list) -> list:
    if not all_chunks:
        return []

    number_patterns = re.findall(r'\b\d+\b', question)
    stopwords = _get_dynamic_stopwords()
    key_words = [w.lower() for w in question.split()
                 if len(w) > 2 and w.lower() not in stopwords]

    matched = []
    seen    = set()

    for i, chunk in enumerate(all_chunks):
        chunk_lower = chunk.lower()
        score = 0

        for num in number_patterns:
            if re.search(rf'\b{num}\b', chunk_lower):
                score += 3

            # TITLE BOOST: number AND at least one content keyword
            # both appear in the first line.
            # Requiring co-occurrence prevents single-digit false positives
            # (e.g. "3" matching page numbers, dates, list items everywhere).
            first_line = chunk.strip().split('\n')[0].lower()
            num_in_first_line = bool(re.search(rf'\b{num}\b', first_line))
            kw_in_first_line  = any(kw in first_line for kw in key_words)

            if num_in_first_line and kw_in_first_line:
                score += 5
                print(f"[ExactMatch] Title boost: chunk {i} "
                      f"(num={num} + keyword co-occur in first line)")

        for word in key_words:
            if word in chunk_lower:
                score += 1

        if score > 0:
            fingerprint = chunk[:120].strip()
            if fingerprint not in seen:
                seen.add(fingerprint)
                matched.append((score, Document(
                    page_content=chunk,
                    metadata={"chunk_id": i, "exact_score": score}
                )))

    matched.sort(key=lambda x: x[0], reverse=True)

    if not matched:
        return []

    top_score  = matched[0][0]
    gap_cutoff = top_score * 0.5
    filtered   = [(s, d) for s, d in matched if s >= gap_cutoff]
    results    = [d for _, d in filtered[:8]]

    if results:
        print(f"[ExactMatch] '{question[:50]}' → {len(results)} exact chunks | "
              f"top score={matched[0][0]}")
    return results
# ============================================================
# Cross-encoder reranking
# ============================================================

def rerank_docs(
    query: str,
    docs: list,
    top_k: int = 5,
):

    if not docs:
        return []

    pairs = [
        (query, d.page_content)
        for d in docs
    ]

    scores = reranker_model.predict(pairs)

    ranked = sorted(
        zip(scores, docs),
        key=lambda x: x[0],
        reverse=True,
    )

    return [
        d
        for _, d in ranked[:top_k]
    ]
def chunk_complexity_score(text: str) -> int:

    text = text.lower()

    architecture_signals = [
        "distributed",
        "scalability",
        "orchestration",
        "enterprise",
        "microservices",
        "fault tolerance",
        "high availability",
        "cloud migration",
        "multi-region",
        "petabyte",
    ]

    practical_signals = [
        "implementation",
        "example",
        "debug",
        "training",
        "dataset",
        "python",
        "model",
        "preprocessing",
        "feature",
        "inference",
    ]

    score = 0

    for term in practical_signals:
        if term in text:
            score += 2

    for term in architecture_signals:
        if term in text:
            score -= 2

    return score
def multi_query_retrieve(question: str, faiss_index, k: int = 12,
                         all_chunks: list = None,
                         query_type: str = "FACTUAL_QA",
                         queries: list = None,
                         experience_level: str = "mid") -> list:
    seen_weights: dict = {}
    chunk_map:    dict = {}

    all_queries = queries if queries else [question]
    print(f"[Hybrid] {len(all_queries)} queries: {all_queries}")

    # per_q_k = max(6, k // len(all_queries))
    # 🔥 ADAPTIVE RETRIEVAL LOGIC
    if query_type == "FACTUAL_QA":
        k = 8
        per_q_k = max(3, k // len(all_queries))

    elif query_type == "MULTIPART_QA":
        k = 12
        per_q_k = max(5, k // len(all_queries))

    elif query_type == "FULL_SUMMARY":
        k = 15
        per_q_k = max(6, k // len(all_queries))

    else:
        k = max(k, 10)
        per_q_k = max(4, k // len(all_queries))
    for q in all_queries:
        try:
            docs = faiss_index.similarity_search(q, k=per_q_k)
            for d in docs:
                key = d.page_content[:120].strip()
                seen_weights[key] = max(seen_weights.get(key, 0), 0.6)
                chunk_map[key]    = d
        except Exception as e:
            print(f"[Hybrid] semantic error for '{q}': {e}")

    print(f"[Hybrid] {len(seen_weights)} unique chunks after semantic")

    if all_chunks:
        try:
            exact_docs = exact_match_retrieve(question, all_chunks)
            for d in exact_docs:
                key = d.page_content[:120].strip()
                seen_weights[key] = max(seen_weights.get(key, 0), 0.6)
                chunk_map[key]    = d
            if exact_docs:
                print(f"[Hybrid] {len(exact_docs)} exact-match chunks boosted to 0.6")
        except Exception as e:
            print(f"[Hybrid] exact match error: {e}")

    if all_chunks:
        try:
            kw_docs = keyword_retrieve(question, all_chunks, k=8)
            for d in kw_docs:
                key = d.page_content[:120].strip()
                seen_weights[key] = max(seen_weights.get(key, 0), 0.3)
                chunk_map[key]    = d
        except Exception as e:
            print(f"[Hybrid] keyword error: {e}")

    print(f"[Hybrid] {len(seen_weights)} total unique chunks across all signals")

    sorted_keys = sorted(seen_weights.keys(),
                         key=lambda x: seen_weights[x],
                         reverse=True)

    final_docs = [chunk_map[key] for key in sorted_keys[:k]]
    if experience_level in ["junior", "mid"]:

        final_docs = sorted(
            final_docs,
            key=lambda d: chunk_complexity_score(
                d.page_content
            ),
            reverse=True,
        )

    if len(final_docs) < k:
        try:
            seen_set = set(seen_weights.keys())
            mmr_docs = faiss_index.max_marginal_relevance_search(
                question, k=k, fetch_k=k * 3)
            for d in mmr_docs:
                key = d.page_content[:120].strip()
                if key not in seen_set:
                    final_docs.append(d)
                    seen_set.add(key)
            print(f"[Hybrid] After MMR fallback: {len(final_docs)} chunks")
        except Exception as e:
            print(f"[Hybrid] MMR fallback error: {e}")

    top_weight = seen_weights.get(sorted_keys[0], 0) if sorted_keys else 0

    print(f"[Hybrid] Final pool: {len(final_docs)} chunks | "
      f"top weight={top_weight:.1f}")

    # ============================================================
    # Final reranking
    # ============================================================

    final_docs = rerank_docs(
        question,
        final_docs,
        top_k=k,
    )

    return final_docs[:k]























