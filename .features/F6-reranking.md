# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 6 — Cross-Encoder Reranking

### Requirement
After hybrid retrieval returns a candidate set of 10 chunks, apply a cross-encoder reranker to re-score them based on relevance to the query. This replaces the bi-encoder approximate ranking with a more precise relevance score before the final LLM call.

### Acceptance Criteria
- The top-10 chunks from Feature 5 are passed through a reranker before being sent to the LLM.
- Reranking uses the Cohere Rerank API (`cohere.rerank`) with model `rerank-english-v3.0`.
- The reranker returns a re-ordered list of the top-5 most relevant chunks with their relevance scores.
- If the Cohere API is unavailable or returns an error, the system gracefully falls back to the original RRF-ranked order and logs a warning.
- Reranker latency is logged to stdout for performance monitoring.
- Cohere API key is loaded from `.env`.

### Implementation Plan
1. Install the `cohere` Python SDK.
2. Implement `rerank_chunks(query, chunks, top_n=5) → List[RankedChunk]`:
   - Call `co.rerank(query=query, documents=[c.text for c in chunks], top_n=top_n, model="rerank-english-v3.0")`.
   - Map results back to the original `Chunk` objects by index.
   - Return a list of `RankedChunk(chunk, relevance_score)`.
3. Wrap the call in a try/except; on failure, log `"Reranker unavailable, using RRF order"` and return the original top-5 from RRF.
4. Add timing with `time.perf_counter()` and log `f"Reranker latency: {elapsed:.2f}s"`.
5. Insert the reranker call into the `POST /query` handler between retrieval and LLM call.