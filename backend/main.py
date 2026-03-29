import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from chunker import chunk_by_sections
from models import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    Citation,
)
import store

app = FastAPI(title="TermsGPT Backend", version="0.1.0")

# Allow all origins for local dev.
# TODO: tighten to the specific chrome-extension:// ID before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest) -> IngestResponse:
    doc_id = str(uuid.uuid4())
    chunks = chunk_by_sections(body.text, body.sections)
    store.save(doc_id, {"text": body.text, "sections": body.sections, "chunks": chunks})
    return IngestResponse(doc_id=doc_id, chunk_count=len(chunks))


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest) -> QueryResponse:
    if not store.exists(body.doc_id):
        raise HTTPException(status_code=404, detail=f"doc_id '{body.doc_id}' not found. Call /ingest first.")
    # Stub response — real RAG logic added in Features 5-7.
    return QueryResponse(
        answer="[Stub] This is a placeholder answer. RAG pipeline not yet implemented.",
        citations=[
            Citation(
                heading="Stub Section",
                snippet="[Stub] Relevant snippet will appear here after Features 5-7 are implemented.",
            )
        ],
    )
