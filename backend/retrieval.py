"""
Hybrid retrieval: BM25 sparse search + dense vector search,
fused via Reciprocal Rank Fusion (RRF).

Embedding providers are pluggable via the EmbeddingProvider protocol.
Swap the active provider at any time with set_provider():

    from retrieval import set_provider
    set_provider(MyHuggingFaceProvider())
"""

from __future__ import annotations

import logging
import time
from typing import List, Tuple
from typing import Protocol, runtime_checkable

import numpy as np
from rank_bm25 import BM25Okapi

from chunker import Chunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider protocol — implement this to plug in any embedding backend
# ---------------------------------------------------------------------------

@runtime_checkable
class EmbeddingProvider(Protocol):
    """
    Any object with this single method qualifies as an EmbeddingProvider.

    Args:
        texts: Non-empty list of strings to embed.

    Returns:
        List of float vectors, one per input string, in the same order.
    """
    def embed(self, texts: List[str]) -> List[List[float]]: ...


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------

class MiniLMEmbeddingProvider:
    """
    Local embeddings using sentence-transformers all-MiniLM-L6-v2.
    No API key required — model is downloaded on first use (~90 MB) and
    cached in ~/.cache/huggingface/hub.

    Requires:  pip install sentence-transformers
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None  # lazy — avoid loading at import time

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def warmup(self) -> None:
        """Download and cache the model. Called at service startup."""
        logger.info("MiniLM: loading model '%s'...", self.model_name)
        t0 = time.perf_counter()
        self._get_model()
        logger.info("MiniLM: model ready (%.2fs)", time.perf_counter() - t0)

    def embed(self, texts: List[str]) -> List[List[float]]:
        t0 = time.perf_counter()
        model = self._get_model()
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        logger.debug("MiniLM embed: %d text(s) in %.2fs", len(texts), time.perf_counter() - t0)
        return vectors.tolist()


class OpenAIEmbeddingProvider:
    """
    OpenAI embeddings via the official SDK.
    Reads OPENAI_API_KEY from the environment (set via .env / load_dotenv).
    """

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model
        self._client = None  # lazy init so load_dotenv() runs first

    def _get_client(self):
        if self._client is None:
            import openai  # noqa: PLC0415
            self._client = openai.OpenAI()
        return self._client

    def embed(self, texts: List[str]) -> List[List[float]]:
        response = self._get_client().embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Active provider — swap with set_provider()
# ---------------------------------------------------------------------------

_provider: EmbeddingProvider = OpenAIEmbeddingProvider()


def set_provider(provider: EmbeddingProvider) -> None:
    """
    Replace the active embedding provider at runtime.

    Example — switching to a local sentence-transformers model:

        from sentence_transformers import SentenceTransformer

        class STProvider:
            def __init__(self, model_name: str) -> None:
                self._model = SentenceTransformer(model_name)

            def embed(self, texts):
                return self._model.encode(texts, convert_to_numpy=False).tolist()

        set_provider(STProvider("all-MiniLM-L6-v2"))
    """
    global _provider
    if not isinstance(provider, EmbeddingProvider):
        raise TypeError(f"{provider!r} does not satisfy the EmbeddingProvider protocol (missing .embed method)")
    _provider = provider


# ---------------------------------------------------------------------------
# Public embedding helpers — delegate to the active provider
# ---------------------------------------------------------------------------

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns one vector per input string."""
    return _provider.embed(texts)


def embed_query(query: str) -> List[float]:
    logger.debug("Embedding query: %r", query[:80])
    return embed_texts([query])[0]


def embed_chunks(chunks: List[Chunk]) -> dict[str, List[float]]:
    """Return {chunk_id: vector} for every chunk in one batched call."""
    logger.info("Embedding %d chunks...", len(chunks))
    t0 = time.perf_counter()
    vectors = embed_texts([c.text for c in chunks])
    logger.info("Chunk embedding complete | %d vectors (%.2fs)", len(vectors), time.perf_counter() - t0)
    return {chunk.chunk_id: vec for chunk, vec in zip(chunks, vectors)}


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

def build_bm25_index(chunks: List[Chunk]) -> BM25Okapi:
    """Tokenise chunk texts and build a BM25Okapi index."""
    logger.info("Building BM25 index over %d chunks...", len(chunks))
    t0 = time.perf_counter()
    tokenised = [c.text.lower().split() for c in chunks]
    index = BM25Okapi(tokenised)
    logger.info("BM25 index ready (%.2fs)", time.perf_counter() - t0)
    return index


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
