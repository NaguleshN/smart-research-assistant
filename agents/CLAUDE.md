# Agents — Sub-agent Scope

Each agent in this directory runs its own `client.messages.create` loop with tool use.

## Responsibilities
| Agent | Input | Output | Max iterations |
|---|---|---|---|
| `search_agent` | query string | `SearchResult[]` JSON | 5 |
| `extract_agent` | `SearchResult[]` | `ExtractedFact[]` JSON | 8 |
| `summarise_agent` | `ExtractedFact[]` | `ResearchReport` JSON | 3 |

## Rules
- Never import from sibling agents — communicate only through the orchestrator
- All tool calls go through the MCP client, never raw `requests`
- If an agent exceeds its iteration cap, raise `AgentMaxIterationsError`
- Log every tool call result with `logger.debug` (structured JSON line)
