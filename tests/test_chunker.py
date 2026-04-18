"""Unit tests for the text chunker."""
import pytest

from realms.ingestion.chunker import chunk_text


def test_short_text_returns_one_chunk():
    text = "This is a short article about nothing in particular. " * 5
    chunks = chunk_text(text, max_chars=4000)
    assert len(chunks) == 1
    assert "short article" in chunks[0].text


def test_long_text_splits_at_paragraph_boundaries():
    paragraphs = ["Paragraph %d. %s" % (i, "word " * 80) for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=1500)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 2000  # soft cap; paragraph boundaries may overshoot


def test_section_headings_tracked():
    text = (
        "Intro paragraph about things. " * 10 + "\n\n"
        "== History ==\n\n"
        "Historical paragraph about things. " * 10 + "\n\n"
        "== Beliefs ==\n\n"
        "Belief paragraph about things. " * 10
    )
    chunks = chunk_text(text, max_chars=4000)
    sections = {c.section_title for c in chunks}
    assert "History" in sections or "Beliefs" in sections


def test_tiny_text_returns_empty():
    chunks = chunk_text("hi", max_chars=4000)
    assert chunks == []


def test_chunks_have_offsets():
    text = "Para one. " * 50 + "\n\n" + "Para two. " * 50
    chunks = chunk_text(text, max_chars=600)
    assert len(chunks) >= 2
    offsets = [c.char_offset for c in chunks]
    assert offsets == sorted(offsets)
