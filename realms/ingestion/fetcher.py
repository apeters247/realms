"""Wikipedia article fetcher with SHA256 hash + on-disk cache."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import requests

log = logging.getLogger(__name__)

USER_AGENT = "REALMS-Ingestor/1.0 (research; contact: realms-project)"
DEFAULT_CACHE_DIR = Path("/app/data/raw")


@dataclass
class FetchedDocument:
    url: str
    title: str
    content_text: str
    content_hash: str
    storage_path: str
    language: str


def _wikipedia_title_from_url(url: str) -> Optional[str]:
    """Parse '/wiki/<Title>' from a Wikipedia URL."""
    parsed = urlparse(url)
    if "wikipedia.org" not in parsed.netloc:
        return None
    match = re.match(r"^/wiki/(.+)$", parsed.path)
    if not match:
        return None
    return unquote(match.group(1))


def _wikipedia_summary_api(lang: str, title: str) -> dict:
    """Fetch the REST summary endpoint (brief extract)."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _wikipedia_plaintext_api(lang: str, title: str) -> str:
    """Fetch full article plain text via the action API."""
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
    }
    resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for _pageid, page in pages.items():
        extract = page.get("extract")
        if extract:
            return extract
    return ""


def fetch_wikipedia(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> FetchedDocument:
    """Fetch a Wikipedia article by URL. Returns a FetchedDocument.

    Content is cached to disk keyed by SHA256 hash of the URL so re-fetches
    are deterministic during development.
    """
    title = _wikipedia_title_from_url(url)
    if title is None:
        raise ValueError(f"Not a Wikipedia URL: {url}")

    lang_match = re.match(r"https?://([a-z]{2})\.wikipedia\.org", url)
    lang = lang_match.group(1) if lang_match else "en"

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.txt"

    if cache_path.exists():
        log.info("Cache hit for %s", url)
        content_text = cache_path.read_text(encoding="utf-8")
    else:
        log.info("Fetching %s", url)
        content_text = _wikipedia_plaintext_api(lang, title)
        if not content_text.strip():
            raise RuntimeError(f"Empty content for {url}")
        cache_path.write_text(content_text, encoding="utf-8")

    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    display_title = title.replace("_", " ")
    return FetchedDocument(
        url=url,
        title=display_title,
        content_text=content_text,
        content_hash=content_hash,
        storage_path=str(cache_path),
        language=lang,
    )
