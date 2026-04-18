# Future Scope

This document outlines planned improvements and enhancements for TermsGPT beyond the current implementation.

---

## API Key Management via Extension UI

Currently, API keys (Anthropic, Cohere, OpenAI) must be manually configured in a `.env` file on the machine running the backend service. This creates friction for non-technical users and makes it difficult to distribute TermsGPT as a standalone tool.

**Planned improvement:** Users will be able to add, update, and remove their API keys directly from the extension's side panel UI in the browser. Keys will be securely stored using Chrome's `chrome.storage.sync` or `chrome.storage.local` APIs and transmitted to the backend on demand — removing the need to edit configuration files entirely.

---

## Persistent Vector Database Integration

The current backend uses an in-memory Python dictionary to store document chunks and embedding vectors. This is fast and simple, but means all analyzed documents are lost when the server restarts, and memory usage grows unboundedly with more documents.

**Planned improvement:** Replace the in-memory store in `store.py` with a dedicated vector database backend. Candidate solutions include:

- **pgvector** (PostgreSQL extension) — for self-hosted, SQL-compatible persistence
- **Pinecone** or **Weaviate** — for managed cloud vector storage with built-in ANN indexing
- **Chroma** — for a lightweight, local-first alternative

This change will enable persistent sessions across server restarts, multi-user support, and the ability to query documents that were analyzed in previous sessions.

---

## Containerization for Deployment

The backend service currently requires manual Python environment setup, which limits portability and makes deployment to cloud or on-premise servers error-prone.

**Planned improvement:** Package the backend as a Docker container with a `Dockerfile` and optionally a `docker-compose.yml` for orchestrating the backend service alongside any required database. This will enable:

- One-command deployment to any environment with Docker installed
- Reproducible builds with pinned dependencies
- Easy integration with cloud platforms (AWS ECS, Google Cloud Run, Azure Container Apps) or self-hosted Kubernetes clusters
