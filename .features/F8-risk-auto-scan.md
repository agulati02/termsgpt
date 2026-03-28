# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 8 — Risk Taxonomy Auto-Scanner

### Requirement
When a T&C document is first ingested, automatically run a fixed set of pre-defined risk queries against the RAG pipeline. Return a structured risk report with a severity level (🔴 High / 🟡 Medium / 🟢 Low) and a one-sentence finding for each category.

### Acceptance Criteria
- `POST /ingest` response is extended to include a `risk_report` field alongside `doc_id` and `chunk_count`.
- The risk report covers exactly 6 categories: Data Selling, Arbitration Clause, Auto-Renewal, IP Ownership, Jurisdiction, and Deletion Rights.
- Each category entry includes: `{ category, severity, finding, citation }`.
- Severity is determined by the LLM based on the retrieved evidence, guided by a scoring rubric in the prompt.
- If a category is not mentioned in the document, its entry reads `{ severity: "🟢", finding: "Not mentioned in this document." }`.
- The full risk scan adds no more than 10 seconds of latency to the ingest endpoint (parallelise the 6 queries).

### Implementation Plan
1. Define a `RISK_TAXONOMY` constant: a list of 6 dicts, each with `{ category, query, rubric }`. Example rubric for Data Selling: `"High if data is sold to third parties. Medium if shared with partners. Low if only used internally."`.
2. Implement `run_risk_scan(doc_id) → List[RiskEntry]`: iterate over the taxonomy, calling the existing retrieval + rerank + LLM pipeline for each query.
3. Parallelise using `asyncio.gather` — all 6 queries run concurrently against the in-memory index.
4. Modify the LLM prompt for risk queries: instruct Claude to return `{ severity: "🔴|🟡|🟢", finding: "one sentence", citation: { heading, snippet } }` as JSON.
5. Attach the completed `risk_report` to the `POST /ingest` response.
6. Add a simple test: ingest a known T&C (e.g., a Reddit User Agreement snippet) and assert the arbitration category returns 🔴.