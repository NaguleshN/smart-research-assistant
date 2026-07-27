"""Phase D1 — agentic loop, no tools (summarise sub-agent).

D5 focus: long facts list is passed as a user message with cache_control so
repeated summarise calls on the same fact set hit the prompt cache.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AnthropicBedrock

from prompts import summarise as summarise_prompts
from schemas.report import ExtractedFact, ResearchReport, SearchResult

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
MODEL = "anthropic.claude-opus-4-8"


class AgentMaxIterationsError(RuntimeError):
    pass


def run(
    query: str,
    facts: list[ExtractedFact],
    sources: list[SearchResult],
    client: AnthropicBedrock,
    token_totals: dict[str, int],
    agent_iterations: dict[str, int],
) -> ResearchReport:
    """Synthesise a ResearchReport from facts. Returns the final report."""
    facts_json = json.dumps([f.model_dump() for f in facts], indent=2)

    # D5: mark large facts payload as cacheable in the user turn
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": summarise_prompts.user_prompt(query, facts_json),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        logger.debug("summarise_agent iteration %d", iteration)

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": summarise_prompts.SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )

        cached = getattr(response.usage, "cache_read_input_tokens", 0)
        logger.info(
            "summarise_agent usage: in=%d out=%d cached=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            cached,
        )
        token_totals["total"] += response.usage.input_tokens + response.usage.output_tokens
        token_totals["cached"] += cached

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    data = json.loads(block.text)
                    key_facts = [ExtractedFact(**f) for f in data.get("key_findings", [])]
                    agent_iterations["summarise"] = iteration
                    return ResearchReport(
                        query=query,
                        summary=data["summary"],
                        key_findings=key_facts,
                        sources=sources,
                        limitations=data.get("limitations", ""),
                        total_tokens_used=token_totals["total"],
                        cached_tokens=token_totals["cached"],
                        agent_iterations=agent_iterations,
                    )

    raise AgentMaxIterationsError(f"summarise_agent exceeded {MAX_ITERATIONS} iterations")
