"""Stage 1 integrity check: verify the extractor's quote_context appears in the source chunk.

Fast, deterministic, no LLM cost. Rejects any claim whose supporting quote can't
be located in the source text. This catches the biggest class of hallucination
(made-up quotes) before the cheaper LLM verifier runs.

Fuzziness tolerated:
- Unicode normalisation (NFC)
- Collapse whitespace runs
- Case-insensitive
- Drop combining diacritics (NFD + strip category Mn)
- Trim a few leading/trailing chars the LLM commonly adds (quotes, ellipses)
"""
from __future__ import annotations

import re
import unicodedata


_WS_RE = re.compile(r"\s+")
_EDGE_CHARS = "\"'“”‘’…[](){}<>—–-—\u00a0 \t\n"


def normalise(text: str) -> str:
    if not text:
        return ""
    # NFC first, then NFD + drop combining marks to strip diacritics.
    nfc = unicodedata.normalize("NFC", text)
    nfd = unicodedata.normalize("NFD", nfc)
    no_diacritics = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    no_diacritics = no_diacritics.lower()
    return _WS_RE.sub(" ", no_diacritics).strip()


def verify_quote(quote: str, source_chunk: str) -> bool:
    """Does ``quote`` appear (fuzzy-matched) in ``source_chunk``?

    Returns True when a normalised substring match is found.
    """
    if not quote or not source_chunk:
        return False
    q = normalise(quote.strip(_EDGE_CHARS))
    src = normalise(source_chunk)
    if not q or not src:
        return False
    # Short quotes need a length floor to avoid accidental matches on single
    # common words ("the", "and").
    if len(q) < 12:
        return False
    return q in src
