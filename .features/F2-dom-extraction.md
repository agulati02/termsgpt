# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 2 — DOM Extraction & T&C Detection

### Requirement
The content script must intelligently extract the main body text of a Terms & Conditions (or Privacy Policy) page, strip navigation/footer/cookie banner noise, and preserve section headings as structured metadata. It must also detect whether the current page actually contains T&C content.

### Acceptance Criteria
- On a known T&C page (e.g., `spotify.com/legal/end-user-agreement`), the extractor returns the full body text with section headings preserved and labelled.
- On a non-T&C page (e.g., `google.com`), the extractor returns a flag `{ isTermsPage: false }` — no false positives.
- Extracted text excludes navbars, footers, cookie banners, and sidebar widgets.
- Section headings are returned as a separate structured array: `[{ heading: "1. Acceptance of Terms", charOffset: 0 }, ...]`.
- The extracted output is a plain JSON object transferable via `chrome.runtime.sendMessage`.

### Implementation Plan
1. Integrate Mozilla's `Readability.js` (via CDN or bundled) into the content script to isolate the main content block.
2. After Readability extraction, walk the DOM of the extracted fragment. Tag `<h1>`–`<h4>` and `<strong>` elements that appear to be section headings (heuristic: short text, followed by a block element).
3. Build a T&C detection heuristic: check the page `<title>`, `<h1>`, and first 200 chars of body for keywords like "terms", "conditions", "privacy policy", "user agreement", "legal". Return `isTermsPage: true` if two or more match.
4. Serialize the result as `{ isTermsPage: boolean, title: string, bodyText: string, sections: Array<{heading, charOffset}> }` and send it to the background worker via `chrome.runtime.sendMessage`.
5. Test against at least 4 real URLs: Spotify ToS, Google Privacy Policy, Reddit User Agreement, and a non-legal page (e.g., a news article).