# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 10 — Sidebar UI (Risk Dashboard + Chat Interface)

### Requirement
Build the full sidebar panel UI with two views: (1) a Risk Dashboard that displays the auto-scanned risk report as a visual scorecard, and (2) a Chat Interface for freeform Q&A with citation display. The UI must be functional, clean, and fast to render.

### Acceptance Criteria
- The Risk Dashboard renders each of the 6 risk categories as a card with a coloured severity badge (🔴/🟡/🟢), a one-line finding, and a clickable "View Clause" link.
- Clicking "View Clause" scrolls the host page to the relevant section (using the `charOffset` metadata from the extraction step).
- The Chat Interface renders below the risk dashboard with a text input and a scrollable message history.
- Each AI response in the chat shows the answer text and an expandable "Sources" section listing citation headings and snippets.
- The UI handles three loading states: (a) extracting, (b) analysing (ingesting + risk scan), (c) answering a query.
- The sidebar is usable at a minimum width of 360px and requires no external CSS framework (vanilla CSS or a single bundled stylesheet).

### Implementation Plan
1. Design `sidebar.html` with two sections: `<div id="risk-dashboard">` and `<div id="chat-interface">`.
2. Build the risk card component in vanilla JS: `renderRiskCard({ category, severity, finding, citation })` → returns an HTML string injected into the dashboard.
3. Implement "View Clause" scroll: store `charOffset` per citation in a data attribute. On click, send a `SCROLL_TO` message to the content script, which uses `document.createTreeWalker` to find the character position and calls `.scrollIntoView()`.
4. Build the chat component: a message list rendered as `<div class="message user|assistant">`, with citations as a `<details><summary>Sources</summary>...</details>` block.
5. Implement the three loading state banners using a single `<div id="status-bar">` element updated by JS.
6. Write CSS for the severity badge colours, card layout, and chat bubbles. Keep the total CSS under 150 lines.
