"""Entrypoint for culture/region promotion — one-shot or scheduled."""
from __future__ import annotations

import logging
import sys

from realms.ingestion.promote_dimensions import promote_all
from realms.utils.database import get_db_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("realms.promote")


def main() -> int:
    with get_db_session() as session:
        stats = promote_all(session)
    log.info("Promotion complete: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
