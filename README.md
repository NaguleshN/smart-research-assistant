# Smart Research Assistant

A multi-agent research pipeline that takes a plain-English question, searches the web, extracts facts from sources, and returns a structured JSON report — all driven by Claude.

---

## What it does end to end

```
You type a question
        │
        ▼
┌─────────────────┐
│  Search Agent   │  Finds 5-10 relevant web sources for your query
└────────┬────────┘
         │  SearchResult[]
         ▼
┌─────────────────┐
│  Extract Agent  │  Fetches each source and pulls out key facts/claims
└────────┬────────┘
         │  ExtractedFact[]
         ▼
┌──────────────────┐
│ Summarise Agent  │  Synthesises everything into an executive summary
└────────┬─────────┘
         │
         ▼
  report.json  ←  structured output with sources, findings, token usage
```

Each agent runs its own conversation loop with Claude, calls tools through the local MCP server, and hands its output to the next stage via the orchestrator.

---

## Where Claude is used

### 1. Search Agent — `agents/search_agent.py`
Claude drives an agentic loop that calls the `web_search` MCP tool repeatedly until it has gathered enough sources (up to 5 iterations). The system prompt instructs Claude to return **only valid JSON** matching the `SearchResult` schema.

```
Claude (claude-opus-4-8)
  ├── tool call → web_search("your query")    [via MCP server]
  ├── tool call → cache_get / cache_set        [avoid re-fetching]
  └── final turn → JSON list of sources
```

### 2. Extract Agent — `agents/extract_agent.py`
Claude loops up to 8 iterations, calling `fetch_page` for each source URL. It reads the raw page text and extracts precise, falsifiable claims — with confidence scores and verbatim quotes where available. Output is **JSON only**, validated against `ExtractedFact`.

```
Claude (claude-opus-4-8)
  ├── tool call → fetch_page("https://source-a.com")
  ├── tool call → fetch_page("https://source-b.com")
  └── final turn → JSON list of extracted facts
```

### 3. Summarise Agent — `agents/summarise_agent.py`
Claude receives the full fact list and synthesises a 3–5 paragraph executive summary, selects the most important key findings, and flags limitations. No tool calls — pure synthesis. The large fact payload is marked with `cache_control: ephemeral` so repeated runs on the same facts hit Claude's **prompt cache** instead of re-processing.

```
Claude (claude-opus-4-8)
  └── final turn → JSON report (summary + key_findings + limitations)
```

### 4. MCP Server — `mcp_server/server.py`
A local [Model Context Protocol](https://modelcontextprotocol.io) server that exposes four tools to all agents:

| Tool | What it does |
|---|---|
| `web_search` | Queries DuckDuckGo and returns titles, URLs, snippets |
| `fetch_page` | Fetches a URL and returns its text content |
| `cache_get` | Reads a time-limited cache entry from disk |
| `cache_set` | Writes a cache entry (default TTL: 1 hour) |

Agents connect to this server via the `type: "mcp"` tool block in their `messages.create` call — the Anthropic SDK handles the MCP handshake.

### 5. Prompt Caching — `agents/summarise_agent.py`
Both system prompts and the large user-turn fact payload carry `"cache_control": {"type": "ephemeral"}`. On subsequent calls with the same content, Claude returns `cache_read_input_tokens` instead of billing full input tokens — visible in the final report's `cached_tokens` field.

---

## Output

`report.json` follows the `ResearchReport` Pydantic schema:

```json
{
  "query": "impact of LLMs on software development",
  "summary": "...",
  "key_findings": [
    {
      "claim": "...",
      "source_url": "https://...",
      "confidence": 0.87,
      "category": "finding",
      "quote": "..."
    }
  ],
  "sources": [...],
  "limitations": "...",
  "total_tokens_used": 12400,
  "cached_tokens": 4800,
  "agent_iterations": { "search": 2, "extract": 5, "summarise": 1 }
}
```

---

## Project structure

```
smart-research-assistant/
├── CLAUDE.md                    # Claude Code project instructions (root)
├── agents/
│   ├── CLAUDE.md                # Claude Code instructions scoped to agents
│   ├── search_agent.py          # Agentic loop: search
│   ├── extract_agent.py         # Agentic loop: extract
│   └── summarise_agent.py       # Agentic loop: summarise + caching
├── mcp_server/
│   └── server.py                # Local MCP server
├── pipeline/
│   └── orchestrator.py          # Wires agents together
├── prompts/
│   ├── search.py                # System + user prompts for search
│   ├── extract.py               # System + user prompts for extract
│   └── summarise.py             # System + user prompts for summarise
├── schemas/
│   └── report.py                # Pydantic models for all outputs
├── tests/
│   ├── test_agents.py           # Schema validation tests
│   └── test_pipeline.py         # Orchestrator tests (mocked Claude)
├── .github/workflows/ci.yml     # GitHub Actions: test + typecheck + lint
├── .claude/settings.json        # Claude Code permissions config
├── requirements.txt
└── main.py                      # CLI entry point
```

---

## Optimizations & Benefits

### Prompt caching — fewer tokens billed on repeated runs
System prompts for all three agents and the large facts payload in the summarise agent are marked `"cache_control": {"type": "ephemeral"}`. When you run the same query twice, or when the summarise agent loops, Claude returns `cache_read_input_tokens` instead of billing full input-token prices. The final `report.json` includes `cached_tokens` so you can see exactly how much was served from cache.

### MCP server shared across agents
A single local MCP server (`mcp_server/server.py`) handles all tool calls — `web_search`, `fetch_page`, `cache_get`, `cache_set`. Every agent connects to it over the same port, so there is no redundant process overhead and each agent's cache reads benefit from pages already fetched by earlier agents in the same pipeline run.

### Iteration caps prevent runaway spend
Each agent has a hard `MAX_ITERATIONS` guard (5 / 8 / 3 for search / extract / summarise). The pipeline never loops indefinitely on a bad model response; if an agent cannot finish within its budget it raises `AgentMaxIterationsError` rather than silently retrying forever.

### Structured output via Pydantic — fail-fast validation
All inter-agent data passes through Pydantic v2 models (`SearchResult`, `ExtractedFact`, `ResearchReport`). Invalid JSON from a model response raises a `ValidationError` immediately at the agent boundary, making bugs visible at the earliest possible point rather than propagating corrupt data through the pipeline.

### AWS Bedrock — compliance, cost control, and VPC isolation
The pipeline uses `AnthropicBedrock` instead of the direct Anthropic API. Benefits:
- **Data residency** — requests stay inside your AWS region; no data leaves your chosen geography.
- **IAM access control** — standard AWS IAM policies govern who can call the model, enabling fine-grained permissions and audit trails via CloudTrail.
- **VPC endpoints** — Bedrock can be accessed through a VPC endpoint so traffic never traverses the public internet.
- **Consolidated billing** — API usage rolls into your existing AWS bill alongside other infrastructure spend.
- **Throttle and quota management** — AWS Service Quotas let you cap concurrency and spend at the account level.

### Modular agent design — easy to swap backends
Each agent is a standalone Python module with a single `run()` function. Swapping the search backend (e.g., replacing DuckDuckGo with a licensed API), adding a new extraction strategy, or plugging in a different summarisation model requires editing one file without touching the rest of the pipeline.

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure AWS credentials (Bedrock access required)
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# 3. Start the MCP server (keep this running in a separate terminal)
python -m mcp_server.server

# 4. Run the pipeline
python main.py --query "impact of LLMs on software development" --output report.json

# 5. Run tests
pytest tests/ -v
```

---

## CI

GitHub Actions runs on every push and pull request to `main`:
- `mypy` strict type checking across all agent and pipeline modules
- `pytest` unit + integration tests (Anthropic client is mocked — no API key needed in CI)
- `ruff` lint check

A failing test or type error blocks the merge.
