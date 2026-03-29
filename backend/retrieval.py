"""
Hybrid retrieval: BM25 sparse search + OpenAI dense vector search,
fused via Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from openai import OpenAI
from rank_bm25 import BM25Okapi

from chunker import Chunk

_client: OpenAI | None = None
_EMBEDDING_MODEL = "text-embedding-3-small"


def _get_client() -> OpenAI:
    """Lazy singleton — created on first call so load_dotenv() runs first."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from environment
    return _client


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns one vector per input string."""
    response = _get_client().embeddings.create(model=_EMBEDDING_MODEL, input=texts)
    # The API guarantees results are in the same order as inputs.
    return [item.embedding for item in response.data]


def embed_query(query: str) -> List[float]:
    return embed_texts([query])[0]


def embed_chunks(chunks: List[Chunk]) -> dict[str, List[float]]:
    """Return {chunk_id: vector} for every chunk in one batched API call."""
    vectors = embed_texts([c.text for c in chunks])
    return {chunk.chunk_id: vec for chunk, vec in zip(chunks, vectors)}


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

def build_bm25_index(chunks: List[Chunk]) -> BM25Okapi:
    """Tokenise chunk texts and build a BM25Okapi index."""
    tokenised = [c.text.lower().split() for c in chunks]
    return BM25Okapi(tokenised)


# ---------------------------------------------------------------------------
# Individual retrievers
# ---------------------------------------------------------------------------

def bm25_search(
    query: str,
    index: BM25Okapi,
    chunks: List[Chunk],
    top_k: int = 20,
) -> List[Tuple[Chunk, int]]:
    """
    Return [(chunk, rank), …] sorted by BM25 score descending.
    Rank is 1-based.
    """
    scores = index.get_scores(query.lower().split())
    ranked_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], rank + 1) for rank, i in enumerate(ranked_indices)]


def vector_search(
    query_embedding: List[float],
    vectors: dict[str, List[float]],
    chunks: List[Chunk],
    top_k: int = 20,
) -> List[Tuple[Chunk, int]]:
    """
    Return [(chunk, rank), …] sorted by cosine similarity descending.
    Rank is 1-based.
    """
    q = np.array(query_embedding, dtype=np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-10)

    chunk_map = {c.chunk_id: c for c in chunks}
    scored: List[Tuple[float, str]] = []

    for chunk_id, vec in vectors.items():
        v = np.array(vec, dtype=np.float32)
        v_norm = v / (np.linalg.norm(v) + 1e-10)
        similarity = float(np.dot(q_norm, v_norm))
        scored.append((similarity, chunk_id))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    return [(chunk_map[cid], rank + 1) for rank, (_, cid) in enumerate(top)]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    bm25_results: List[Tuple[Chunk, int]],
    vector_results: List[Tuple[Chunk, int]],
    k: int = 60,
    top_n: int = 10,
) -> List[Chunk]:
    """
    Merge two ranked lists using RRF: score(d) = Σ 1 / (k + rank(d)).

    Returns the top_n chunks by fused score.
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for chunk, rank in bm25_results:
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        chunk_map[chunk.chunk_id] = chunk

    for chunk, rank in vector_results:
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        chunk_map[chunk.chunk_id] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_map[cid] for cid, _ in ranked[:top_n]]
