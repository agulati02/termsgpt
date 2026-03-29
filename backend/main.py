import uuid

from dotenv import load_dotenv
load_dotenv()  # must run before OpenAI client is imported

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
from retrieval import (
    build_bm25_index,
    bm25_search,
    embed_chunks,
    embed_query,
    reciprocal_rank_fusion,
    vector_search,
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

    vectors = embed_chunks(chunks)
    bm25_index = build_bm25_index(chunks)

    store.save(doc_id, {
        "text": body.text,
        "sections": body.sections,
        "chunks": chunks,
        "vectors": vectors,
        "bm25_index": bm25_index,
    })
    return IngestResponse(doc_id=doc_id, chunk_count=len(chunks))


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest) -> QueryResponse:
    doc = store.get(body.doc_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"doc_id '{body.doc_id}' not found. Call /ingest first.",
        )

    chunks = doc["chunks"]
    vectors = doc["vectors"]
    bm25_index = doc["bm25_index"]

    query_vec = embed_query(body.query)
    bm25_results = bm25_search(body.query, bm25_index, chunks)
    vector_results = vector_search(query_vec, vectors, chunks)
    top_chunks = reciprocal_rank_fusion(bm25_results, vector_results)

    # Stub answer — replaced by LLM call in Feature 7.
    answer = "[Retrieval stub] Top chunks retrieved:\n\n" + "\n\n".join(
        f"[{c.heading}] {c.text}" for c in top_chunks
    )
    citations = [Citation(heading=c.heading, snippet=c.text[:200]) for c in top_chunks]

    return QueryResponse(answer=answer, citations=citations)
