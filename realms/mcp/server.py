"""MCP Server for REALMS.

Exposes the entity knowledge base as MCP tools that AI agents
(Claude Code, Cursor, etc.) can discover and call.

Usage:
  # stdio mode (Claude Desktop, Cursor)
  python -m realms.mcp.server

  # HTTP/SSE mode (for marketplace hosting)
  python -m realms.mcp.server --transport http --port 8002
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

import httpx

log = logging.getLogger(__name__)

API_ORIGIN = os.getenv("REALMS_API_ORIGIN", "http://127.0.0.1:8005")
API_KEY = os.getenv("REALMS_API_KEY", "")
MCP_SERVER_NAME = "realms-entity-knowledge-base"
MCP_SERVER_VERSION = "1.0.0"

# Per-connection API key for HTTP/SSE mode
_connection_api_key: str = ""


def _api(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_ORIGIN}{path}"
    key = _connection_api_key or API_KEY
    headers = {}
    if key:
        headers["X-API-Key"] = key
    resp = httpx.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def handle_call(tool_name: str, arguments: dict[str, Any]) -> str:
    try:
        if tool_name == "search_entities":
            return json.dumps(_api("/entities/", arguments), indent=2)
        elif tool_name == "get_entity":
            eid = arguments.get("entity_id")
            return json.dumps(_api(f"/entities/{eid}"), indent=2)
        elif tool_name == "get_entity_relationships":
            eid = arguments.get("entity_id")
            return json.dumps(_api(f"/entities/{eid}/relationships"), indent=2)
        elif tool_name == "search_similar":
            return json.dumps(_api("/search/similar", arguments), indent=2)
        elif tool_name == "get_corroboration":
            eid = arguments.get("entity_id")
            return json.dumps(_api(f"/corroboration/{eid}"), indent=2)
        elif tool_name == "get_statistics":
            return json.dumps(_api("/stats/"), indent=2)
        elif tool_name == "global_search":
            return json.dumps(_api("/search/", {"q": arguments.get("q", "")}), indent=2)
        elif tool_name == "get_entity_graph":
            eid = arguments.get("entity_id")
            depth = arguments.get("depth", 2)
            return json.dumps(_api(f"/graph/ego/{eid}", {"depth": depth}), indent=2)
        else:
            return json.dumps({"error": f"unknown tool: {tool_name}"})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"API error: {exc.response.status_code}", "detail": exc.response.text[:500]})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


TOOLS = [
    {
        "name": "search_entities",
        "description": "Search the REALMS entity knowledge base. Returns entities with their type, alignment, realm, and confidence. Use this to find spiritual beings by name, type, culture, or region.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query (name, description)"},
                "entity_type": {"type": "string", "description": "Filter: deity, nature_spirit, demonic, angelic, ancestor, animal_ally, human_specialist, plant_spirit"},
                "alignment": {"type": "string", "description": "Filter: beneficial, neutral, malevolent, protective, ambiguous"},
                "realm": {"type": "string", "description": "Filter: earth, sky, underworld, water, forest, mountain, hyperspace, intermediate"},
                "culture_id": {"type": "integer", "description": "Filter by culture ID"},
                "region_id": {"type": "integer", "description": "Filter by region ID"},
                "confidence_min": {"type": "number", "description": "Minimum consensus confidence (0-1)"},
                "page": {"type": "integer", "description": "Page number"},
                "per_page": {"type": "integer", "description": "Results per page (max 100)"},
            },
        },
    },
    {
        "name": "get_entity",
        "description": "Get full detail for a specific entity by ID. Returns description, alternate names, powers, domains, relationships, sources, extractions, temporal data, external IDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer", "description": "Entity ID"},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "get_entity_relationships",
        "description": "Get outgoing typed relationships for a specific entity. Shows parent_of, sibling_of, consort_of, allied_with, enemy_of, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer", "description": "Entity ID"},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "global_search",
        "description": "Full-text search across entities, classes, cultures, and sources. Returns categorized results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query"},
            },
            "required": ["q"],
        },
    },
    {
        "name": "search_similar",
        "description": "Fuzzy name matching using trigram similarity. Use for variant spellings (e.g. 'xapiri' finds 'Xapiripë').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Name to search"},
                "threshold": {"type": "number", "description": "Similarity threshold 0.05-0.95"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["q"],
        },
    },
    {
        "name": "get_corroboration",
        "description": "Get corroboration tier and source evidence for an entity. Returns Tier 0-3 badge and sources grouped by type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer", "description": "Entity ID"},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "get_entity_graph",
        "description": "Get ego subgraph for an entity — its relationships visualized as a Cytoscape.js-compatible node-edge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer", "description": "Center entity ID"},
                "depth": {"type": "integer", "description": "BFS depth (1-3)"},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "get_statistics",
        "description": "Get aggregate corpus statistics: total entities by type, realm, alignment, culture, avg confidence, sources processed.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def create_stdio_server():
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server(MCP_SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**t) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = await handle_call(name, arguments)
        return [TextContent(type="text", text=result)]

    return server


def run_stdio():
    import anyio
    from mcp.server.stdio import stdio_server

    server = create_stdio_server()
    async def _run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    anyio.run(_run)


def run_http(host: str = "0.0.0.0", port: int = 8002):
    from mcp.server import Server
    from mcp.types import TextContent, Tool
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    import mcp.server.sse

    server = Server(MCP_SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**t) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = await handle_call(name, arguments)
        return [TextContent(type="text", text=result)]

    sse_app = mcp.server.sse.SseServerTransport("/mcp/v1/messages")

    async def handle_sse(request):
        global _connection_api_key
        _connection_api_key = request.query_params.get("api_key", "")
        async with sse_app.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        _connection_api_key = ""

    async def asgi_messages(scope, receive, send):
        scope["path"] = "/mcp/v1/messages"
        await sse_app.handle_post_message(scope, receive, send)

    app = Starlette(
        routes=[
            Route("/mcp/v1/sse", endpoint=handle_sse),
            Mount("/mcp/v1/messages", app=asgi_messages),
        ],
        middleware=[Middleware(CORSMiddleware, allow_origins=["*"])],
    )

    import uvicorn
    log.info("REALMS MCP server listening on http://%s:%d/mcp/v1/sse", host, port)
    uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="REALMS MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    if args.transport == "http":
        run_http(host=args.host, port=args.port)
    else:
        run_stdio()


if __name__ == "__main__":
    main()
