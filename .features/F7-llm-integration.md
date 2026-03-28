# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 7 — LLM Answer Generation with Citation Grounding

### Requirement
Use the Claude API to generate a grounded answer to the user's query, based exclusively on the top-5 reranked chunks. The response must include the answer in plain language and a list of citations — each citation pointing to the exact section heading and a short snippet that supports the answer.

### Acceptance Criteria
- `POST /query` returns `{ answer: string, citations: Array<{heading, snippet, relevance_score}> }`.
- The LLM is instructed via system prompt to only use information present in the provided chunks and to never hallucinate.
- Each factual claim in the answer corresponds to at least one citation.
- If no relevant chunks are found (all relevance scores below 0.3), the API returns `{ answer: "This document does not appear to cover that topic.", citations: [] }` without calling the LLM.
- The Claude model used is `claude-sonnet-4-20250514`.
- The full prompt (system + user) is logged in debug mode for inspection.

### Implementation Plan
1. Install the `anthropic` Python SDK. Load `ANTHROPIC_API_KEY` from `.env`.
2. Build the prompt:
   - **System:** `"You are a legal document analyst. Answer the user's question using only the provided document excerpts. For each claim, cite the section it comes from. If the excerpts do not contain enough information, say so explicitly."`
   - **User:** Format the top-5 chunks as a numbered list of `[Section: {heading}]\n{text}`, followed by `\nQuestion: {query}`. Ask for the answer in JSON: `{ "answer": "...", "citations": [{ "heading": "...", "snippet": "..." }] }`.
3. Parse the JSON response. If parsing fails, return the raw text as the answer with empty citations.
4. Add a relevance gate: if `max(relevance_scores) < 0.3`, skip the LLM call and return the no-coverage response.
5. Update `POST /query` to return the full structured response.