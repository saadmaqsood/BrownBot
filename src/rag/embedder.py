"""
Module: src/rag/embedder.py
Purpose: SentenceTransformer wrapper for course embedding using intfloat/e5-base-v2.

E5 models are trained for asymmetric retrieval and expect prefixes:
  - "query: " for search queries
  - "passage: " for documents/passages being indexed
"""

from sentence_transformers import SentenceTransformer
from src.config import EMBEDDING_MODEL

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def build_embedding_text(course: dict) -> str:
    """Build a single text string from course fields for embedding.

    Description is placed first (after code/title) so it carries the most
    semantic weight in the passage embedding.
    """
    parts = [
        course.get("course_code", ""),
        course.get("title", ""),
        course.get("description", ""),
        course.get("department", ""),
        course.get("instructor", ""),
        course.get("prerequisites", ""),
    ]
    return " ".join(p for p in parts if p)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of passage texts (for indexing)."""
    model = _get_model()
    prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed, show_progress_bar=True, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single query string (for search)."""
    model = _get_model()
    return model.encode(f"query: {text}", convert_to_numpy=True).tolist()
