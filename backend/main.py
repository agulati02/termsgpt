import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # must run before OpenAI client is imported

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from chunker import chunk_by_sections
from models import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from retrieval import (
    build_bm25_index,
    bm25_search,
    embed_chunks,
    embed_query,
    reciprocal_rank_fusion,
    vector_search,
    set_provider,
    MiniLMEmbeddingProvider,
)
from reranker import rerank_chunks, set_reranker, CohereReranker
from llm import generate_answer
from risk_scanner import run_risk_scan
import store

logger = logging.getLogger(__name__)

_embedding_provider = MiniLMEmbeddingProvider()
_reranker_provider = CohereReranker()

set_provider(_embedding_provider)
set_reranker(_reranker_provider)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Downloading/loading models at startup...")
    await asyncio.gather(
        asyncio.to_thread(_embedding_provider.warmup),
        asyncio.to_thread(_reranker_provider.warmup),
    )
    logger.info("All models ready.")
    yield


app = FastAPI(title="TermsGPT Backend", version="0.1.0", lifespan=lifespan)

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
async def ingest(body: IngestRequest) -> IngestResponse:
    doc_id = str(uuid.uuid4())
    text_len = len(body.text)
    section_count = len(body.sections) if body.sections else 0
    logger.info("Ingest started | doc_id=%s | text=%d chars | sections=%d", doc_id, text_len, section_count)
    t_total = time.perf_counter()

    t = time.perf_counter()
    chunks = chunk_by_sections(body.text, body.sections)
    logger.info("  [1/4] Chunking done | %d chunks (%.2fs)", len(chunks), time.perf_counter() - t)

    t = time.perf_counter()
    vectors = embed_chunks(chunks)
    logger.info("  [2/4] Embedding done | %d vectors (%.2fs)", len(vectors), time.perf_counter() - t)

    t = time.perf_counter()
    bm25_index = build_bm25_index(chunks)
    logger.info("  [3/4] BM25 index built (%.2fs)", time.perf_counter() - t)

    store.save(doc_id, {
        "text": body.text,
        "sections": body.sections,
        "chunks": chunks,
        "vectors": vectors,
        "bm25_index": bm25_index,
    })

    t = time.perf_counter()
    risk_report = await run_risk_scan(doc_id)
    logger.info("  [4/4] Risk scan done | %d entries (%.2fs)", len(risk_report), time.perf_counter() - t)

    logger.info("Ingest complete | doc_id=%s | total=%.2fs", doc_id, time.perf_counter() - t_total)
    return IngestResponse(doc_id=doc_id, chunk_count=len(chunks), risk_report=risk_report)


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest) -> QueryResponse:
    logger.info("Query | doc_id=%s | query=%r", body.doc_id, body.query[:80])
    t_total = time.perf_counter()

    doc = store.get(body.doc_id)
    if doc is None:
        logger.warning("Query failed: doc_id '%s' not found", body.doc_id)
        raise HTTPException(
            status_code=404,
            detail=f"doc_id '{body.doc_id}' not found. Call /ingest first.",
        )

    chunks = doc["chunks"]
    vectors = doc["vectors"]
    bm25_index = doc["bm25_index"]

    t = time.perf_counter()
    query_vec = embed_query(body.query)
    logger.debug("  [1/4] Query embedding (%.2fs)", time.perf_counter() - t)

    bm25_results = bm25_search(body.query, bm25_index, chunks)
    vector_results = vector_search(query_vec, vectors, chunks)
    rrf_chunks = reciprocal_rank_fusion(bm25_results, vector_results)
    logger.info("  [2/4] Hybrid retrieval | %d RRF candidates", len(rrf_chunks))

    t = time.perf_counter()
    ranked = rerank_chunks(body.query, rrf_chunks)
    logger.info("  [3/4] Reranking done | %d results (%.2fs)", len(ranked), time.perf_counter() - t)

    result = generate_answer(body.query, ranked)
    logger.info("  [4/4] Answer generated | %d citations | total=%.2fs",
                len(result.citations), time.perf_counter() - t_total)
    return result
