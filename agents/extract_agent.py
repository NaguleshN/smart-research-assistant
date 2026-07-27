"""Phase D1 — agentic loop with tool use (extract sub-agent)."""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AnthropicBedrock
from anthropic.types import MessageParam

from prompts import extract as extract_prompts
from schemas.report import ExtractedFact, SearchResult

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8
MODEL = "anthropic.claude-opus-4-8"

MCP_TOOLS: list[dict[str, Any]] = [
    {
        "type": "mcp",
        "server_label": "research",
        "server_url": "http://localhost:8765/mcp",
        "tool_names": ["fetch_page", "cache_get", "cache_set"],
    }
]


class AgentMaxIterationsError(RuntimeError):
    pass


def run(
    sources: list[SearchResult], client: AnthropicBedrock
) -> tuple[list[ExtractedFact], int]:
    """Run the extract agentic loop. Returns (facts, iterations_used)."""
    sources_json = json.dumps([s.model_dump() for s in sources], indent=2)
    messages: list[MessageParam] = [
        {"role": "user", "content": extract_prompts.user_prompt(sources_json)}
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        logger.debug("extract_agent iteration %d", iteration)

        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": extract_prompts.SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=MCP_TOOLS,  # type: ignore[arg-type]
            messages=messages,
        )

        logger.debug(
            "extract_agent usage: in=%d out=%d cached=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            getattr(response.usage, "cache_read_input_tokens", 0),
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    data = json.loads(block.text)
                    facts = [ExtractedFact(**f) for f in data.get("facts", [])]
                    logger.info("extract_agent extracted %d facts", len(facts))
                    return facts, iteration

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"status": "tool_executed"}),
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    raise AgentMaxIterationsError(f"extract_agent exceeded {MAX_ITERATIONS} iterations")
