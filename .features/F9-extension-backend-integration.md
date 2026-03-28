# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 9 — Extension ↔ Backend Integration

### Requirement
Connect the Chrome extension frontend to the FastAPI backend. When the sidebar opens on a T&C page, it should automatically trigger ingestion and display the risk report. The sidebar must also support sending freeform questions to `POST /query` and displaying the structured answer with citations.

### Acceptance Criteria
- When the sidebar opens on a detected T&C page, the content script extracts the text and the background worker POSTs it to `POST /ingest` automatically, with no user action required.
- The sidebar shows a loading spinner during ingest and renders the risk dashboard once the response arrives.
- The user can type a question in an input field and press Enter or a Submit button to query.
- Query results render as: the answer text, followed by a collapsible list of citations (heading + snippet).
- All API calls include error handling: network errors show a user-facing message ("Could not reach TermsGPT backend — is the server running?").
- The backend URL is configurable via a constant in `background.js` (default: `http://localhost:8000`).

### Implementation Plan
1. In `content.js`, after extraction (Feature 2), send the result to `background.js` via `chrome.runtime.sendMessage({ type: "TC_EXTRACTED", payload })`.
2. In `background.js`, listen for `TC_EXTRACTED`. On receipt, POST to `http://localhost:8000/ingest` using `fetch`. Forward the response to the sidebar via `chrome.runtime.sendMessage({ type: "INGEST_COMPLETE", payload: riskReport })`.
3. In `sidebar.js`, listen for `INGEST_COMPLETE`. Render the risk dashboard from the received `risk_report` (Feature 10 handles the visual design).
4. Add a query input in `sidebar.html`. On submit, `sidebar.js` sends `{ type: "QUERY", doc_id, query }` to `background.js`, which calls `POST /query` and returns the result.
5. Handle all fetch errors in `background.js` with try/catch; forward error messages to the sidebar for display.