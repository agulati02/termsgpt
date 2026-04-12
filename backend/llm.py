"""
LLM answer generation using the Claude API.

Takes the top reranked chunks and produces a grounded answer with citations.
Relevance scores from the reranker are attached to each citation after parsing.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import List, Tuple

import anthropic

from models import Citation, QueryResponse
from reranker import RankedChunk

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-0"  # full ID: claude-sonnet-4-20250514
_RELEVANCE_GATE = 0.1
_NO_COVERAGE_RESPONSE = QueryResponse(
    answer="This document does not appear to cover that topic.",
    citations=[],
)

_SYSTEM_PROMPT = (
    "You are a legal document analyst. Answer the user's question using only "
    "the provided document excerpts. For each claim, cite the section it comes "
    "from. If the excerpts do not contain enough information, say so explicitly."
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_user_message(query: str, ranked: List[RankedChunk]) -> str:
    excerpts = "\n\n".join(
        f'{i + 1}. [Section: {r.chunk.heading}]\n{r.chunk.text}'
        for i, r in enumerate(ranked)
    )
    return (
        f"{excerpts}\n\n"
        f"Question: {query}\n\n"
        'Respond ONLY in valid JSON: '
        '{"answer": "...", "citations": [{"heading": "...", "snippet": "..."}]}'
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(text: str) -> Tuple[str, list[dict]]:
    """
    Parse the LLM JSON response with a two-stage fallback:
      1. Direct json.loads on the full text.
      2. Extract the first {...} block via regex (handles markdown fences / prose wrap).
      3. Return raw text with empty citations.
    """
    def _extract(raw: str) -> Tuple[str, list[dict]]:
        data = json.loads(raw)
        return data.get("answer", ""), data.get("citations", [])

    # Attempt 1: direct parse
    try:
        return _extract(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: pull out the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return _extract(match.group(0))
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("LLM response could not be parsed as JSON; returning raw text.")
    return text, []


def _attach_scores(
    raw_citations: list[dict], ranked: List[RankedChunk]
) -> List[Citation]:
    """
    Attach relevance_score from the corresponding RankedChunk to each citation,
    matched by heading. Defaults to 0.0 when no match is found.
    """
    score_by_heading = {r.chunk.heading: r.relevance_score for r in ranked}
    return [
        Citation(
            heading=c.get("heading", ""),
            snippet=c.get("snippet", ""),
            relevance_score=score_by_heading.get(c.get("heading", ""), 0.0),
        )
        for c in raw_citations
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_answer(query: str, ranked: List[RankedChunk]) -> QueryResponse:
    """
    Generate a grounded answer using the Claude API.

    Steps:
      1. Relevance gate — if max(relevance_score) < 0.3, skip the LLM call.
      2. Build prompt and log it at DEBUG level.
      3. Call Claude; parse the JSON response.
      4. Attach relevance scores from RankedChunk objects to each citation.
    """
    if not ranked:
        logger.info("generate_answer: no ranked chunks — returning no-coverage response")
        return _NO_COVERAGE_RESPONSE

    max_score = max(r.relevance_score for r in ranked)
    logger.info(
        "generate_answer: query=%r | %d chunks | max_score=%.3f",
        query[:80], len(ranked), max_score,
    )

    if max_score < _RELEVANCE_GATE:
        logger.info(
            "Relevance gate triggered (max_score=%.3f < threshold=%.1f) — skipping LLM call.",
            max_score, _RELEVANCE_GATE,
        )
        return _NO_COVERAGE_RESPONSE

    user_message = _build_user_message(query, ranked)
    logger.debug(
        "=== LLM PROMPT ===\nSYSTEM:\n%s\n\nUSER:\n%s\n==================",
        _SYSTEM_PROMPT,
        user_message,
    )

    logger.info("Calling Claude API (model=%s, max_tokens=1024)...", _MODEL)
    t0 = time.perf_counter()
    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.RateLimitError as exc:
        logger.error(
            "RATE LIMIT hit on Anthropic API (query=%r) — %s",
            query[:80], exc,
        )
        raise
    except anthropic.APIStatusError as exc:
        logger.error(
            "Anthropic API error status=%d (query=%r) — %s",
            exc.status_code, query[:80], exc.message,
        )
        raise
    except anthropic.APIConnectionError as exc:
        logger.error("Anthropic API connection error (query=%r) — %s", query[:80], exc)
        raise

    elapsed = time.perf_counter() - t0
    usage = response.usage
    logger.info(
        "Claude API response (%.2fs) | tokens in=%d out=%d | stop_reason=%s",
        elapsed, usage.input_tokens, usage.output_tokens, response.stop_reason,
    )

    raw_text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    answer, raw_citations = _parse_response(raw_text)
    citations = _attach_scores(raw_citations, ranked)

    logger.info("generate_answer: returning %d citation(s)", len(citations))
    return QueryResponse(answer=answer, citations=citations)
