# Contributing to REALMS

## Code Style

### Python

- **Line length:** 88 characters (Black default)
- **Type hints:** Required for all function signatures (Python 3.11)
- **Imports:** Standard library → third-party → project, groups separated by blank line
- **Docstrings:** Google-style for all public functions

```python
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def my_function(session: Session, name: str) -> Optional[dict[str, Any]]:
    """One-line description.
    
    Args:
        session: Active database session.
        name: Entity name to look up.
    
    Returns:
        Entity dict or None if not found.
    """
    ...
```

### TypeScript / Svelte

- **TypeScript:** Strict mode, types defined in `src/lib/types.ts`
- **Components:** Svelte 5 runes (`$state`, `$derived`, `$effect`)
- **Astro:** Prefer `.astro` for static content, `.svelte` for interactive islands

### Commit Messages

Follow conventional commits:

```
feat: add temporal filter to entity search endpoint
fix: handle null cultural_associations in entity detail
docs: add frontend architecture documentation
test: add integration test for trigram search
refactor: extract entity normalization to separate service
```

## Pull Request Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run tests: `docker compose exec realms-api pytest tests/ -v`
4. Run lint: `docker compose exec realms-api ruff check .`
5. Run type check (Python): `docker compose exec realms-api mypy realms/`
6. Run frontend check: `docker compose exec realms-api npm run check --prefix /app/web-next`
7. Submit PR with description of changes

## Code Review Guidelines

### What We Look For

- **Provenance preservation** — Every new data field must track its source
- **Backward compatibility** — API changes should not break existing clients
- **Error handling** — LLM calls, database operations, external APIs all fail; handle gracefully
- **Testing** — New features need tests (integration for API, unit for pure logic)
- **Type safety** — Type hints everywhere, avoid `Any` where possible

### What We Avoid

- Hardcoded prompts in Python code (prompts live in `realms/ingestion/prompts/`)
- Direct SQL queries (use SQLAlchemy ORM)
- Blocking operations in API routes (use async where possible)
- Adding new dependencies without discussion

## Testing

```bash
# Run all tests
docker compose exec realms-api pytest tests/ -v

# Run unit tests only (fast, no DB)
docker compose exec realms-api pytest tests/ -m unit -v

# Run with coverage
docker compose exec realms-api pytest tests/ --cov=realms tests/ --cov-report=term-missing
```

## Environment

All development happens inside Docker containers. Never use local Python environments — the Docker environment is the source of truth.

### Code Quality Tools

```bash
# Format
docker compose exec realms-api ruff format .

# Lint
docker compose exec realms-api ruff check .

# Type check
docker compose exec realms-api mypy realms/ --ignore-missing-imports

# Frontend
cd web-next && npm run check
```

## Project Architecture Notes

- **No circular imports** — Models import nothing from `api/` or `services/`
- **Services are stateless** — They receive a `Session` and return data
- **Routes are thin** — Parse request, call service, return response
- **Scripts are self-contained** — Can import from `realms.*` but not from each other
- **Prompts are files** — LLM prompts are `.md` files in `realms/ingestion/prompts/`, not strings in code
