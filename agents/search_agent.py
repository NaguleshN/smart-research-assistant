"""Phase D1 — agentic loop with tool use (search sub-agent)."""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AnthropicBedrock

from prompts import search as search_prompts
from schemas.report import SearchResult

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5
MODEL = "anthropic.claude-opus-4-8"

MCP_TOOLS: list[dict] = [
    {
        "type": "mcp",
        "server_label": "research",
        "server_url": "http://localhost:8765/mcp",
        "tool_names": ["web_search", "cache_get", "cache_set"],
    }
]


class AgentMaxIterationsError(RuntimeError):
    pass


def run(query: str, client: AnthropicBedrock) -> tuple[list[SearchResult], int]:
    """Run the search agentic loop. Returns (results, iterations_used)."""
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": search_prompts.user_prompt(query)}
    ]
    total_tokens = 0

    for iteration in range(1, MAX_ITERATIONS + 1):
        logger.debug("search_agent iteration %d", iteration)

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": search_prompts.SYSTEM,
                    # D5: mark system prompt as cacheable
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=MCP_TOOLS,  # type: ignore[arg-type]
            messages=messages,
        )

        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        logger.debug(
            "search_agent usage: in=%d out=%d cached=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            getattr(response.usage, "cache_read_input_tokens", 0),
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract JSON from final text block
            for block in response.content:
                if block.type == "text":
                    data = json.loads(block.text)
                    results = [SearchResult(**r) for r in data.get("results", [])]
                    logger.info("search_agent found %d results", len(results))
                    return results, iteration

        # Handle tool use — append tool results and continue loop
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                # MCP handles execution; we just append a placeholder result
                # so the loop can continue (real MCP SDK handles this automatically)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"status": "tool_executed"}),
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    raise AgentMaxIterationsError(f"search_agent exceeded {MAX_ITERATIONS} iterations")
