"""Paragraph-based chunking with soft token cap (approximated by chars)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    char_offset: int
    section_title: str | None


MAX_CHUNK_CHARS = 3500  # ~800-900 tokens, safe for most context windows
MIN_CHUNK_CHARS = 200


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Split article text into chunks bounded by ``max_chars``.

    Paragraphs are preserved; oversize paragraphs are split on sentence boundaries.
    Wikipedia section headings (`== Section ==`) are tracked and attached to chunks.
    """
    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    offset = 0
    cursor = 0
    section: str | None = None

    lines = text.split("\n")
    for raw_line in lines:
        line = raw_line.rstrip()
        line_start = cursor
        cursor += len(raw_line) + 1  # +1 for the newline

        # Wikipedia section markers look like "== Heading ==" or "=== Sub ==="
        stripped = line.strip()
        if stripped.startswith("==") and stripped.endswith("==") and len(stripped) > 4:
            # Flush any pending chunk under the previous section
            if current_len >= MIN_CHUNK_CHARS:
                chunks.append(Chunk(
                    text="\n".join(current).strip(),
                    char_offset=offset,
                    section_title=section,
                ))
                current = []
                current_len = 0
                offset = line_start
            section = stripped.strip("= ").strip()
            continue

        if not line:
            # paragraph boundary
            if current_len >= max_chars:
                chunks.append(Chunk(
                    text="\n".join(current).strip(),
                    char_offset=offset,
                    section_title=section,
                ))
                current = []
                current_len = 0
                offset = cursor
            else:
                current.append("")
                current_len += 1
            continue

        if current_len + len(line) + 1 > max_chars and current_len >= MIN_CHUNK_CHARS:
            chunks.append(Chunk(
                text="\n".join(current).strip(),
                char_offset=offset,
                section_title=section,
            ))
            current = [line]
            current_len = len(line)
            offset = line_start
        else:
            current.append(line)
            current_len += len(line) + 1

    if current and "\n".join(current).strip():
        chunks.append(Chunk(
            text="\n".join(current).strip(),
            char_offset=offset,
            section_title=section,
        ))

    return [c for c in chunks if len(c.text) >= MIN_CHUNK_CHARS]
