# BrownBot - AI-Powered Brown University Course Search

A RAG (Retrieval-Augmented Generation) pipeline that scrapes Brown University course data from CAB and the Bulletin, indexes it in a vector database, and provides natural language search with cross-disciplinary course suggestions via a Streamlit UI.

## Architecture

```
Scrapers (CAB + Bulletin) -> Merged JSON -> Qdrant Vector DB
                                                  |
                                          E5-base-v2 embeddings
                                          (query:/passage:)
                                                  |
                                    FastAPI (async) -> Ollama LLM (Mistral)
                                                  |
                                             Streamlit UI
```

**Components:**
- **Scrapers**: Playwright (CAB) + requests/BeautifulSoup (Bulletin) with normalized course codes
- **Vector DB**: Qdrant with `intfloat/e5-base-v2` embeddings (768 dim, asymmetric query/passage prefixes)
- **Search**: Hybrid search (semantic retrieval + keyword reranking via rapidfuzz on the candidate set)
- **Suggestions**: Cross-disciplinary "Students exploring this also found" recommendations using embedding similarity across departments
- **LLM**: Ollama (Mistral) for answer generation
- **API**: Async FastAPI with `/query`, `/evaluate`, `/health` endpoints
- **Frontend**: Streamlit ("Brown University Forager") with expandable course cards, client-side department filtering, and suggestion section

## Quick Start (Docker)

```bash
# Start all services
docker-compose up --build

# Pull the LLM model (first time only)
docker exec -it brownbot-ollama-1 ollama pull mistral

# Run scraper (from host or inside api container)
docker exec -it brownbot-api-1 python scripts/run_scrape.py

# Ingest into Qdrant
docker exec -it brownbot-api-1 python scripts/run_ingest.py
```

Then visit:
- **Frontend**: http://localhost:8501
- **API docs**: http://localhost:8000/docs
- **Qdrant dashboard**: http://localhost:6333/dashboard

## Local Development

**Install dependencies:**
```bash
pip install -r requirements.txt
playwright install chromium
```

**Start Qdrant:**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**Start Ollama:**
```bash
ollama serve
ollama pull mistral
```

**Run scraper:**
```bash
python scripts/run_scrape.py
```

**Ingest into Qdrant:**
```bash
python scripts/run_ingest.py
```

**Start API:**
```bash
uvicorn src.api.main:app --reload
```

**Start frontend (separate terminal):**
```bash
streamlit run frontend/app.py
```

## Example Queries

- "Who teaches APMA2680, and when does the class meet?"
- "I am interested in Philosophy courses related to metaphysics. Which ones do you recommend?"
- "Find a Brown Bulletin course similar to CSCI0320 from CAB."
- "List all CAB courses taught on Fridays after 3 pm related to machine learning."
- "What ML courses are available?"

## Configuration

All settings are configurable via environment variables (see `src/config.py`):

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | localhost | Qdrant server host |
| `QDRANT_PORT` | 6333 | Qdrant server port |
| `OLLAMA_URL` | http://localhost:11434 | Ollama API URL |
| `OLLAMA_MODEL` | mistral | LLM model name |
| `OLLAMA_TEMPERATURE` | 0.3 | LLM sampling temperature |
| `OLLAMA_TIMEOUT` | 500 | LLM request timeout in seconds |
| `EMBEDDING_MODEL` | intfloat/e5-base-v2 | SentenceTransformer model |
| `DEFAULT_TOP_K` | 5 | Default number of results |
| `HYBRID_KEYWORD_WEIGHT` | 0.3 | Weight for keyword score in hybrid fusion (0=pure semantic, 1=pure keyword) |
| `SUGGESTION_COUNT` | 3 | Number of cross-disciplinary suggestions |
| `SCORE_THRESHOLD` | 0.65 | Minimum cosine similarity to include in results |
| `EXPLORE_GAP_THRESHOLD` | 0.25 | Score gap threshold for factual vs exploratory query detection |
| `DESCRIPTION_MAX_CHARS` | 500 | Max characters for description in LLM context |
| `EMBED_TEXT_MAX_CHARS` | 512 | Max characters for suggestion embedding input |
| `CAB_MAX_SCROLLS` | 30 | Maximum scroll iterations when loading CAB results |
| `CAB_SCROLL_PAUSE_MS` | 2000 | Pause between scroll iterations (ms) |
| `QDRANT_COLLECTION` | brown_courses | Qdrant collection name |
| `DATA_FILE` | data/courses.json | Path to merged course data |
| `API_URL` | http://localhost:8000 | API URL used by the Streamlit frontend |

## Design Decisions

- **intfloat/e5-base-v2**: Retrieval-tuned embedding model that uses `query:` and `passage:` prefixes for asymmetric search. 768 dimensions provide strong semantic resolution. Handles abbreviations (ML, AI, NLP) natively, unlike general-purpose models.
- **Hybrid search**: Semantic retrieval fetches 3x candidates, then keyword reranking with rapidfuzz scores the candidate set. This is O(3k) not O(n) — fast hybrid without scanning the full collection.
- **Cross-disciplinary suggestions**: After main retrieval, the top result's embedding text is re-embedded and used to find similar courses from other departments. This gives a "students who like X also take Y" effect emergent from the embedding space.
- **Qdrant**: Purpose-built vector DB with payload filtering and full-text indexing, eliminating need for a separate metadata store.
- **Deterministic IDs**: UUID5 from course_code ensures stable point IDs across ingestion runs, preventing duplicates if the pipeline is extended to support incremental upserts.
- **Async API**: All FastAPI endpoints are `async def` with blocking work offloaded via `asyncio.to_thread()`. This keeps the event loop free so `/health` and concurrent `/query` requests don't block each other during long LLM generation calls.
- **Union merge**: Both CAB and Bulletin courses are included. CAB provides schedule data (instructor, meeting times), Bulletin provides catalog data (descriptions, prerequisites). Courses in both get field-level merge with source="Both".

## Adding New Data Sources

1. Create a new scraper in `src/scraper/` returning `list[dict]` with fields from `schema.py`
2. Apply `normalize_course_code()` to all course codes
3. Add merge logic in `merged.py`
4. Re-run `run_scrape.py` and `run_ingest.py`
