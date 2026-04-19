"""PubMed fetcher via NCBI E-utilities.

Given a PubMed URL (https://pubmed.ncbi.nlm.nih.gov/<PMID>/), pulls the abstract
plus metadata and returns it as a FetchedDocument compatible with the worker.

E-utilities are free, no API key required at the polite rate (<=3 req/sec).
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

from realms.ingestion.fetcher import FetchedDocument, USER_AGENT

log = logging.getLogger(__name__)

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DEFAULT_CACHE_DIR = Path("/app/data/pubmed")
POLITE_DELAY_SECONDS = 0.4


def _pmid_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "pubmed.ncbi.nlm.nih.gov" not in parsed.netloc:
        return None
    match = re.search(r"/(\d+)/?", parsed.path)
    return match.group(1) if match else None


def _efetch_xml(pmid: str) -> str:
    params = {"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"}
    resp = requests.get(
        EFETCH_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    time.sleep(POLITE_DELAY_SECONDS)
    return resp.text


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    # Join all descendant text (abstract often has sub-tags)
    return " ".join((t or "").strip() for t in node.itertext()).strip()


def _parse_pubmed_xml(xml_text: str, pmid: str) -> tuple[str, str]:
    """Return (title, body_text) from an efetch PubMedArticle XML."""
    root = ET.fromstring(xml_text)
    article = root.find(".//PubmedArticle/MedlineCitation/Article")
    if article is None:
        raise LookupError(f"PubMed PMID {pmid} returned no Article element")

    title = _text(article.find("ArticleTitle"))
    journal = _text(article.find("Journal/Title"))
    year_node = article.find("Journal/JournalIssue/PubDate/Year")
    year = _text(year_node)

    authors: list[str] = []
    for author in article.findall("AuthorList/Author"):
        last = _text(author.find("LastName"))
        fore = _text(author.find("ForeName"))
        if last:
            authors.append(f"{fore} {last}".strip())

    abstract_nodes = article.findall("Abstract/AbstractText")
    abstract_parts: list[str] = []
    for node in abstract_nodes:
        label = node.get("Label")
        text = _text(node)
        if not text:
            continue
        abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = "\n\n".join(abstract_parts)

    # Assemble a chunkable body. Title + citation header + abstract.
    header_bits = [title]
    if authors:
        header_bits.append("Authors: " + ", ".join(authors[:10]))
    if journal:
        header_bits.append(f"Journal: {journal}" + (f" ({year})" if year else ""))
    body = "\n".join(b for b in header_bits if b).strip()
    if abstract:
        body = body + "\n\n" + abstract
    return title, body


def fetch_pubmed(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> FetchedDocument:
    """Fetch a PubMed abstract by URL. Cached to disk by PMID.

    Raises ``ValueError`` for non-PubMed URLs and ``LookupError`` for missing PMIDs.
    """
    pmid = _pmid_from_url(url)
    if pmid is None:
        raise ValueError(f"Not a PubMed URL: {url}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{pmid}.xml"

    if cache_path.exists():
        log.info("PubMed cache hit for PMID %s", pmid)
        xml_text = cache_path.read_text(encoding="utf-8")
    else:
        log.info("Fetching PubMed PMID %s", pmid)
        xml_text = _efetch_xml(pmid)
        cache_path.write_text(xml_text, encoding="utf-8")

    title, body = _parse_pubmed_xml(xml_text, pmid)
    if not body.strip():
        raise RuntimeError(f"PubMed PMID {pmid} has no usable content (no abstract)")

    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return FetchedDocument(
        url=url,
        title=title or f"PubMed {pmid}",
        content_text=body,
        content_hash=content_hash,
        storage_path=str(cache_path),
        language="en",
    )


def esearch_pmids(query: str, retmax: int = 5) -> list[str]:
    """Return a list of PMIDs matching ``query``.

    Used by the seed script to generate candidate PubMed sources per entity.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
        "sort": "relevance",
    }
    resp = requests.get(
        ESEARCH_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    time.sleep(POLITE_DELAY_SECONDS)
    data = resp.json()
    return list(data.get("esearchresult", {}).get("idlist", []) or [])
