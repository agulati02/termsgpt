# Project Description

---

## Problem Statement

Every digital service — from social media platforms and streaming apps to cloud storage providers and e-commerce sites — requires users to agree to Terms & Conditions (T&C) before use. These documents are typically dense, lengthy, and written in complex legal language that the average user cannot be expected to read or fully understand. Studies consistently show that the majority of people accept T&Cs without reading them, often unknowingly surrendering significant rights over their data, intellectual property, and legal recourse options.

The key risks buried in these agreements include:

- **Data monetization clauses** that permit the sale or sharing of personal data with third parties.
- **Mandatory arbitration clauses** that waive a user's right to pursue disputes in court.
- **Auto-renewal traps** that silently charge users on a recurring basis with difficult cancellation terms.
- **IP ownership transfers** that grant the service provider broad rights over content the user creates.
- **Unfavorable jurisdiction clauses** that require users to litigate in inconvenient or legally disadvantageous locations.
- **Poor data deletion rights** that make it difficult or impossible to remove personal information upon account closure.

The result is a widespread information asymmetry: companies benefit from users who do not understand what they are agreeing to, and users bear the legal, financial, and privacy costs.

---

## Proposed Solution

TermsGPT is an AI-powered browser extension that automatically detects when a user is on a Terms & Conditions page, extracts the document's content, and uses a Retrieval-Augmented Generation (RAG) pipeline backed by large language models to analyze, summarize, and flag high-risk clauses in real time.

The solution operates in two modes:

1. **Automatic Risk Scanning:** Upon detecting a T&C page, TermsGPT immediately runs a structured analysis across six predefined risk categories — Data Selling, Arbitration Clauses, Auto-Renewal, IP Ownership, Jurisdiction, and Deletion Rights. Each category receives a severity rating (High, Medium, or Low) with a plain-English finding and a direct link to the relevant clause in the document.

2. **Interactive Q&A:** Users can ask natural language questions about any aspect of the agreement (e.g., "Can this company share my data with advertisers?" or "What happens to my content if I delete my account?"). The backend retrieves the most relevant clauses using a hybrid search approach and generates a grounded, citation-backed answer using LLM.

TermsGPT eliminates the barrier between users and their digital rights by making the analysis instant, accessible, and actionable — directly inside the browser, with no additional steps required.

---

## Project Scope

The current version of TermsGPT covers the following scope:

**In Scope:**
- Automatic detection of Terms & Conditions and Privacy Policy pages using heuristic keyword analysis.
- Full-document ingestion, semantic chunking, and embedding via a local sentence-transformer model.
- Hybrid retrieval combining BM25 sparse search and dense vector search, fused via Reciprocal Rank Fusion (RRF).
- Optional cross-encoder reranking via the Cohere API, with graceful fallback to RRF ordering.
- Automated risk scanning across 6 risk categories using parallel LLM API calls.
- Natural language Q&A with context-grounded answers and inline clause citations.
- Clickable "View Clause" links that scroll the browser to the exact section referenced.
- A persistent sidebar panel UI within Chrome that displays both the risk dashboard and a chat interface.
- In-memory session state tied to browser tabs, managed by the extension's background service worker.

**Out of Scope (Current Version):**
- Support for browsers other than Chrome (Firefox, Safari, Edge).
- Persistent storage of analyzed documents across sessions.
- API key configuration from within the extension UI.
- Containerized or cloud-hosted backend deployment.
- Multi-language support for non-English T&C documents.
