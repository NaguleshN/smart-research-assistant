from __future__ import annotations


from pydantic import BaseModel, field_validator


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float

    @field_validator("relevance_score")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ExtractedFact(BaseModel):
    claim: str
    source_url: str
    confidence: float
    category: str  # e.g. "statistic", "definition", "finding"
    quote: str | None = None


class ResearchReport(BaseModel):
    query: str
    summary: str
    key_findings: list[ExtractedFact]
    sources: list[SearchResult]
    limitations: str
    total_tokens_used: int
    cached_tokens: int
    agent_iterations: dict[str, int]  # agent_name → iteration count
