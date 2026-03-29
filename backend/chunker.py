"""
Section-aware semantic chunker for Terms & Conditions documents.

Strategy:
  1. Use charOffset values to slice the full text into per-section bodies.
  2. Sentence-tokenise each section body with nltk.
  3. Greedily pack sentences into chunks up to `max_tokens`.
  4. When a chunk is full, carry the last `overlap` tokens (decoded back to text)
     into the next chunk as a prefix.
  5. Every chunk is tagged with its parent section heading.

Token counting uses tiktoken with the cl100k_base encoding (matches
text-embedding-ada-002 / text-embedding-3-* used in Feature 5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

import nltk
import tiktoken

# Download the sentence tokeniser data on first use (no-op if already present).
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

_enc = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_enc.encode(text))


@dataclass
class Chunk:
    chunk_id: str
    text: str
    heading: str
    token_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.token_count = _token_count(self.text)


def chunk_by_sections(
    text: str,
    sections: list,
    max_tokens: int = 512,
    overlap: int = 50,
) -> List[Chunk]:
    """
    Pure function: splits `text` into overlap-aware chunks that respect section
    boundaries.

    Args:
        text:       Full document body.
        sections:   List of dicts with keys 'heading' and 'char_offset'
                    (or Pydantic Section objects with .heading / .char_offset).
        max_tokens: Hard ceiling per chunk (default 512).
        overlap:    Token overlap between consecutive chunks (default 50).

    Returns:
        List of Chunk instances, each ≤ max_tokens tokens.
    """
    chunks: List[Chunk] = []

    def _heading(s) -> str:
        return s.heading if hasattr(s, "heading") else s["heading"]

    def _offset(s) -> int:
        return s.char_offset if hasattr(s, "char_offset") else s["char_offset"]

    sorted_sections = sorted(sections, key=_offset)

    for i, section in enumerate(sorted_sections):
        heading = _heading(section)
        start = _offset(section)
        end = _offset(sorted_sections[i + 1]) if i + 1 < len(sorted_sections) else len(text)
        section_text = text[start:end].strip()

        if not section_text:
            continue

        sentences = nltk.sent_tokenize(section_text)
        chunks.extend(_pack_sentences(sentences, heading, max_tokens, overlap))

    return chunks


def _pack_sentences(
    sentences: list[str],
    heading: str,
    max_tokens: int,
    overlap: int,
) -> List[Chunk]:
    """
    Greedily pack sentences into chunks.

    Sentences are kept as strings and joined with spaces so that spaces between
    sentences are preserved in the decoded output. The overlap is extracted as
    the last `overlap` token IDs from the flushed chunk, decoded back to text
    and prepended to the next chunk.
    """
    chunks: List[Chunk] = []
    current_sentences: list[str] = []
    overlap_prefix: str = ""  # decoded text carried over from previous chunk

    def _flush() -> tuple[list[int], str]:
        """Encode and emit the current chunk; return (token_ids, new_overlap_prefix)."""
        parts = ([overlap_prefix] if overlap_prefix else []) + current_sentences
        flush_text = " ".join(parts)
        flush_ids = _enc.encode(flush_text)
        chunks.append(_make_chunk(flush_ids, heading))
        new_overlap_ids = flush_ids[-overlap:] if overlap else []
        return flush_ids, (_enc.decode(new_overlap_ids) if new_overlap_ids else "")

    for sentence in sentences:
        # Detect a single sentence that already exceeds max_tokens.
        if _token_count(sentence) > max_tokens:
            if current_sentences:
                _, overlap_prefix = _flush()
                current_sentences = []

            sentence_ids = _enc.encode(sentence)
            step = max_tokens - overlap
            for window_start in range(0, len(sentence_ids), step):
                window = sentence_ids[window_start : window_start + max_tokens]
                if window:
                    chunks.append(_make_chunk(window, heading))
            overlap_prefix = _enc.decode(sentence_ids[-overlap:]) if overlap else ""
            continue

        # Compute token count of the candidate chunk (overlap prefix + accumulated + new sentence).
        candidate_parts = ([overlap_prefix] if overlap_prefix else []) + current_sentences + [sentence]
        candidate_token_count = _token_count(" ".join(candidate_parts))

        if current_sentences and candidate_token_count > max_tokens:
            _, overlap_prefix = _flush()
            current_sentences = []

        current_sentences.append(sentence)

    if current_sentences:
        _flush()

    return chunks


def _make_chunk(token_ids: list[int], heading: str) -> Chunk:
    text = _enc.decode(token_ids)
    return Chunk(chunk_id=str(uuid.uuid4()), text=text, heading=heading)
