"""
Risk Taxonomy Auto-Scanner (F8).

Runs 6 pre-defined risk queries against an already-ingested document's in-memory
index and returns a structured risk report.  All 6 queries run concurrently via
asyncio.gather + asyncio.to_thread so the total latency is bounded by the slowest
single query rather than their sum.

Usage
-----
    from risk_scanner import run_risk_scan

    risk_report = await run_risk_scan(doc_id)
    # → List[RiskEntry], one entry per category

Design choices
--------------
- PassthroughReranker is used deliberately (no Cohere call per query) to keep
  latency within the 10-second target and avoid hitting Cohere rate limits with
  six simultaneous requests.
- On any per-category failure the entry silently falls back to the "not mentioned"
  🟢 response rather than failing the whole ingest.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List

import anthropic

import store
from models import RiskCitation, RiskEntry
from retrieval import (
    bm25_search,
    embed_query,
    reciprocal_rank_fusion,
    vector_search,
)
from reranker import PassthroughReranker, RankedChunk

logger = logging.getLogger(__name__)

_MODEL = "claude-opus-4-6"
_TOP_N_RISK = 3
_PASSTHROUGH = PassthroughReranker()


# ---------------------------------------------------------------------------
# Risk taxonomy
# ---------------------------------------------------------------------------

RISK_TAXONOMY: list[dict] = [
    {
        "category": "Data Selling",
        "query": "Does this service sell or transfer user data to third parties?",
        "rubric": (
            "High if data is sold to third parties for profit. "
            "Medium if shared with partners or affiliates. "
            "Low if only used internally or with service providers under strict contracts."
        ),
    },
    {
        "category": "Arbitration Clause",
        "query": "Does this agreement require mandatory arbitration or waive class action rights?",
        "rubric": (
            "High if mandatory arbitration is required and class action is waived. "
            "Medium if arbitration is optional or class action rights are partially limited. "
            "Low if users retain full right to court proceedings."
        ),
    },
    {
        "category": "Auto-Renewal",
        "query": "Does this service automatically renew subscriptions or charge recurring fees?",
        "rubric": (
            "High if auto-renewal occurs without prominent notice and is difficult to cancel. "
            "Medium if auto-renewal is disclosed but cancellation is cumbersome. "
            "Low if auto-renewal requires explicit opt-in or is easy to cancel."
        ),
    },
    {
        "category": "IP Ownership",
        "query": "Who owns the intellectual property rights to user-generated content?",
        "rubric": (
            "High if the company claims ownership or a broad irrevocable license over user content. "
            "Medium if the company claims a license for service purposes but users retain ownership. "
            "Low if users retain full IP rights with minimal licensing."
        ),
    },
    {
        "category": "Jurisdiction",
        "query": "What jurisdiction or governing law applies to disputes?",
        "rubric": (
            "High if jurisdiction is in a location significantly inconvenient for most users "
            "or has weak consumer protections. "
            "Medium if jurisdiction is specified but reasonably accessible. "
            "Low if local law applies or the jurisdiction is user-friendly."
        ),
    },
    {
        "category": "Deletion Rights",
        "query": "Can users delete their account and personal data, and is data actually removed?",
        "rubric": (
            "High if deletion is not offered, is difficult, or data is retained indefinitely. "
            "Medium if deletion is available but data may persist for extended periods. "
            "Low if users can easily delete and data is promptly removed."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RISK_SYSTEM_PROMPT = (
    "You are a legal risk analyst. "
    "Assess whether the provided document excerpts contain language relevant to the given risk category. "
    "Use the scoring rubric to determine severity. "
    "Return ONLY valid JSON in this exact format: "
    '{"severity": "🔴|🟡|🟢", "finding": "one sentence", '
    '"citation": {"heading": "...", "snippet": "..."}} '
    "If the excerpts do not address the risk category, return: "
    '{"severity": "🟢", "finding": "Not mentioned in this document.", '
    '"citation": {"heading": "", "snippet": ""}}'
)


def _not_mentioned(category: str) -> RiskEntry:
    return RiskEntry(
        category=category,
        severity="🟢",
        finding="Not mentioned in this document.",
        citation=RiskCitation(heading="", snippet=""),
    )


def _build_risk_message(
    category: str, query: str, rubric: str, ranked: List[RankedChunk]
) -> str:
    excerpts = "\n\n".join(
        f"{i + 1}. [Section: {r.chunk.heading}]\n{r.chunk.text}"
        for i, r in enumerate(ranked)
    )
    return (
        f"Risk Category: {category}\n"
        f"Scoring Rubric: {rubric}\n\n"
        f"Document Excerpts:\n{excerpts}\n\n"
        f"Question: {query}"
    )


def _parse_risk_response(text: str, category: str) -> RiskEntry:
    """
    Two-stage JSON parse with fallback to 'not mentioned' entry.
    Stage 1: direct json.loads.
    Stage 2: extract first {...} block via regex.
    Stage 3: return 'not mentioned' with a warning.
    """

    def _extract(raw: str) -> RiskEntry:
        data = json.loads(raw)
        c = data.get("citation", {})
        return RiskEntry(
            category=category,
            severity=data.get("severity", "🟢"),
            finding=data.get("finding", "Not mentioned in this document."),
            citation=RiskCitation(
                heading=c.get("heading", ""),
                snippet=c.get("snippet", ""),
            ),
        )

    try:
        return _extract(text)
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return _extract(match.group(0))
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    logger.warning("Risk LLM response unparseable for '%s'; using not-mentioned.", category)
    return _not_mentioned(category)


# ---------------------------------------------------------------------------
# Per-category query (sync — runs in a thread)
# ---------------------------------------------------------------------------

def _run_single_risk_query(
    doc: dict, category: str, query: str, rubric: str
) -> RiskEntry:
    import time as _time
    t_total = _time.perf_counter()
    logger.info("[%s] Starting risk query", category)
    try:
        chunks = doc["chunks"]
        vectors = doc["vectors"]
        bm25_index = doc["bm25_index"]

        t = _time.perf_counter()
        query_vec = embed_query(query)
        logger.debug("[%s] Embedding done (%.2fs)", category, _time.perf_counter() - t)

        bm25_results = bm25_search(query, bm25_index, chunks)
        vector_results = vector_search(query_vec, vectors, chunks)
        rrf_chunks = reciprocal_rank_fusion(bm25_results, vector_results)
        logger.debug("[%s] Hybrid retrieval: %d RRF candidates", category, len(rrf_chunks))

        ranked = _PASSTHROUGH.rerank(query, rrf_chunks, top_n=_TOP_N_RISK)
        if not ranked:
            logger.info("[%s] No relevant chunks — returning not-mentioned", category)
            return _not_mentioned(category)

        user_message = _build_risk_message(category, query, rubric, ranked)
        logger.debug("[%s] Risk prompt:\n%s", category, user_message)

        logger.info("[%s] Calling Claude API (model=%s)...", category, _MODEL)
        t = _time.perf_counter()
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_RISK_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.RateLimitError as exc:
            logger.error(
                "[%s] RATE LIMIT hit on Anthropic API — %s. "
                "Consider adding a retry delay or reducing concurrent requests.",
                category, exc,
            )
            return _not_mentioned(category)
        except anthropic.APIStatusError as exc:
            logger.error(
                "[%s] Anthropic API error status=%d — %s",
                category, exc.status_code, exc.message,
            )
            return _not_mentioned(category)
        except anthropic.APIConnectionError as exc:
            logger.error("[%s] Anthropic API connection error — %s", category, exc)
            return _not_mentioned(category)

        llm_elapsed = _time.perf_counter() - t
        usage = response.usage
        logger.info(
            "[%s] Claude response (%.2fs) | tokens in=%d out=%d | stop_reason=%s",
            category, llm_elapsed, usage.input_tokens, usage.output_tokens, response.stop_reason,
        )

        raw_text = next(
            (block.text for block in response.content if block.type == "text"), ""
        )
        result = _parse_risk_response(raw_text, category)
        logger.info(
            "[%s] Result: severity=%s | finding=%r (total=%.2fs)",
            category, result.severity, result.finding[:80], _time.perf_counter() - t_total,
        )
        return result

    except Exception as exc:
        logger.warning(
            "[%s] Unexpected error (%s: %s) — falling back to not-mentioned.",
            category, type(exc).__name__, exc,
        )
        return _not_mentioned(category)


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------

async def run_risk_scan(doc_id: str) -> List[RiskEntry]:
    """
    Run all 6 risk queries concurrently against the stored document index.

    Each query runs in a separate thread (asyncio.to_thread) so that the
    synchronous embedding + Claude API calls don't block the event loop.
    Total wall-clock time ≈ max(individual query latency), not their sum.
    """
    import time as _time

    doc = store.get(doc_id)
    if doc is None:
        logger.warning("run_risk_scan: unknown doc_id '%s'", doc_id)
        return []

    categories = [item["category"] for item in RISK_TAXONOMY]
    logger.info(
        "Risk scan started | doc_id=%s | %d categories: %s",
        doc_id, len(categories), ", ".join(categories),
    )
    t0 = _time.perf_counter()

    tasks = [
        asyncio.to_thread(
            _run_single_risk_query,
            doc,
            item["category"],
            item["query"],
            item["rubric"],
        )
        for item in RISK_TAXONOMY
    ]
    results = await asyncio.gather(*tasks)

    elapsed = _time.perf_counter() - t0
    summary = " | ".join(f"{r.category}={r.severity}" for r in results)
    logger.info("Risk scan complete (%.2fs) | %s", elapsed, summary)
    return list(results)
