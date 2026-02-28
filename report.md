# BrownBot - Technical Report

## RAG Pipeline Overview

BrownBot implements a Retrieval-Augmented Generation pipeline for Brown University course search. The system ingests course data from two sources (CAB and Bulletin), embeds it into a vector space, and uses retrieved context to ground LLM-generated answers. It also provides cross-disciplinary course suggestions based on embedding similarity.

### Data Flow

1. **Scraping**: Playwright scrapes CAB (instructor, meeting times) and requests/BeautifulSoup scrapes Bulletin (descriptions, prerequisites)
2. **Merging**: Field-level merge on normalized course codes. Courses in both sources get combined metadata with `source="Both"`. Both CAB-only and Bulletin-only courses are retained.
3. **Embedding**: Each course is embedded as a concatenation of its fields using `intfloat/e5-base-v2` with `passage:` prefix for documents
4. **Indexing**: Embeddings + full payloads stored in Qdrant with payload indexes on `department`, `source`, and full-text on `embedding_text`
5. **Search**: Hybrid search — semantic retrieval fetches 3x candidates, then keyword reranking with rapidfuzz scores the candidate set (O(3k), not O(n))
6. **Suggestions**: Top result's embedding vector finds similar courses from other departments for cross-disciplinary recommendations
7. **Generation**: Top-k courses + suggestions formatted as context, sent to Ollama (Mistral) with a constraining system prompt

## Embedding Model Choice: intfloat/e5-base-v2

Selected over `all-MiniLM-L6-v2` and other candidates for three reasons:

**Asymmetric vs symmetric retrieval.** MiniLM is a symmetric model — it embeds both queries and documents in the same space. This works for sentence similarity but breaks down for search, where a short query ("What ML courses?") and a long document ("CSCI 1420 Machine Learning: This course covers supervised and unsupervised learning...") occupy fundamentally different roles. E5 is trained for asymmetric retrieval with explicit `query:` and `passage:` prefixes, so the model learns that a query is an *intent* and a passage is a *candidate answer*.

**The abbreviation problem.** During development, MiniLM consistently failed on abbreviation queries. Testing showed that MiniLM maps "ML" closer to "Mathematics" (cosine 0.51) than "Machine Learning" (cosine 0.31) — the top-5 results for "ML courses" were all irrelevant. This is a known limitation of symmetric models: short tokens like "ML" lack enough surrounding context to disambiguate. E5's instruction-tuned training resolves common abbreviations natively, and the hybrid search with keyword reranking provides a second pass for cases where semantic search alone isn't enough.

**768 dimensions.** Higher semantic resolution than 384-dim models. For a corpus with nuanced academic descriptions, this captures finer-grained distinctions between related courses.

**Trade-off:** ~2x the storage and embedding time vs MiniLM, but retrieval quality improvement is dramatic — relevant courses jump from sub-0.35 scores to 0.5+ scores. Even with this improvement, abbreviations remain the hardest case for pure semantic search. Production mitigations would include query expansion (mapping "ML" → "Machine Learning"), synonym dictionaries, and cross-encoder reranking.

## Vector Store Choice: Qdrant over FAISS

FAISS is a strong choice for pure vector similarity — it's fast and battle-tested. However, this project needs more than raw ANN search:

- **Built-in payload filtering.** The `/query` endpoint supports filtering by department and source. With FAISS, this requires either post-filtering (search all, then discard non-matching results — wasteful and breaks top-k counts) or maintaining separate FAISS indexes per filter combination (combinatorial explosion). Qdrant applies filters *during* the ANN search natively via payload indexes.
- **Full-text indexing.** Qdrant's `TextIndexParams` provides built-in keyword indexing on the `embedding_text` field, supporting the hybrid search strategy without an external search engine like Elasticsearch.
- **Metadata storage.** Each Qdrant point carries its full course payload (instructor, meeting times, description, etc.) alongside the vector. FAISS stores only vectors and integer IDs — you'd need a separate store (SQLite, a dict, a JSON file) to map IDs back to course metadata, adding a synchronization concern.
- **Lower operational overhead.** Qdrant runs as a single Docker container with persistent storage, a REST API, and a built-in dashboard for debugging. FAISS requires manual serialization/deserialization of indexes and has no built-in persistence or API layer.

The trade-off is that Qdrant adds a network hop and a running service, while FAISS is in-process. For this project's scale (~2000 courses), FAISS's raw speed advantage is negligible, and Qdrant's features reduce the amount of infrastructure code needed significantly.

## Hybrid Search Strategy

Semantic search and keyword search fail in complementary ways:

- **Semantic search** understands meaning but not exact words. Each course is embedded as a 768-dimensional vector; courses about similar topics cluster together. A query like "machine learning courses" finds courses about statistical pattern recognition even if those words never appear. But searching for "CSCI 1470" may rank a semantically similar but different course higher, and short abbreviations like "ML" can match the wrong topic entirely.
- **Keyword search** understands exact words but not meaning. It matches "CSCI 1470" perfectly and catches "Friday" in meeting times. But "machine learning courses" won't find a course that describes the same concepts using different terminology.

The hybrid approach combines both via candidate-set reranking:

1. **Semantic pass** — Retrieve 3x top_k candidates from Qdrant via ANN vector search. This casts a wide net based on meaning.
2. **Keyword pass** — Score each candidate with `rapidfuzz.token_set_ratio` against the original query text. This measures how much the actual words overlap.
3. **Score fusion** — Combine both signals: `final = (1 - w) * semantic + w * keyword`, default `w = 0.3`. Courses that are both semantically relevant and contain matching keywords rank highest.

This is O(3k) not O(n) — keyword scoring runs only on the small candidate set from step 1, not the full collection. The approach gets semantic understanding and keyword precision without the cost of scanning every course for text matches.

## Score Threshold Calibration

Empirical testing across query types revealed a consistent boundary between relevant and irrelevant results:

| Query type | Relevant scores | Irrelevant scores |
|---|---|---|
| Broad topic ("Economics courses") | 0.70–0.76 | — |
| Specific topic ("Greek philosophy") | 0.69–0.83 | — |
| Abbreviation ("ML on Fridays") | — | 0.64–0.67 |
| Course code ("CSCI 0320") | 0.68–1.00 | — |

The gap is consistent: relevant results score 0.68+, irrelevant noise tops out at ~0.67. The score threshold is set to 0.65 to provide a small margin while filtering out clearly irrelevant matches.

## Cross-Disciplinary Suggestions

After the main retrieval, the system finds "You Might Also Like" courses:
1. Takes the top result's embedding text
2. Queries Qdrant for similar courses, excluding departments already in the main results
3. Returns top 3 cross-disciplinary matches

**When to show suggestions:** Not every query benefits from cross-disciplinary recommendations. A factual lookup like "Who teaches APMA 2680?" has one clear answer — suggestions would be noise. A topic exploration like "courses about climate change" has many similarly-relevant results — suggestions add value.

The system detects this from the score distribution: if the gap between the #1 and #2 result scores exceeds 0.25, the query has a dominant match (factual) and suggestions are suppressed. Below that threshold, scores are clustered (exploratory) and suggestions are shown. The threshold was lowered from 0.30 to 0.25 after observing that specific course-code queries (e.g., "Who teaches APMA 2680?") had gaps just under 0.30 due to closely-scored related results, incorrectly triggering suggestions.

This creates emergent personality-based recommendations — courses with similar descriptions cluster in embedding space, so a student interested in "machine learning" might see suggestions from Applied Math, Engineering, or Public Health that cover related methods from different angles.

## Performance Observations

- **Ingestion**: ~2000 courses embed and index in under 60 seconds on CPU with E5-base-v2
- **Search latency**: Semantic search returns in <100ms. Hybrid reranking adds negligible overhead (fuzzy matching on 15 candidates)
- **Suggestion latency**: One additional Qdrant query, <50ms
- **LLM generation**: Ollama/Mistral on CPU dominates total latency at ~60-120 seconds per query

## Production Improvements

1. **GPU acceleration**: Run Ollama with GPU passthrough to reduce LLM generation from ~120s to ~2-5s
2. **Streaming**: Stream LLM responses to the frontend for better perceived latency
3. **Query expansion**: Map common abbreviations ("ML" → "Machine Learning", "AI" → "Artificial Intelligence") before embedding. This addresses the remaining gap where even E5 struggles with very short ambiguous tokens.
4. **Caching**: Add Redis cache for frequent queries to avoid redundant LLM calls
5. **LLM-powered extraction**: Replace brittle CSS selectors with [Google's LangExtract](https://github.com/google/langextract) for the scraping layer. LangExtract uses LLMs to extract structured data from unstructured text with source grounding — each extracted field maps back to its exact location in the source HTML. This would make the scrapers resilient to markup changes on CAB and the Bulletin, and the grounding traces provide auditability for data quality.
6. **Incremental updates**: Delta ingestion instead of full recreate; track last-scraped timestamps
7. **Fine-tuned embeddings**: Fine-tune E5 on academic course description pairs for domain-specific similarity
8. **Cross-encoder reranking**: Add a cross-encoder step between retrieval and generation for precision
9. **Evaluation**: Automated eval with ground-truth Q&A pairs; track MRR and answer faithfulness
10. **Auth & rate limiting**: Add API key auth and rate limits for production deployment
11. **Monitoring**: Prometheus metrics for latency percentiles, error rates, and cache hit rates
