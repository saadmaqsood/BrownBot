"""
Module: src/api/main.py
Purpose: FastAPI backend for BrownBot course search.
"""

import asyncio
import time
from collections import deque

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from src.config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION
from src.api.models import (
    QueryRequest,
    QueryResponse,
    CourseResult,
    HealthResponse,
    EvalResponse,
)
from src.api.logging_config import query_logger
from src.rag.generate import generate_answer

app = FastAPI(title="BrownBot", description="AI-powered Brown University course search")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory query log for /evaluate
_query_log: deque[dict] = deque(maxlen=1000)

# Shared Qdrant client for health checks (avoids new TCP connection per call)
_qdrant: QdrantClient | None = None


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Execute a natural language course query.

    Runs the blocking RAG pipeline in a thread so the async event loop
    stays free for concurrent requests and health checks.
    """
    start = time.time()

    try:
        result = await asyncio.to_thread(
            generate_answer,
            query=req.q,
            top_k=req.top_k,
            department=req.department,
            source=req.source,
        )
    except Exception as e:
        if "doesn't exist" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Course data not ingested yet. Run: python scripts/run_ingest.py",
            )
        raise HTTPException(status_code=500, detail=str(e))

    latency_ms = round((time.time() - start) * 1000, 1)

    courses = [CourseResult(**c) for c in result["courses"]]
    suggestions = [CourseResult(**c) for c in result.get("suggestions", [])]

    # Log query
    query_logger.info(
        f"q={req.q!r} | dept={req.department} | top_k={req.top_k} | "
        f"latency={latency_ms}ms | results={result['retrieval_count']}"
    )
    _query_log.append({"latency_ms": latency_ms, "retrieval_count": result["retrieval_count"]})

    return QueryResponse(
        answer=result["answer"],
        courses=courses,
        scores=result.get("scores", []),
        suggestions=suggestions,
        suggestion_scores=result.get("suggestion_scores", []),
        latency_ms=latency_ms,
        retrieval_count=result["retrieval_count"],
        timings=result.get("timings", {}),
    )


@app.get("/evaluate", response_model=EvalResponse)
async def evaluate():
    """Return average latency and retrieval stats from recent queries."""
    if not _query_log:
        return EvalResponse(total_queries=0, avg_latency_ms=0.0, avg_retrieval_count=0.0)

    total = len(_query_log)
    avg_lat = sum(q["latency_ms"] for q in _query_log) / total
    avg_ret = sum(q["retrieval_count"] for q in _query_log) / total

    return EvalResponse(
        total_queries=total,
        avg_latency_ms=round(avg_lat, 1),
        avg_retrieval_count=round(avg_ret, 1),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check with Qdrant collection info."""
    try:
        info = await asyncio.to_thread(
            _get_qdrant().get_collection, QDRANT_COLLECTION
        )
        return HealthResponse(
            status="ok",
            collection=QDRANT_COLLECTION,
            point_count=info.points_count,
        )
    except Exception as e:
        return HealthResponse(status=f"error: {e}")
