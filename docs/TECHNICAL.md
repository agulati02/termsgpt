# Technical Details

---

## Technology Stack

### Backend

| Component | Technology | Version |
|-----------|-----------|---------|
| Web Framework | FastAPI | 0.115.12 |
| ASGI Server | Uvicorn | 0.34.0 |
| Data Validation | Pydantic | 2.11.1 |
| LLM (Primary) | Anthropic Claude API (claude-sonnet-4) | SDK ≥0.50.0 |
| LLM (Fallback) | OpenAI API | SDK 1.75.0 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | ≥3.0.0 |
| Sparse Retrieval | rank-bm25 (BM25Okapi) | 0.2.2 |
| Reranking | Cohere Rerank API (rerank-english-v3.0) | SDK ≥5.0.0 |
| Tokenization | tiktoken (cl100k_base) | 0.9.0 |
| NLP Utilities | NLTK | 3.9.1 |
| Numerical Compute | NumPy | 2.2.4 |
| Configuration | python-dotenv | 1.1.0 |
| Language | Python | 3.8+ |

### Browser Extension

| Component | Technology | Version |
|-----------|-----------|---------|
| Manifest Version | Chrome Manifest V3 | — |
| Content Extraction | @mozilla/readability | 0.6.0 |
| Build Tool | esbuild | 0.18.0 |
| Language | JavaScript (ES2020+) | — |
| Browser APIs | Chrome sidePanel, scripting, tabs | — |

---

## Directory Structure

```
termsgpt/
├── backend/                    # Python FastAPI backend service
│   ├── main.py                 # FastAPI application, CORS config, route handlers
│   ├── llm.py                  # Claude API integration and answer generation
│   ├── models.py               # Pydantic request/response schemas
│   ├── chunker.py              # Section-aware semantic text chunking
│   ├── retrieval.py            # Hybrid RAG: BM25, vector search, RRF fusion
│   ├── reranker.py             # Cross-encoder reranking (Cohere + fallback)
│   ├── risk_scanner.py         # Automated 6-category risk taxonomy scanning
│   ├── store.py                # In-memory session store (keyed by doc_id)
│   ├── requirements.txt        # Python dependency specifications
│   ├── .env.example            # Template for required environment variables
│   └── tests/
│       └── test_chunker.py     # Unit tests for the chunker module
│
├── extension/                  # Chrome browser extension
│   ├── manifest.json           # Extension configuration and permission declarations
│   ├── background.js           # Service worker: orchestration and state management
│   ├── content.js              # Content script: T&C detection and text extraction
│   ├── sidebar.html            # Side panel UI markup and styles
│   ├── sidebar.js              # Side panel logic: rendering, chat, state transitions
│   ├── package.json            # Node.js dev dependencies and build scripts
│   └── dist/
│       └── content.js          # esbuild-bundled content script (served to browser)
│
├── docs/                       # Project documentation
│   ├── DESCRIPTION.md          # Problem statement, solution, and project scope
│   ├── TECHNICAL.md            # This file: stack, architecture, and internals
│   ├── USAGE.md                # Setup and usage guide for local development
│   └── FUTURE.md               # Planned improvements and future roadmap
│
└── README.md                   # Project overview and entry point
```

---

## Browser Extension

### Architecture Overview

The extension follows a three-component Manifest V3 architecture:

```
┌──────────────────────────────────────────────────────────────┐
│  Chrome Browser                                              │
│                                                              │
│  ┌─────────────────┐       ┌────────────────────────────-┐   │
│  │  Content Script │◄────► │  Background Service Worker  │   │
│  │  (content.js)   │       │     (background.js)         │   │
│  │                 │       │                             │   │
│  │ - T&C detection │       │ - Tab state management      │   │
│  │ - Readability   │       │ - /ingest and /query calls  │   │
│  │   extraction    │       │ - Message routing           │   │
│  │ - charOffset    │       │ - Icon click → sidePanel    │   │
│  │   mapping       │       └────────────┬───────────────-┘   │
│  │ - Scroll handler│                    │                    │
│  └─────────────────┘      ┌────────────-▼───────────────┐    │
│                           │      Sidebar Panel          │    │
│                           │ (sidebar.html / sidebar.js) │    │
│                           │                             │    │
│                           │ - Risk dashboard UI         │    │
│                           │ - Chat interface            │    │
│                           │ - State transitions         │    │
│                           └────────────────────────────-┘    │
└──────────────────────────────────────────────────────────────┘
```

### State Machine

The extension manages four states per browser tab:

| State | Trigger | Display |
|-------|---------|---------|
| `EXTRACTING` | Tab loads a detected T&C page | Spinner: "Extracting page content…" |
| `LOADING` | Backend `/ingest` call in progress | Spinner: "Analysing terms…" |
| `READY` | Risk report received and cached | Risk dashboard + chat input |
| `ERROR` / `NOT_TC_PAGE` | Backend error or non-T&C page | Error message or inactive state |

### Message Protocol

All inter-component communication uses Chrome's `chrome.runtime.sendMessage` / `chrome.tabs.sendMessage` APIs:

| Message Type | Direction | Payload |
|--------------|-----------|---------|
| `TC_EXTRACTED` | content → background | `{ text, sections[] }` |
| `INGEST_LOADING` | background → sidebar | — |
| `INGEST_COMPLETE` | background → sidebar | `{ doc_id, risk_report[] }` |
| `INGEST_ERROR` | background → sidebar | `{ error }` |
| `QUERY` | sidebar → background | `{ doc_id, query }` |
| `QUERY_RESPONSE` | background → sidebar | `{ answer, citations[] }` |
| `SCROLL_TO` | sidebar → background → content | `{ charOffset }` |

### T&C Detection Heuristic

The content script detects T&C pages by scanning the page title and body text for at least 2 of the following 8 keywords: `terms`, `conditions`, `privacy`, `policy`, `agreement`, `service`, `legal`, `cookies`. This minimizes false positives while covering the breadth of legal document patterns.

### Section Extraction

After extracting the article body via Mozilla Readability, the content script walks the DOM to find all `h1`–`h4` headings and `<strong>` elements styled as section titles. Each heading is paired with its character offset in the extracted plain text, creating a `sections[]` array that maps section names to their position in the document — enabling "View Clause" scroll navigation.

---

## Backend Service

### Processing Pipeline

#### Ingest (`POST /ingest`)

```
Raw Text + Sections
        │
        ▼
┌───────────────────┐
│  Section-Aware    │  Splits text by section boundaries,
│  Chunker          │  then greedily packs sentences up to
│  (chunker.py)     │  512 tokens with 50-token overlap.
└────────┬──────────┘
         │  Chunk[]
         ▼
┌───────────────────┐
│  Embedding        │  Encodes all chunks using the local
│  Provider         │  all-MiniLM-L6-v2 model (384 dims).
│  (retrieval.py)   │  Supports OpenAI as a fallback.
└────────┬──────────┘
         │  vectors{}
         ▼
┌───────────────────┐
│  Index Building   │  Builds BM25Okapi sparse index and
│  (retrieval.py)   │  stores dense vectors in memory,
│                   │  keyed by doc_id.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Risk Scanner     │  Runs 6 concurrent risk queries via
│  (risk_scanner.py)│  asyncio.gather, one per risk category.
│                   │  Each query uses the full RAG pipeline.
└────────┬──────────┘
         │
         ▼
  doc_id + chunk_count + risk_report[]
```

#### Query (`POST /query`)

```
doc_id + query
      │
      ▼
┌─────────────────┐
│  Hybrid Search  │  Embeds query; runs BM25 (top 20) and
│  (retrieval.py) │  cosine vector search (top 20); merges
│                 │  via Reciprocal Rank Fusion → top 10.
└────────┬────────┘
         │  top-10 candidates
         ▼
┌─────────────────┐
│  Reranker       │  Cohere cross-encoder scores candidates
│  (reranker.py)  │  against the query → top 5. Falls back
│                 │  to PassthroughReranker if API fails.
└────────┬────────┘
         │  top-5 chunks + relevance scores
         ▼
┌─────────────────┐
│  LLM Answer Gen │  If max relevance score ≥ 0.1, sends
│  (llm.py)       │  context + query to Claude. Returns
│                 │  JSON: { answer, citations[] }.
└────────┬────────┘
         │
         ▼
   answer + citations[]
```

### API Endpoints

| Method | Path | Request Body | Response Body |
|--------|------|--------------|---------------|
| `GET` | `/health` | — | `{ "status": "ok" }` |
| `POST` | `/ingest` | `{ text: str, sections: [{ heading, charOffset }] }` | `{ doc_id, chunk_count, risk_report[] }` |
| `POST` | `/query` | `{ doc_id: str, query: str }` | `{ answer: str, citations: [{ heading, snippet, relevance_score }] }` |

### Risk Taxonomy

The risk scanner evaluates every document against six categories:

| Category | Risk Description | Severity Levels |
|----------|-----------------|-----------------|
| Data Selling | Third-party data sharing or sale | High / Medium / Low |
| Arbitration Clause | Mandatory arbitration, court waiver | High / Medium / Low |
| Auto-Renewal | Automatic subscription renewal, cancellation friction | High / Medium / Low |
| IP Ownership | Ownership rights over user-generated content | High / Medium / Low |
| Jurisdiction | Dispute resolution location (convenience/favorability) | High / Medium / Low |
| Deletion Rights | Ease and permanence of account/data deletion | High / Medium / Low |

### Hybrid Retrieval

The retrieval system combines two complementary search strategies:

- **BM25 (Sparse):** Keyword-based scoring using BM25Okapi. Tokenizes chunk text with simple whitespace splitting. Strong at exact term matching.
- **Vector Search (Dense):** Cosine similarity over 384-dimensional embeddings from the all-MiniLM-L6-v2 model. Strong at semantic matching where exact keywords are absent.
- **Reciprocal Rank Fusion (RRF):** Merges ranked results from both approaches using the formula `score(d) = Σ 1/(k + rank(d))` where k=60. This is a parameter-free fusion method that consistently outperforms individual rankers.

### Data Models

```python
# Ingest Request
{
  "text": str,            # Full document text
  "sections": [
    { "heading": str, "charOffset": int }
  ]
}

# Ingest Response
{
  "doc_id": str,          # UUID for this document session
  "chunk_count": int,
  "risk_report": [
    {
      "category": str,    # e.g., "Data Selling"
      "severity": str,    # "high" | "medium" | "low"
      "finding": str,     # Plain-English one-sentence assessment
      "citation": {
        "heading": str,
        "snippet": str
      }
    }
  ]
}

# Query Request
{
  "doc_id": str,
  "query": str
}

# Query Response
{
  "answer": str,
  "citations": [
    {
      "heading": str,
      "snippet": str,
      "relevance_score": float
    }
  ]
}
```
