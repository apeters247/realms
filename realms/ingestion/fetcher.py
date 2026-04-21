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
    """Fetch full article plain text via the action API.

    Raises ``LookupError`` if the title is missing or a disambiguation stub.
    """
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
        if "missing" in page:
            raise LookupError(f"Wikipedia title missing: {title}")
        extract = page.get("extract")
        if extract:
            return extract
    raise LookupError(f"Wikipedia returned no extract for: {title}")


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


# ─── Wikisource (MediaWiki API, different host) ─────────────────────────

def _wikisource_title_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if "wikisource.org" not in parsed.netloc:
        return None
    m = re.match(r"^/wiki/(.+)$", parsed.path)
    return unquote(m.group(1)) if m else None


def _wikisource_plaintext(lang: str, title: str) -> str:
    """Wikisource articles are typically Page:-namespace transclusions, so the
    MediaWiki ``extracts`` extension returns an empty string for them. Use
    ``action=parse&prop=text`` to get rendered HTML, then strip to plain
    text via BeautifulSoup.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 required for wikisource fetch") from exc

    resp = requests.get(
        f"https://{lang}.wikisource.org/w/api.php",
        params={
            "action": "parse",
            "page": title,
            "prop": "text",
            "formatversion": "2",
            "format": "json",
            "redirects": "1",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise LookupError(f"Wikisource error for {title}: {data['error'].get('code')}")
    parse = data.get("parse", {})
    html = parse.get("text", "") or ""
    if isinstance(html, dict):
        html = html.get("*", "")
    if not html:
        raise LookupError(f"Wikisource returned no HTML for: {title}")

    soup = BeautifulSoup(html, "html.parser")
    for sel in [".ws-noexport", ".noprint", ".mw-references", ".reference",
                ".reflist", "table.footer", "span.pagenum"]:
        for tag in soup.select(sel):
            tag.decompose()
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) < 100:
        raise LookupError(f"Wikisource text too short for {title} ({len(text)} chars)")
    return text


def fetch_wikisource(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> FetchedDocument:
    title = _wikisource_title_from_url(url)
    if title is None:
        raise ValueError(f"Not a Wikisource URL: {url}")
    lang_match = re.match(r"https?://([a-z]{2})\.wikisource\.org", url)
    lang = lang_match.group(1) if lang_match else "en"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.txt"
    if cache_path.exists():
        content_text = cache_path.read_text(encoding="utf-8")
    else:
        log.info("Fetching (wikisource) %s", url)
        content_text = _wikisource_plaintext(lang, title)
        if not content_text.strip():
            raise RuntimeError(f"Empty content for {url}")
        cache_path.write_text(content_text, encoding="utf-8")
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    return FetchedDocument(
        url=url,
        title=title.split("/")[-1].replace("_", " "),
        content_text=content_text,
        content_hash=content_hash,
        storage_path=str(cache_path),
        language=lang,
    )


# ─── Generic HTML fetcher (for theoi, perseus, archive.org, journal landing) ─

def fetch_html(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> FetchedDocument:
    """Strip HTML → text. Works for any static page."""
    try:
        from bs4 import BeautifulSoup  # part of realms deps
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 required for fetch_html") from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.txt"
    if cache_path.exists():
        content_text = cache_path.read_text(encoding="utf-8")
        title_line = content_text.split("\n", 1)[0]
        title = title_line.lstrip("# ").strip() or url
    else:
        log.info("Fetching (html) %s", url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT},
            timeout=60, allow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip scripts, styles, navs — keep the body of the article.
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title_el = soup.find("title") or soup.find("h1")
        title = (title_el.get_text(strip=True) if title_el else url)[:200]

        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(id=re.compile(r"mw-content-text|main|content", re.I))
            or soup.body
        )
        text = (main or soup).get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) < 200:
            raise RuntimeError(f"Empty / too-short HTML for {url} ({len(text)} chars)")
        content_text = f"# {title}\n\n{text}"
        cache_path.write_text(content_text, encoding="utf-8")

    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    return FetchedDocument(
        url=url,
        title=title,
        content_text=content_text,
        content_hash=content_hash,
        storage_path=str(cache_path),
        language="en",
    )
