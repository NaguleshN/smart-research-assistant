"""
Phase D1 (agentic loop) + D5 (caching/context management).

Wires the three sub-agents together and tracks token usage across the pipeline.
"""
from __future__ import annotations

import logging

import anthropic

from agents import extract_agent, search_agent, summarise_agent
from schemas.report import ResearchReport

logger = logging.getLogger(__name__)


def run(query: str) -> ResearchReport:
    client = anthropic.AnthropicBedrock()

    token_totals = {"total": 0, "cached": 0}
    agent_iterations: dict[str, int] = {}

    # Phase 1 — Search
    logger.info("==> search_agent starting")
    sources, search_iters = search_agent.run(query, client)
    agent_iterations["search"] = search_iters
    logger.info("search_agent done: %d sources, %d iterations", len(sources), search_iters)

    # Phase 2 — Extract
    logger.info("==> extract_agent starting")
    facts, extract_iters = extract_agent.run(sources, client)
    agent_iterations["extract"] = extract_iters
    logger.info("extract_agent done: %d facts, %d iterations", len(facts), extract_iters)

    # Phase 3 — Summarise
    logger.info("==> summarise_agent starting")
    report = summarise_agent.run(
        query, facts, sources, client, token_totals, agent_iterations
    )
    logger.info(
        "summarise_agent done. total_tokens=%d cached=%d",
        report.total_tokens_used,
        report.cached_tokens,
    )

    return report
