"""Unit tests for the new Phase 3 fetchers.

These tests avoid network I/O by exercising the URL parsing and OCR cleaner
directly. Live-network tests are gated behind an ``REALMS_LIVE_FETCH`` env var.
"""
from __future__ import annotations

import os

import pytest

from realms.ingestion import archive_fetcher, pubmed_fetcher


# ---- URL parsing ----------------------------------------------------------

def test_pubmed_pmid_parse_valid():
    assert pubmed_fetcher._pmid_from_url("https://pubmed.ncbi.nlm.nih.gov/12345678/") == "12345678"


def test_pubmed_pmid_parse_no_trailing_slash():
    assert pubmed_fetcher._pmid_from_url("https://pubmed.ncbi.nlm.nih.gov/12345678") == "12345678"


def test_pubmed_pmid_parse_non_pubmed():
    assert pubmed_fetcher._pmid_from_url("https://example.com/foo") is None


def test_archive_identifier_parse_valid():
    got = archive_fetcher._identifier_from_url("https://archive.org/details/polynesianmythol00grey_0")
    assert got == "polynesianmythol00grey_0"


def test_archive_identifier_parse_non_archive():
    assert archive_fetcher._identifier_from_url("https://example.com/details/foo") is None


# ---- OCR cleaner ----------------------------------------------------------

def test_clean_ocr_removes_short_noise_lines():
    noisy = "\n".join([
        "Valid paragraph line one with words.",
        "12",
        "Another valid line with plenty of characters.",
        "",
        "Third real paragraph describing some content.",
    ])
    out = archive_fetcher._clean_ocr(noisy)
    assert "Valid paragraph line one" in out
    assert "Another valid line" in out
    assert "\n12\n" not in out


def test_clean_ocr_caps_size():
    big = "x" * 2_000_000
    out = archive_fetcher._clean_ocr(big, max_chars=1000)
    assert len(out) == 1000


def test_find_text_filename_prefers_djvu():
    meta = {"files": [
        {"name": "foo.pdf"},
        {"name": "foo_other.txt"},
        {"name": "foo_djvu.txt"},
    ]}
    assert archive_fetcher._find_text_filename(meta) == "foo_djvu.txt"


def test_find_text_filename_fallback_txt():
    meta = {"files": [{"name": "foo.pdf"}, {"name": "foo.txt"}]}
    assert archive_fetcher._find_text_filename(meta) == "foo.txt"


def test_find_text_filename_none_available():
    meta = {"files": [{"name": "foo.pdf"}, {"name": "foo.epub"}]}
    assert archive_fetcher._find_text_filename(meta) is None


# ---- Live network tests (gated) -------------------------------------------

@pytest.mark.skipif(
    os.getenv("REALMS_LIVE_FETCH") != "1",
    reason="live-network test; set REALMS_LIVE_FETCH=1 to run",
)
def test_live_pubmed_fetch():
    pmids = pubmed_fetcher.esearch_pmids("ayahuasca shamanism", retmax=1)
    assert pmids, "esearch should return at least one PMID"
    doc = pubmed_fetcher.fetch_pubmed(f"https://pubmed.ncbi.nlm.nih.gov/{pmids[0]}/")
    assert doc.title
    assert len(doc.content_text) > 100


@pytest.mark.skipif(
    os.getenv("REALMS_LIVE_FETCH") != "1",
    reason="live-network test; set REALMS_LIVE_FETCH=1 to run",
)
def test_live_archive_fetch():
    doc = archive_fetcher.fetch_archive("https://archive.org/details/polynesianmythol00grey_0")
    assert "POLYNESIAN" in doc.content_text.upper() or "Polynesian" in doc.title
    assert len(doc.content_text) > 10_000
