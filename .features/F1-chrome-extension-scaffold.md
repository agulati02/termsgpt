# TermsGPT — Feature Breakdown for AI-Assisted Implementation

> **Project summary:** A Chrome extension that extracts Terms & Conditions from any webpage, runs a RAG pipeline over the text, auto-scores risk categories, and lets users ask freeform questions — all surfaced in a native Chrome sidebar.
>
> **Tech stack:** Manifest V3 Chrome extension (JS) + FastAPI backend (Python) + OpenAI Embeddings + Cohere Rerank + Claude API
>
> **How to use this document:** Each feature below is self-contained and can be handed to an AI coding agent independently. Features are ordered by dependency — implement them top-to-bottom.

---

## Feature 1 — Chrome Extension Scaffold

### Requirement
Set up a working Manifest V3 Chrome extension with the minimum viable structure: a background service worker, a content script, and a sidebar panel (`chrome.sidePanel`). The extension should activate on any webpage the user visits.

### Acceptance Criteria
- `manifest.json` is valid Manifest V3 and passes Chrome's extension loader without errors.
- The background service worker registers without crashing.
- The content script injects successfully on any `http://` or `https://` page.
- Clicking the extension icon opens a sidebar panel (`chrome.sidePanel`) that renders a static placeholder UI ("TermsGPT loading...").
- The extension can be loaded unpacked in Chrome via `chrome://extensions`.

### Implementation Plan
1. Create `manifest.json` with `manifest_version: 3`, declaring `sidePanel`, `activeTab`, and `scripting` permissions.
2. Create `background.js` as the service worker. Register a `chrome.action.onClicked` listener that calls `chrome.sidePanel.open()`.
3. Create `content.js` as the content script, injected on `<all_urls>`. For now, log `"TermsGPT content script active"` to confirm injection.
4. Create `sidebar.html` + `sidebar.js` as the sidebar panel entry point. Render a static `<div>TermsGPT loading...</div>`.
5. Wire up message passing: content script sends a `PING` to the background worker, background responds with `PONG`, and sidebar displays the result — confirming the full communication chain works end to end.