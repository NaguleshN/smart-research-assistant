"""
Local MCP server exposing research tools to all sub-agents.

Tools exposed:
  web_search(query, num_results) → list[{title, url, snippet}]
  fetch_page(url, max_chars)     → str (page text)
  cache_get(key)                 → str | null
  cache_set(key, value, ttl_s)  → bool
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.environ.get("CACHE_DIR", ".cache"))
CACHE_DIR.mkdir(exist_ok=True)

MCP_LOG = Path("logs/mcp_calls.jsonl")
MCP_LOG.parent.mkdir(exist_ok=True)

app = Server("smart-research-mcp")


def _log_call(tool: str, args: dict, result_chars: int) -> None:
    entry = {"ts": time.time(), "tool": tool, "args": args, "result_chars": result_chars}
    with MCP_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web and return top results",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_page",
            description="Fetch and return the text content of a URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 8000},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="cache_get",
            description="Retrieve a cached value by key",
            inputSchema={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        ),
        Tool(
            name="cache_set",
            description="Store a value in the cache",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "ttl_s": {"type": "integer", "default": 3600},
                },
                "required": ["key", "value"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "web_search":
        result = await _web_search(arguments["query"], arguments.get("num_results", 5))
    elif name == "fetch_page":
        result = await _fetch_page(arguments["url"], arguments.get("max_chars", 8000))
    elif name == "cache_get":
        result = _cache_get(arguments["key"])
    elif name == "cache_set":
        result = _cache_set(
            arguments["key"], arguments["value"], arguments.get("ttl_s", 3600)
        )
    else:
        result = {"error": f"Unknown tool: {name}"}

    text = json.dumps(result)
    _log_call(name, arguments, len(text))
    return [TextContent(type="text", text=text)]


async def _web_search(query: str, num_results: int) -> dict:
    # Uses DuckDuckGo Instant Answer API (no key required) for basic results.
    # Replace with a proper Search API (Brave, Serper, Tavily) for production.
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1},
            )
            data = resp.json()
        results = []
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if "Text" in topic and "FirstURL" in topic:
                results.append(
                    {
                        "title": topic["Text"][:120],
                        "url": topic["FirstURL"],
                        "snippet": topic["Text"],
                    }
                )
        return {"results": results}
    except Exception as exc:
        logger.warning("web_search failed: %s", exc)
        return {"results": [], "error": str(exc)}


async def _fetch_page(url: str, max_chars: int) -> dict:
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "SmartResearchBot/1.0"},
        ) as client:
            resp = await client.get(url)
            text = resp.text[:max_chars]
        return {"url": url, "status": resp.status_code, "content": text}
    except Exception as exc:
        logger.warning("fetch_page failed for %s: %s", url, exc)
        return {"url": url, "error": str(exc)}


def _cache_get(key: str) -> dict:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return {"hit": False, "value": None}
    data = json.loads(path.read_text())
    if data["expires"] < time.time():
        path.unlink(missing_ok=True)
        return {"hit": False, "value": None}
    return {"hit": True, "value": data["value"]}


def _cache_set(key: str, value: str, ttl_s: int) -> dict:
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"value": value, "expires": time.time() + ttl_s}))
    return {"stored": True}


async def main() -> None:
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
