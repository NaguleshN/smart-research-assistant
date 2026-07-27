"""Unit tests for agent output parsing and schema validation."""
from __future__ import annotations

import json

from schemas.report import ExtractedFact, ResearchReport, SearchResult


def test_search_result_relevance_clamp():
    r = SearchResult(
        title="t", url="https://example.com", snippet="s", source="example.com",
        relevance_score=1.5,
    )
    assert r.relevance_score == 1.0


def test_search_result_low_clamp():
    r = SearchResult(
        title="t", url="https://example.com", snippet="s", source="example.com",
        relevance_score=-0.3,
    )
    assert r.relevance_score == 0.0


def test_extracted_fact_optional_quote():
    f = ExtractedFact(
        claim="The sky is blue",
        source_url="https://example.com",
        confidence=0.9,
        category="finding",
    )
    assert f.quote is None


def test_research_report_round_trip():
    sources = [
        SearchResult(
            title="T", url="https://x.com", snippet="s", source="x.com",
            relevance_score=0.8,
        )
    ]
    facts = [
        ExtractedFact(
            claim="Claim A", source_url="https://x.com", confidence=0.85,
            category="statistic", quote="raw quote",
        )
    ]
    report = ResearchReport(
        query="test query",
        summary="summary text",
        key_findings=facts,
        sources=sources,
        limitations="narrow sources",
        total_tokens_used=1000,
        cached_tokens=400,
        agent_iterations={"search": 2, "extract": 4, "summarise": 1},
    )
    data = json.loads(report.model_dump_json())
    assert data["query"] == "test query"
    assert data["cached_tokens"] == 400
    assert len(data["key_findings"]) == 1


def test_category_field_preserved():
    f = ExtractedFact(
        claim="c", source_url="https://a.com", confidence=0.5, category="definition"
    )
    assert f.category == "definition"
