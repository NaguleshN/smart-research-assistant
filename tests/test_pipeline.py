"""Integration-style tests for the orchestrator (mocked Anthropic client)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from schemas.report import ResearchReport


def _make_text_response(text: str, stop_reason: str = "end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = [block]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    response.usage.cache_read_input_tokens = 0
    return response


SEARCH_JSON = json.dumps({
    "results": [
        {
            "title": "Source A", "url": "https://a.com", "snippet": "snippet",
            "source": "a.com", "relevance_score": 0.9,
        }
    ]
})

EXTRACT_JSON = json.dumps({
    "facts": [
        {
            "claim": "A is true", "source_url": "https://a.com",
            "confidence": 0.8, "category": "finding", "quote": None,
        }
    ]
})

SUMMARISE_JSON = json.dumps({
    "summary": "A summary.",
    "key_findings": [
        {
            "claim": "A is true", "source_url": "https://a.com",
            "confidence": 0.8, "category": "finding", "quote": None,
        }
    ],
    "limitations": "Only one source.",
})


@patch("pipeline.orchestrator.anthropic.AnthropicBedrock")
def test_orchestrator_happy_path(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_text_response(SEARCH_JSON),
        _make_text_response(EXTRACT_JSON),
        _make_text_response(SUMMARISE_JSON),
    ]

    from pipeline.orchestrator import run
    report = run("test query")

    assert isinstance(report, ResearchReport)
    assert report.query == "test query"
    assert len(report.sources) == 1
    assert len(report.key_findings) == 1
    assert report.agent_iterations["search"] == 1
