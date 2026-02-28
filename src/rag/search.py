"""
Module: src/rag/search.py
Purpose: Semantic, hybrid, and suggestion search over Qdrant.
"""

import re
import time

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from rapidfuzz import fuzz

from src.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    DEFAULT_TOP_K,
    HYBRID_KEYWORD_WEIGHT,
    SUGGESTION_COUNT,
    SCORE_THRESHOLD,
    EMBED_TEXT_MAX_CHARS,
)
from src.rag.embedder import embed_query
from src.scraper.schema import normalize_course_code

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client


_CODE_PATTERN = re.compile(r"\b([A-Z]{2,6})\s*(\d{4}[A-Z]?)\b")


def _extract_course_codes(query: str) -> list[str]:
    """Extract and normalize course codes found in a query string."""
    return [
        normalize_course_code(f"{m.group(1)}{m.group(2)}")
        for m in _CODE_PATTERN.finditer(query.upper())
    ]


def _direct_code_lookup(codes: list[str]) -> list[dict]:
    """Look up courses by exact course_code match in Qdrant."""
    if not codes:
        return []
    client = _get_client()
    results = []
    for code in codes:
        hits = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="course_code", match=MatchValue(value=code))]
            ),
            limit=1,
            with_payload=True,
        )[0]
        for hit in hits:
            results.append({"course": dict(hit.payload), "score": 1.0})
    return results


def _build_filter(department: str | None = None, source: str | None = None) -> Filter | None:
    """Build a Qdrant filter from optional department/source constraints."""
    conditions = []
    if department:
        conditions.append(FieldCondition(key="department", match=MatchValue(value=department)))
    if source:
        conditions.append(FieldCondition(key="source", match=MatchValue(value=source)))
    if conditions:
        return Filter(must=conditions)
    return None


def semantic_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    department: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Pure vector search with optional filters.

    Returns list of dicts with 'course' payload and 'score'.
    """
    client = _get_client()
    query_vector = embed_query(query)
    qfilter = _build_filter(department, source)

    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=qfilter,
        limit=top_k,
        score_threshold=SCORE_THRESHOLD,
        with_payload=True,
    )

    return [
        {"course": dict(hit.payload), "score": hit.score}
        for hit in results.points
    ]


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    department: str | None = None,
    source: str | None = None,
    keyword_weight: float = HYBRID_KEYWORD_WEIGHT,
) -> list[dict]:
    """Hybrid search: semantic retrieval + keyword reranking.

    1. If the query contains course codes, fetch them via direct payload lookup
    2. Retrieve 3*top_k candidates via semantic search (fast ANN lookup)
    3. Score each candidate with fuzzy keyword matching (O(3*k), not O(n))
    4. Fuse scores: final = (1 - kw_weight) * semantic + kw_weight * keyword
    5. Merge direct-lookup results to the front (guaranteed inclusion)

    Returns (results_list, timings_dict).
    """
    # Direct lookup for any course codes mentioned in the query
    t0 = time.time()
    codes = _extract_course_codes(query)
    direct = _direct_code_lookup(codes)
    direct_codes = {r["course"].get("course_code") for r in direct}
    direct_ms = round((time.time() - t0) * 1000, 1)

    # Over-fetch semantically for reranking headroom
    t1 = time.time()
    candidates = semantic_search(query, top_k=top_k * 3, department=department, source=source)
    semantic_ms = round((time.time() - t1) * 1000, 1)

    t2 = time.time()
    query_lower = query.lower()
    fused = []
    for r in candidates:
        # Skip duplicates already covered by direct lookup
        if r["course"].get("course_code") in direct_codes:
            continue
        text = r["course"].get("embedding_text", "")
        kw_score = fuzz.token_set_ratio(query_lower, text.lower()) / 100.0
        final = (1 - keyword_weight) * r["score"] + keyword_weight * kw_score
        fused.append({"course": r["course"], "score": round(final, 4)})

    fused.sort(key=lambda x: x["score"], reverse=True)
    rerank_ms = round((time.time() - t2) * 1000, 1)

    results = direct + fused[:top_k - len(direct)]
    timings = {
        "direct_lookup_ms": direct_ms,
        "semantic_ms": semantic_ms,
        "rerank_ms": rerank_ms,
    }
    return results, timings


def suggest_courses(
    main_results: list[dict],
    count: int = SUGGESTION_COUNT,
) -> list[dict]:
    """Find cross-disciplinary course suggestions based on main search results.

    Uses the top result's embedding vector to find similar courses from
    departments not already represented in the main results.
    """
    if not main_results:
        return []

    client = _get_client()

    # Collect departments already in main results to exclude
    seen_depts = {r["course"].get("department", "") for r in main_results}
    seen_codes = {r["course"].get("course_code", "") for r in main_results}

    # Use the top result's embedding_text to find similar courses
    top_text = main_results[0]["course"].get("embedding_text", "")
    if not top_text:
        return []

    query_vector = embed_query(top_text[:EMBED_TEXT_MAX_CHARS])

    # Exclude departments already in main results
    must_not = [
        FieldCondition(key="department", match=MatchValue(value=dept))
        for dept in seen_depts if dept
    ]

    qfilter = Filter(must_not=must_not) if must_not else None

    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=qfilter,
        limit=count + len(seen_codes),
        score_threshold=SCORE_THRESHOLD,
        with_payload=True,
    )

    suggestions = []
    for hit in results.points:
        code = hit.payload.get("course_code", "")
        if code not in seen_codes:
            suggestions.append({"course": dict(hit.payload), "score": hit.score})
        if len(suggestions) >= count:
            break

    return suggestions
