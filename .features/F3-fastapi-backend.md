# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 3 — FastAPI Backend Scaffold

### Requirement
Create a FastAPI backend server that the Chrome extension's background worker communicates with. The backend will be the orchestration layer for all RAG operations: chunking, embedding, retrieval, reranking, and LLM calls. It must handle CORS correctly so the extension can reach it.

### Acceptance Criteria
- The server runs locally on `http://localhost:8000`.
- `GET /health` returns `{ status: "ok" }`.
- `POST /ingest` accepts `{ text: string, sections: Array<{heading, charOffset}> }` and returns `{ doc_id: string, chunk_count: int }`.
- `POST /query` accepts `{ doc_id: string, query: string }` and returns `{ answer: string, citations: Array<{heading, snippet}> }` (stub response is fine at this stage).
- CORS is configured to allow requests from Chrome extension origins (`chrome-extension://*`).
- All endpoints validate input with Pydantic models and return structured error responses on failure.

### Implementation Plan
1. Create a Python project with `fastapi`, `uvicorn`, and `pydantic` as dependencies. Include a `requirements.txt`.
2. In `main.py`, configure `CORSMiddleware` to allow all origins (tighten later) and all standard HTTP methods.
3. Implement `GET /health` as a smoke-test endpoint.
4. Define Pydantic models: `IngestRequest`, `IngestResponse`, `QueryRequest`, `QueryResponse`.
5. Implement stub handlers for `POST /ingest` and `POST /query` that validate input and return hardcoded mock responses. Real logic is added in Features 4–7.
6. Add a simple in-memory store (`dict`) keyed by `doc_id` (a UUID generated at ingest time) to hold session state between ingest and query calls.