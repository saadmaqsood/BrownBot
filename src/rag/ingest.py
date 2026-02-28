"""
Module: src/rag/ingest.py
Purpose: Load courses.json into Qdrant with vector embeddings.
"""

import json
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
)

from src.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    EMBEDDING_DIM,
    DATA_FILE,
)
from src.rag.embedder import build_embedding_text, embed_texts


def _deterministic_id(course_code: str) -> str:
    """Generate a deterministic UUID5 from course_code for idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, course_code))


def ingest(data_file: str = DATA_FILE, batch_size: int = 256):
    """Ingest courses from JSON into Qdrant."""
    with open(data_file, "r") as f:
        courses = json.load(f)

    print(f"Loaded {len(courses)} courses from {data_file}")

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Recreate collection
    if client.collection_exists(QDRANT_COLLECTION):
        client.delete_collection(QDRANT_COLLECTION)

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    # Create payload indexes for filtered search
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="course_code",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="department",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="source",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    # Full-text index on embedding_text for keyword search
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="embedding_text",
        field_schema=TextIndexParams(
            type=TextIndexType.TEXT,
            tokenizer=TokenizerType.WORD,
            lowercase=True,
        ),
    )

    # Build embedding texts
    embedding_texts = [build_embedding_text(c) for c in courses]

    # Batch embed and upsert
    for i in range(0, len(courses), batch_size):
        batch_courses = courses[i : i + batch_size]
        batch_texts = embedding_texts[i : i + batch_size]

        vectors = embed_texts(batch_texts)

        points = []
        for j, course in enumerate(batch_courses):
            code = course.get("course_code", f"unknown_{i+j}")
            point_id = _deterministic_id(code)
            payload = {**course, "embedding_text": batch_texts[j]}
            points.append(PointStruct(id=point_id, vector=vectors[j], payload=payload))

        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        print(f"  Upserted batch {i // batch_size + 1} ({len(points)} points)")

    count = client.count(collection_name=QDRANT_COLLECTION).count
    print(f"Ingestion complete. {count} points in '{QDRANT_COLLECTION}'")
    return count


if __name__ == "__main__":
    ingest()
