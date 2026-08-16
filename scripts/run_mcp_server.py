"""CLI entry point for the REALMS MCP server.

Usage:
  python -m scripts.run_mcp_server                    # stdio (Claude Desktop)
  python -m scripts.run_mcp_server --transport http   # HTTP/SSE (marketplace)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realms.mcp.server import main

if __name__ == "__main__":
    main()
