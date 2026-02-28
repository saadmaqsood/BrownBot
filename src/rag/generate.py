"""
Module: src/rag/generate.py
Purpose: Context assembly and Ollama LLM generation.
"""

import time
import requests
from src.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    EXPLORE_GAP_THRESHOLD,
    DESCRIPTION_MAX_CHARS,
)
from src.rag.search import hybrid_search, suggest_courses


def _is_exploratory(results: list[dict]) -> bool:
    """Determine query intent from the score distribution of search results.

    A large gap between the #1 and #2 scores means one dominant match
    (factual lookup, e.g. "Who teaches APMA 2680?").  A small gap means
    many similarly-relevant results (topic browsing, e.g. "courses about
    climate change") where cross-disciplinary suggestions add value.
    """
    if len(results) < 2:
        return False
    gap = results[0]["score"] - results[1]["score"]
    return gap < EXPLORE_GAP_THRESHOLD

SYSTEM_PROMPT = """You are a helpful academic advisor for Brown University. Answer the user's question
using ONLY the course information provided below. If the information is not in the context,
say so clearly. Be concise and specific. Reference course codes when mentioning courses.

When cross-disciplinary suggestions are provided, briefly mention 1-2 that might interest
the student based on their query, explaining why they could be relevant."""


def _format_context(results: list[dict], label: str = "Retrieved courses") -> str:
    """Format search results into a structured context block."""
    if not results:
        return f"{label}: None found.\n"
    lines = [f"{label}:"]
    for i, r in enumerate(results, 1):
        c = r["course"]
        lines.append(f"[{i}] {c.get('course_code', 'N/A')} - {c.get('title', 'N/A')}")
        if c.get("department"):
            lines.append(f"    Department: {c['department']}")
        if c.get("instructor"):
            lines.append(f"    Instructor: {c['instructor']}")
        if c.get("meeting_times"):
            lines.append(f"    Meeting Times: {c['meeting_times']}")
        if c.get("description"):
            desc = c["description"][:DESCRIPTION_MAX_CHARS] + "..." if len(c.get("description", "")) > DESCRIPTION_MAX_CHARS else c["description"]
            lines.append(f"    Description: {desc}")
        if c.get("prerequisites"):
            lines.append(f"    Prerequisites: {c['prerequisites']}")
        lines.append(f"    Source: {c.get('source', 'N/A')} | Relevance: {r.get('score', 0):.3f}")
        lines.append("")
    return "\n".join(lines)


def generate_answer(
    query: str,
    top_k: int = 5,
    department: str | None = None,
    source: str | None = None,
) -> dict:
    """Run hybrid search + suggestions + Ollama generation.

    Returns:
        dict with 'answer', 'courses', 'scores', 'suggestions', 'suggestion_scores',
        'retrieval_count'
    """
    t0 = time.time()
    results, search_timings = hybrid_search(query, top_k=top_k, department=department, source=source)
    search_ms = round((time.time() - t0) * 1000, 1)

    t1 = time.time()
    suggestions = suggest_courses(results) if _is_exploratory(results) else []
    suggest_ms = round((time.time() - t1) * 1000, 1)

    context = _format_context(results)
    suggestion_context = _format_context(suggestions, label="Cross-disciplinary suggestions")

    prompt = f"""Context:
{context}
{suggestion_context}

User question: {query}

Answer the question based on the context above."""

    t2 = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": OLLAMA_TEMPERATURE},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        answer = resp.json().get("response", "No response from LLM.")
    except requests.RequestException as e:
        answer = f"LLM generation failed: {e}. Here are the top matching courses based on the search results."
    llm_ms = round((time.time() - t2) * 1000, 1)

    timings = {
        **search_timings,
        "search_total_ms": search_ms,
        "suggest_ms": suggest_ms,
        "llm_ms": llm_ms,
    }

    return {
        "answer": answer,
        "courses": [r["course"] for r in results],
        "scores": [r["score"] for r in results],
        "suggestions": [r["course"] for r in suggestions],
        "suggestion_scores": [r["score"] for r in suggestions],
        "retrieval_count": len(results),
        "timings": timings,
    }
