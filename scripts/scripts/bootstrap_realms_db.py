"""Create REALMS tables (idempotent). Invoked at container startup."""
from __future__ import annotations

import logging
import sys

from realms.models import Base
from realms.utils.database import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.bootstrap")


def main() -> int:
    engine = get_engine()
    log.info("Creating REALMS tables (if not exist) on %s", engine.url)
    Base.metadata.create_all(engine)
    created = sorted(Base.metadata.tables.keys())
    log.info("REALMS tables ready: %s", ", ".join(created))
    return 0


if __name__ == "__main__":
    sys.exit(main())
