"""
Module: src/api/models.py
Purpose: Pydantic request/response schemas for the API.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    q: str = Field(..., description="Natural language query")
    department: str | None = Field(None, description="Filter by department code")
    source: str | None = Field(None, description="Filter by source: CAB, Bulletin, Both")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class CourseResult(BaseModel):
    course_code: str = ""
    title: str = ""
    instructor: str = ""
    meeting_times: str = ""
    prerequisites: str = ""
    department: str = ""
    description: str = ""
    source: str = ""


class QueryResponse(BaseModel):
    answer: str
    courses: list[CourseResult]
    scores: list[float] = []
    suggestions: list[CourseResult] = []
    suggestion_scores: list[float] = []
    latency_ms: float
    retrieval_count: int
    timings: dict[str, float] = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    collection: str = ""
    point_count: int = 0


class EvalResponse(BaseModel):
    total_queries: int
    avg_latency_ms: float
    avg_retrieval_count: float
