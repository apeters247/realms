"""Stream S — per-entity OpenGraph image generator.

Renders a 1200×630 PNG at request time. Uses Pillow (already in Python
image). Cached on disk at data/og_cache/<entity_id>.png.

Route:
    GET /og/entity/{entity_id}.png
    GET /og/default.png   (fallback used by the Astro <meta og:image>)

The Astro entity pages will reference ``/og/entity/{id}.png`` via their
``ogImage`` prop so Twitter, Reddit, and Slack previews show a
per-entity card.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from realms.models import Entity
from realms.utils.database import get_db_session

log = logging.getLogger(__name__)

router = APIRouter()


CACHE_DIR = Path("data/og_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Paper-cream background, warm ink, oxblood accent — matches site palette.
BG_RGB = (250, 249, 246)         # #faf9f6
INK_RGB = (26, 24, 21)           # #1a1815
INK_DIM_RGB = (74, 68, 58)
INK_FAINT_RGB = (155, 146, 130)
ACCENT_RGB = (122, 31, 19)       # #7a1f13
RULE_RGB = (212, 204, 188)


def _render_png(entity: Entity) -> bytes:
    """Render a 1200×630 OG card PNG for one entity."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow required for OG rendering") from exc

    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG_RGB)
    d = ImageDraw.Draw(img)

    # Attempt to locate Fraunces (bundled with the web-next static build);
    # fall back to DejaVu Serif (ships with pillow on debian).
    serif_paths = [
        "/app/web-next/node_modules/@fontsource-variable/fraunces/files/fraunces-latin-wght-normal.woff2",  # not a truetype
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    sans_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    def _first_font(candidates, size):
        for p in candidates:
            if Path(p).exists():
                try:
                    return ImageFont.truetype(p, size=size)
                except Exception:  # noqa: BLE001
                    continue
        return ImageFont.load_default()

    title_font = _first_font(serif_paths, 76)
    subtitle_font = _first_font(sans_paths, 22)
    body_font = _first_font(sans_paths, 28)

    # Top rule
    d.rectangle([(0, 0), (W, 6)], fill=ACCENT_RGB)

    # Small-caps label
    d.text((60, 60), "REALMS · ARCHIVE OF ENTITIES",
           font=subtitle_font, fill=INK_FAINT_RGB)

    # Wrap the entity name so it fits within 1080px
    name = (entity.name or "(unnamed)")
    max_title_width = W - 120
    lines = _wrap_text(d, name, title_font, max_title_width)
    y = 140
    for line in lines[:3]:
        d.text((60, y), line, font=title_font, fill=INK_RGB)
        y += 92

    # Type + tradition + realm pill row
    info_parts = []
    if entity.entity_type:
        info_parts.append(entity.entity_type)
    if entity.realm:
        info_parts.append(entity.realm)
    if entity.cultural_associations:
        info_parts.append(str(entity.cultural_associations[0]))
    if info_parts:
        info = "  ·  ".join(info_parts)
        d.text((60, y + 10), info, font=body_font, fill=INK_DIM_RGB)

    # Footer rule
    d.rectangle([(60, H - 90), (W - 60, H - 89)], fill=RULE_RGB)
    # Footer tagline + URL
    d.text((60, H - 70), "A provenance-tracked knowledge base of spiritual entities",
           font=subtitle_font, fill=INK_DIM_RGB)
    d.text((60, H - 40), "realms.cloud",
           font=subtitle_font, fill=ACCENT_RGB)

    # Domain-agnostic: write REALMS wordmark on right edge
    d.text((W - 160, H - 40), f"#{entity.id}",
           font=subtitle_font, fill=INK_FAINT_RGB)

    from io import BytesIO
    buf = BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """Simple greedy wrap so long names display on multiple lines."""
    words = text.split()
    if not words:
        return [text]
    lines = [words[0]]
    for word in words[1:]:
        candidate = lines[-1] + " " + word
        w = draw.textlength(candidate, font=font)
        if w <= max_width:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


@router.get("/entity/{entity_id}.png")
async def entity_og(entity_id: int):
    cache_path = CACHE_DIR / f"{entity_id}.png"
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="image/png")

    with get_db_session() as session:
        entity = session.execute(
            select(Entity).where(Entity.id == entity_id)
        ).scalars().first()
        if entity is None:
            raise HTTPException(404, detail="entity not found")
        try:
            png = _render_png(entity)
        except Exception as exc:  # noqa: BLE001
            log.warning("OG render failed for %d: %s", entity_id, exc)
            raise HTTPException(500, detail=f"render failed: {exc}")

    try:
        cache_path.write_bytes(png)
    except OSError:
        log.warning("could not cache OG PNG for %d", entity_id)

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800, stale-while-revalidate=86400"},
    )


@router.get("/default.png")
async def default_og():
    """Non-entity fallback OG image (used by home, browse, collections, etc.)."""
    from PIL import Image, ImageDraw, ImageFont
    cache_path = CACHE_DIR / "_default.png"
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="image/png")

    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG_RGB)
    d = ImageDraw.Draw(img)
    serif_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    sans_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    def _first(c, s):
        for p in c:
            if Path(p).exists():
                try:
                    return ImageFont.truetype(p, size=s)
                except Exception:  # noqa: BLE001
                    continue
        return ImageFont.load_default()
    title_font = _first(serif_paths, 88)
    sub_font = _first(sans_paths, 28)

    d.rectangle([(0, 0), (W, 6)], fill=ACCENT_RGB)
    d.text((60, 180), "REALMS", font=title_font, fill=INK_RGB)
    d.text((60, 290),
           "Research Entity Archive for Light",
           font=sub_font, fill=INK_DIM_RGB)
    d.text((60, 330),
           "& Metaphysical Spirit Hierarchies",
           font=sub_font, fill=INK_DIM_RGB)
    d.text((60, H - 40), "Provenance-tracked, CC-BY-4.0",
           font=sub_font, fill=ACCENT_RGB)

    from io import BytesIO
    buf = BytesIO()
    img.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    try:
        cache_path.write_bytes(png)
    except OSError:
        pass
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})
