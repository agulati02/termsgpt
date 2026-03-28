# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 4 — Semantic Chunking Pipeline

### Requirement
Implement a section-aware semantic chunker in the FastAPI backend. Instead of splitting text by fixed token counts, the chunker must respect the logical structure of the T&C document — splitting at section boundaries first, then by size if a section is too large.

### Acceptance Criteria
- Given a T&C body text and its section headings array, the chunker produces a list of chunks where each chunk includes: `{ chunk_id, text, heading, token_count }`.
- No chunk exceeds 512 tokens.
- Each chunk preserves the heading of the section it belongs to as metadata.
- If a section body exceeds 512 tokens, it is split at sentence boundaries (not mid-sentence) into sub-chunks, each inheriting the parent heading.
- Chunks have a 50-token overlap with their neighbours to preserve context across boundaries.
- The chunker is a pure function (no side effects) and is covered by at least 3 unit tests.

### Implementation Plan
1. Install `tiktoken` (for token counting) and `nltk` or `spacy` (for sentence tokenisation).
2. Write `chunk_by_sections(text, sections, max_tokens=512, overlap=50)`:
   - Use the `charOffset` values from the sections array to slice the body text into per-section strings.
   - For each section, tokenise into sentences using `nltk.sent_tokenize`.
   - Greedily pack sentences into chunks up to `max_tokens`. When a chunk is full, start a new one and prepend the last `overlap` tokens from the previous chunk.
   - Tag each chunk with its parent `heading`.
3. Return a list of `Chunk` dataclass instances.
4. Wire into `POST /ingest`: call the chunker, store chunks in the in-memory session dict under the `doc_id`.
5. Write unit tests: (a) single short section → one chunk; (b) long section → multiple overlapping chunks; (c) multiple sections → chunks correctly labelled.