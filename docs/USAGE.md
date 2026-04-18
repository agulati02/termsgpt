# Usage Guidelines

---

## Pre-requisites

Before setting up TermsGPT locally, ensure the following are in place:

### System Requirements

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python | 3.8+ | 3.10+ recommended |
| Node.js | 16+ | Required only to rebuild the extension |
| npm | 8+ | Required only to rebuild the extension |
| Google Chrome | Latest stable | The extension targets Chrome Manifest V3 |
| RAM | 4 GB free | The MiniLM embedding model loads ~90 MB into memory |
| Disk Space | ~500 MB | For Python packages and the sentence-transformers model cache |

### API Keys

TermsGPT requires the following API keys. Create a `.env` file in the `backend/` directory using the template at `backend/.env.example`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | **Yes** | Powers risk scanning and natural language Q&A via Claude |
| `COHERE_API_KEY` | Optional | Enables cross-encoder reranking for higher-quality results. If absent, results fall back to RRF ordering. |
| `OPENAI_API_KEY` | Optional | Alternative embedding provider. If absent, the local MiniLM model is used. |

---

## Implementation Steps

### Step 1 — Clone the Repository

```bash
git clone <repository-url>
cd termsgpt
```

### Step 2 — Set Up the Backend

**2a. Create and activate a virtual environment:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# or
.venv\Scripts\activate         # Windows
```

**2b. Install Python dependencies:**

```bash
pip install -r requirements.txt
```

This will download and install all required packages including FastAPI, sentence-transformers, rank-bm25, and the Anthropic SDK. The first run will also download the `all-MiniLM-L6-v2` embedding model (~90 MB) from Hugging Face into the local sentence-transformers cache.

**2c. Configure environment variables:**

```bash
cp .env.example .env
```

Open `.env` and fill in your API keys:

```
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...              # Optional
OPENAI_API_KEY=sk-...           # Optional
```

**2d. Start the backend server:**

```bash
uvicorn main:app --reload
```

The server will start at `http://localhost:8000`. You can verify it is running by visiting `http://localhost:8000/health` in your browser, which should return:

```json
{ "status": "ok" }
```

### Step 3 — Load the Browser Extension

**3a. (Optional) Rebuild the content script:**

If you have made any changes to `extension/content.js`, rebuild the bundle:

```bash
cd extension
npm install
npm run build
```

This produces an updated `extension/dist/content.js` using esbuild.

**3b. Load the unpacked extension in Chrome:**

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension/` directory from this project.

The TermsGPT extension will appear in your Chrome toolbar.

### Step 4 — Using TermsGPT

1. **Navigate to any Terms & Conditions or Privacy Policy page** in Chrome (e.g., a signup page that shows a terms agreement).

2. **Click the TermsGPT icon** in the Chrome toolbar to open the side panel.

3. **Automatic analysis:** TermsGPT will automatically detect the T&C page, extract the content, and send it to the backend for analysis. A spinner will indicate progress.

4. **Review the risk dashboard:** Once analysis is complete, the sidebar displays a dashboard with up to 6 risk categories. Each entry shows:
   - A severity badge (High / Medium / Low)
   - A plain-English finding
   - A **View Clause** link that scrolls the page to the relevant section

5. **Ask questions:** Use the chat input at the bottom of the sidebar to ask natural language questions about the terms, such as:
   - *"Can they share my data with third parties?"*
   - *"What are the cancellation terms for auto-renewal?"*
   - *"Do I retain ownership of content I post?"*

   The backend will retrieve the most relevant clauses and return a grounded answer with citations.

### Step 5 — Running Tests

To run the backend unit tests:

```bash
cd backend
python -m pytest tests/
```

---

## Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Extension shows no activity | Backend server is not running | Ensure `uvicorn main:app --reload` is running at `localhost:8000` |
| "NOT_TC_PAGE" shown | Page does not have enough T&C keywords | Try a dedicated terms page (e.g., a service signup page) |
| Risk scan fails | Missing `ANTHROPIC_API_KEY` | Check the `.env` file in `backend/` |
| Reranking not active | Missing `COHERE_API_KEY` | Add the key or leave blank to use fallback ordering |
| Content script not loading | Bundle not built | Run `npm install && npm run build` inside `extension/` |
