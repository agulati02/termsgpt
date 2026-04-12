"""
Cross-encoder reranking with a pluggable provider pattern.

Swap the active reranker at any time with set_reranker():

    from reranker import set_reranker, CohereReranker
    set_reranker(CohereReranker())

Built-in providers
------------------
CohereReranker       — Cohere Rerank API (rerank-english-v3.0, requires COHERE_API_KEY)
PassthroughReranker  — No-op; returns the top_n chunks in their original order.
                       Used as the default so the pipeline works without any API key,
                       and as the fallback target when a reranker call fails.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List
from typing import Protocol, runtime_checkable

from chunker import Chunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class RankedChunk:
    chunk: Chunk
    relevance_score: float


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class RerankerProvider(Protocol):
    """
    Any object with this single method qualifies as a RerankerProvider.

    Args:
        query:   The user query string.
        chunks:  Candidate chunks to re-score (typically the top-10 from RRF).
        top_n:   How many to return after reranking.

    Returns:
        List of RankedChunk, length ≤ top_n, sorted by relevance_score descending.
    """
    def rerank(self, query: str, chunks: List[Chunk], top_n: int) -> List[RankedChunk]: ...


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------

class PassthroughReranker:
    """
    No-op reranker — returns the first top_n chunks unchanged with score 1.0.
    Used as the default and as the graceful fallback when a real reranker fails.
    """

    def rerank(self, query: str, chunks: List[Chunk], top_n: int) -> List[RankedChunk]:
        return [RankedChunk(chunk=c, relevance_score=1.0) for c in chunks[:top_n]]


class CohereReranker:
    """
    Cohere Rerank API cross-encoder.
    Reads COHERE_API_KEY from the environment (set via .env / load_dotenv).

    Requires:  pip install cohere
    """

    def __init__(self, model: str = "rerank-english-v3.0") -> None:
        self.model = model
        self._client = None  # lazy — avoid loading at import time

    def _get_client(self):
        if self._client is None:
            import cohere  # noqa: PLC0415
            self._client = cohere.Client()  # reads COHERE_API_KEY from env
        return self._client

    def warmup(self) -> None:
        """Eagerly initialise the Cohere client. Validates COHERE_API_KEY at startup."""
        logger.info("CohereReranker: initialising client (model=%s)...", self.model)
        t0 = time.perf_counter()
        self._get_client()
        logger.info("CohereReranker: client ready (%.2fs)", time.perf_counter() - t0)

    def rerank(self, query: str, chunks: List[Chunk], top_n: int) -> List[RankedChunk]:
        logger.info("CohereReranker: reranking %d chunks → top %d (model=%s)", len(chunks), top_n, self.model)
        t0 = time.perf_counter()
        try:
            co = self._get_client()
            response = co.rerank(
                query=query,
                documents=[c.text for c in chunks],
                top_n=top_n,
                model=self.model,
            )
        except Exception as exc:
            exc_str = str(exc)
            exc_name = type(exc).__name__
            status = getattr(exc, "status_code", None)
            if status == 429 or "429" in exc_str or "rate" in exc_str.lower() or "TooMany" in exc_name:
                logger.error(
                    "RATE LIMIT hit on Cohere Rerank API (%s) — backing off recommended. %s",
                    exc_name, exc_str[:200],
                )
            else:
                logger.error("CohereReranker error (%s): %s", exc_name, exc_str[:200])
            raise
        elapsed = time.perf_counter() - t0
        results = [
            RankedChunk(chunk=chunks[r.index], relevance_score=r.relevance_score)
            for r in response.results
        ]
        scores = [f"{r.relevance_score:.3f}" for r in results]
        logger.info("CohereReranker: done (%.2fs) | scores=%s", elapsed, scores)
        return results


class LocalCrossEncoderReranker:
    """
    Local cross-encoder reranker via sentence-transformers.
    No API key required — model is downloaded on first use and cached locally.

    Example:
        set_reranker(LocalCrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2"))

    Requires:  pip install sentence-transformers
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # noqa: PLC0415
            self._model = CrossEncoder(self.model_name)
        return self._model

    def warmup(self) -> None:
        """Download and cache the model. Called at service startup."""
        logger.info("LocalCrossEncoderReranker: loading model '%s'...", self.model_name)
        t0 = time.perf_counter()
        self._get_model()
        logger.info("LocalCrossEncoderReranker: model ready (%.2fs)", time.perf_counter() - t0)

    def rerank(self, query: str, chunks: List[Chunk], top_n: int) -> List[RankedChunk]:
        model = self._get_model()
        pairs = [(query, c.text) for c in chunks]
        scores = model.predict(pairs).tolist()
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [RankedChunk(chunk=c, relevance_score=float(s)) for c, s in ranked[:top_n]]


# ---------------------------------------------------------------------------
# Active provider — swap with set_reranker()
# ---------------------------------------------------------------------------

_reranker: RerankerProvider = PassthroughReranker()


def set_reranker(provider: RerankerProvider) -> None:
    """
    Replace the active reranker at runtime.

    Example — switching to Cohere:
        from reranker import set_reranker, CohereReranker
        set_reranker(CohereReranker())
    """
    global _reranker
    if not isinstance(provider, RerankerProvider):
        raise TypeError(
            f"{provider!r} does not satisfy the RerankerProvider protocol (missing .rerank method)"
        )
    _reranker = provider


# ---------------------------------------------------------------------------
# Public reranking function — delegates to active provider with timing + fallback
# ---------------------------------------------------------------------------

_FALLBACK = PassthroughReranker()


def rerank_chunks(query: str, chunks: List[Chunk], top_n: int = 5) -> List[RankedChunk]:
    """
    Re-score `chunks` against `query` using the active RerankerProvider.

    - Logs reranker latency to stdout.
    - On any provider error, logs a warning and falls back to PassthroughReranker
      (i.e. returns the top_n chunks in their original RRF order with score 1.0).
    """
    provider_name = type(_reranker).__name__
    logger.info("rerank_chunks: provider=%s | %d candidates → top %d", provider_name, len(chunks), top_n)
    t0 = time.perf_counter()
    try:
        results = _reranker.rerank(query, chunks, top_n)
    except Exception as exc:
        logger.warning(
            "Reranker (%s) failed — falling back to RRF order. %s: %s",
            provider_name, type(exc).__name__, exc,
        )
        results = _FALLBACK.rerank(query, chunks, top_n)
    elapsed = time.perf_counter() - t0
    logger.info("rerank_chunks: done (%.2fs) | returned %d results", elapsed, len(results))
    return results
