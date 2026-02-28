"""
Module: src/config.py
Purpose: Central configuration with environment variable overrides.
"""

import os

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "brown_courses")

# Embedding model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/e5-base-v2")
EMBEDDING_DIM = 768  # dimension for e5-base-v2

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Ollama generation
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "500"))  # seconds

# Search
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.3"))
SUGGESTION_COUNT = int(os.getenv("SUGGESTION_COUNT", "3"))

# Minimum cosine similarity to include in results.
# Empirically: relevant results score >=0.68, noise tops out at ~0.67.
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.65"))

# If the gap between the #1 and #2 result scores exceeds this threshold,
# the query has one clear answer (factual) — skip cross-disciplinary suggestions.
# Below the threshold, scores are clustered (exploratory) — show suggestions.
# Lowered from 0.30 to 0.25: course-code queries had gaps just under 0.30.
EXPLORE_GAP_THRESHOLD = float(os.getenv("EXPLORE_GAP_THRESHOLD", "0.25"))

# Maximum characters to keep when truncating fields for context/embedding
DESCRIPTION_MAX_CHARS = int(os.getenv("DESCRIPTION_MAX_CHARS", "500"))
EMBED_TEXT_MAX_CHARS = int(os.getenv("EMBED_TEXT_MAX_CHARS", "512"))

# CAB scraper scroll tuning
CAB_MAX_SCROLLS = int(os.getenv("CAB_MAX_SCROLLS", "30"))
CAB_SCROLL_PAUSE_MS = int(os.getenv("CAB_SCROLL_PAUSE_MS", "2000"))

# Data
DATA_FILE = os.getenv("DATA_FILE", "data/courses.json")

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_URL = os.getenv("API_URL", "http://localhost:8000")
