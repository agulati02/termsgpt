# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 5 — Hybrid Retrieval (BM25 + Vector Search)

### Requirement
Implement hybrid retrieval over the document chunks: a BM25 sparse retriever for exact keyword matching, a dense vector retriever using OpenAI embeddings, and a Reciprocal Rank Fusion (RRF) merger to combine both result lists into a single ranked set.

### Acceptance Criteria
- `POST /ingest` embeds all chunks via the OpenAI `text-embedding-3-small` model and stores vectors in an in-memory store keyed by `doc_id`.
- A BM25 index is also built at ingest time from the same chunks.
- `POST /query` performs both BM25 and vector retrieval for the given query and returns the top-10 merged chunks ranked by RRF score.
- RRF is implemented as: `score(d) = Σ 1 / (k + rank(d))` where `k=60`, summed across both ranker lists.
- The combined retrieval outperforms either method alone on at least 2 manually tested queries involving legal jargon (e.g., "indemnification", "governing law").
- OpenAI API key is loaded from an `.env` file and never hardcoded.

### Implementation Plan
1. Install `openai`, `rank_bm25`, `numpy`, and `python-dotenv`.
2. On `POST /ingest`, call `openai.embeddings.create(model="text-embedding-3-small", input=[chunk.text for chunk in chunks])` and store the resulting vectors in a dict `{ doc_id: { chunk_id: vector } }`.
3. Build a `BM25Okapi` index from the tokenised chunk texts; store it in the same session dict.
4. Implement `bm25_search(query, index, chunks, top_k=20) → List[(chunk, rank)]`.
5. Implement `vector_search(query_embedding, vectors, chunks, top_k=20) → List[(chunk, rank)]` using numpy cosine similarity.
6. Implement `reciprocal_rank_fusion(bm25_results, vector_results, k=60) → List[chunk]`.
7. On `POST /query`, embed the query, run both retrievers, fuse results, return top-10 chunks. Update the stub response to include real retrieved chunks.