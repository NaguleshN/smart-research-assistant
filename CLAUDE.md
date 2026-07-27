# Smart Research Assistant

## Project Overview
A multi-agent research pipeline built on the Anthropic SDK. Three sub-agents (search, extract, summarise) cooperate through a local MCP server to produce structured JSON research reports.

## Architecture
```
main.py → orchestrator → search_agent → extract_agent → summarise_agent
                    ↕              ↕               ↕               ↕
               mcp_server  (tool calls via MCP across all agents)
```

## Key Files
- `agents/` — three autonomous sub-agents, each with its own agentic loop
- `mcp_server/server.py` — local MCP server exposing research tools
- `pipeline/orchestrator.py` — wires agents together, manages context/cache
- `prompts/` — all system and user prompts (structured JSON output required)
- `schemas/report.py` — Pydantic models for the final report shape
- `tests/` — pytest suite; CI blocks on red tests

## Commands
```bash
# Install
pip install -r requirements.txt

# Run the pipeline
python main.py --query "your research question" --output report.json

# Start MCP server standalone (for development)
python -m mcp_server.server

# Run tests
pytest tests/ -v

# Type check
mypy agents/ pipeline/ --strict
```

## Environment Variables
```
AWS_ACCESS_KEY_ID=        # required — Bedrock IAM credentials
AWS_SECRET_ACCESS_KEY=    # required
AWS_DEFAULT_REGION=       # required (e.g. us-east-1)
MCP_SERVER_PORT=8765      # default
CACHE_DIR=.cache          # prompt cache storage
```

## Sub-agent CLAUDE.md files
Each sub-agent directory has its own CLAUDE.md scoped to that agent's responsibilities. See:
- `agents/CLAUDE.md`

## Coding Standards
- All agent outputs must conform to the Pydantic schemas in `schemas/`
- Prompts must request JSON and include `response_format` instructions
- Every agentic loop must implement a max-iterations guard
- MCP tool calls must be logged to `logs/mcp_calls.jsonl`
