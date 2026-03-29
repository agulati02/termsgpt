import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tiktoken
from chunker import Chunk, chunk_by_sections, _token_count

_enc = tiktoken.get_encoding("cl100k_base")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sections(*headings_and_offsets):
    """Build a plain-dict sections list from (heading, char_offset) pairs."""
    return [{"heading": h, "char_offset": o} for h, o in headings_and_offsets]


# ---------------------------------------------------------------------------
# Test 1 — Single short section produces exactly one chunk
# ---------------------------------------------------------------------------

def test_single_short_section_one_chunk():
    text = "You agree to our terms. We may update these terms at any time."
    sections = _sections(("Introduction", 0))

    chunks = chunk_by_sections(text, sections)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, Chunk)
    assert chunk.heading == "Introduction"
    assert chunk.token_count <= 512
    # Key words from both sentences must survive in the output.
    assert "agree" in chunk.text
    assert "update" in chunk.text


# ---------------------------------------------------------------------------
# Test 2 — Long section is split into multiple overlapping chunks
# ---------------------------------------------------------------------------

def test_long_section_splits_with_overlap():
    # 60 repetitions × ~11 tokens/sentence ≈ 660 tokens — comfortably over 512.
    sentence = "The company reserves the right to change these policies without notice."
    body = (" " + sentence) * 60
    sections = _sections(("Data Policy", 0))

    chunks = chunk_by_sections(body, sections, max_tokens=512, overlap=50)

    assert len(chunks) >= 2, f"Expected ≥2 chunks, got {len(chunks)}"

    for chunk in chunks:
        assert chunk.token_count <= 512, f"Chunk exceeded max_tokens: {chunk.token_count}"
        assert chunk.heading == "Data Policy"

    # Verify overlap: the decoded last-50-tokens of chunk[i] should be a prefix
    # of chunk[i+1].text (text-level check; avoids decode→re-encode round-trip issues).
    for i in range(len(chunks) - 1):
        overlap_text = _enc.decode(_enc.encode(chunks[i].text)[-50:])
        assert chunks[i + 1].text.startswith(overlap_text), (
            f"Chunk {i+1} does not start with the overlap tail of chunk {i}.\n"
            f"  Expected prefix: {overlap_text!r}\n"
            f"  Chunk start:     {chunks[i + 1].text[:len(overlap_text) + 20]!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Multiple sections produce chunks correctly labelled per section
# ---------------------------------------------------------------------------

def test_multiple_sections_labelled_correctly():
    privacy_body = "We collect your name, email and usage data. " * 3
    liability_body = "Our liability is limited to the amount you paid us. " * 3

    full_text = privacy_body + liability_body
    sections = _sections(
        ("Privacy Policy", 0),
        ("Limitation of Liability", len(privacy_body)),
    )

    chunks = chunk_by_sections(full_text, sections)

    privacy_chunks = [c for c in chunks if c.heading == "Privacy Policy"]
    liability_chunks = [c for c in chunks if c.heading == "Limitation of Liability"]

    assert len(privacy_chunks) >= 1, "Expected at least one Privacy Policy chunk"
    assert len(liability_chunks) >= 1, "Expected at least one Liability chunk"

    for chunk in privacy_chunks:
        assert "paid us" not in chunk.text, "Privacy chunk contains liability text"
    for chunk in liability_chunks:
        assert "email" not in chunk.text, "Liability chunk contains privacy text"


# ---------------------------------------------------------------------------
# Test 4 — All chunk IDs are unique UUIDs
# ---------------------------------------------------------------------------

def test_chunk_ids_are_unique():
    sentence = "The company may update terms at any time without prior notice to users."
    body = (" " + sentence) * 60
    sections = _sections(("Terms", 0))

    chunks = chunk_by_sections(body, sections, max_tokens=512, overlap=50)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs detected"


# ---------------------------------------------------------------------------
# Test 5 — Empty section body produces no chunks
# ---------------------------------------------------------------------------

def test_empty_section_produces_no_chunks():
    sections = _sections(("Empty Section", 0))
    chunks = chunk_by_sections("   ", sections)
    assert chunks == [], f"Expected no chunks for whitespace-only text, got {chunks}"
