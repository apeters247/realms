"""Internet Archive fetcher for open ethnographic monographs.

Given an archive.org details URL (https://archive.org/details/<IDENTIFIER>),
pulls the plain-text OCR output and filters to paragraphs long enough to
contain usable ethnographic context. Returns a FetchedDocument.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from realms.ingestion.fetcher import FetchedDocument, USER_AGENT

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("/app/data/archive_org")
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
MAX_BODY_CHARS = 500_000  # cap: worker chunker will then chop to ~3500 each


def _identifier_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "archive.org" not in parsed.netloc:
        return None
    match = re.match(r"^/details/([^/]+)/?", parsed.path)
    return match.group(1) if match else None


def _fetch_metadata(identifier: str) -> dict:
    resp = requests.get(
        METADATA_URL.format(identifier=identifier),
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _find_text_filename(metadata: dict) -> str | None:
    """Return the best plain-text sidecar filename from an archive.org metadata payload.

    Prefers ``*_djvu.txt`` which is the full OCR; falls back to any other ``.txt``.
    """
    files = metadata.get("files") or []
    djvu = next(
        (f["name"] for f in files
         if isinstance(f, dict) and str(f.get("name", "")).endswith("_djvu.txt")),
        None,
    )
    if djvu:
        return djvu
    txt = next(
        (f["name"] for f in files
         if isinstance(f, dict) and str(f.get("name", "")).endswith(".txt")),
        None,
    )
    return txt


def _fetch_text_file(identifier: str, filename: str) -> str:
    url = DOWNLOAD_URL.format(identifier=identifier, filename=filename)
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
        timeout=120,
    )
    if resp.status_code == 404:
        raise LookupError(f"archive.org file not found: {identifier}/{filename}")
    resp.raise_for_status()
    body = resp.text
    # Guard against HTML error pages returned with 200
    head = body.lstrip()[:256].lower()
    if head.startswith("<!doctype html") or head.startswith("<html"):
        raise LookupError(f"archive.org returned HTML instead of plaintext: {url}")
    return body


def _clean_ocr(text: str, max_chars: int = MAX_BODY_CHARS) -> str:
    """OCR pages concatenated; normalize whitespace and trim obvious noise."""
    # Remove form-feed page breaks and collapse runs of blank lines.
    text = text.replace("\x0c", "\n\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Drop very short lines that are typically page numbers / headers.
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if len(stripped) < 5 and not re.search(r"[A-Za-z]{3,}", stripped):
            continue
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned


def fetch_archive(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> FetchedDocument:
    """Fetch an archive.org item's OCR text by details URL. Cached to disk.

    Raises ``ValueError`` for non-archive.org URLs, ``LookupError`` if no
    _djvu.txt is available (e.g., audio-only or restricted items).
    """
    identifier = _identifier_from_url(url)
    if identifier is None:
        raise ValueError(f"Not an archive.org details URL: {url}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{identifier}.txt"

    title = identifier.replace("_", " ").replace("-", " ")
    if cache_path.exists():
        log.info("archive.org cache hit for %s", identifier)
        raw = cache_path.read_text(encoding="utf-8")
    else:
        log.info("Fetching archive.org %s", identifier)
        meta = _fetch_metadata(identifier)
        m_title = (meta.get("metadata") or {}).get("title")
        if isinstance(m_title, str):
            title = m_title
        elif isinstance(m_title, list) and m_title:
            title = str(m_title[0])
        filename = _find_text_filename(meta)
        if not filename:
            raise LookupError(f"archive.org {identifier}: no text sidecar in metadata")
        raw = _fetch_text_file(identifier, filename)
        cache_path.write_text(raw, encoding="utf-8")

    cleaned = _clean_ocr(raw)
    if len(cleaned) < 500:
        raise RuntimeError(f"archive.org {identifier} has <500 chars of usable text")

    content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    return FetchedDocument(
        url=url,
        title=title,
        content_text=cleaned,
        content_hash=content_hash,
        storage_path=str(cache_path),
        language="en",
    )
