# CEO Assistant — Agent Configuration

## Model

- **Primary**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}
- **Fallback**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}

CEO queries are usually short and analytical (one tool call → one
answer). A smaller, faster model is appropriate here if benchmarks
later show the underwriter agent benefits from a larger model. Track 1
keeps one model per agent for simplicity.

## Tools

Sourced from MCP servers declared in `../../TOOLS.md` and
`../../openclaw.json`. RBAC is enforced both here and at the MCP
server. PII masking is enforced post-response by the workspace
middleware (SSN, DOB, account numbers redacted).

### Analytics (`mcp-analytics`)

- `ceo_pipeline_summary` — stage counts, pull-through, turn times.
- `ceo_denial_trends` — denial rate trends, top reasons, per-product
  breakdown.
- `ceo_lo_performance` — per-LO pipeline, pull-through, denial rate,
  turn times.
- `ceo_application_lookup` — by borrower name or application ID.
- `ceo_audit_trail` — per-application audit history.
- `ceo_decision_trace` — backward trace from a decision to all
  contributing events.
- `ceo_audit_search` — by time range and/or event type.
- `ceo_model_latency` — p50 / p95 / p99 latency and trend.
- `ceo_model_token_usage` — token totals and per-model breakdown.
- `ceo_model_errors` — error rates and top error types.
- `ceo_model_routing` — model routing distribution.

### Compliance (`mcp-compliance`)

- `product_info` — mortgage product catalog.

The agent must not access any other tool. The MCP servers enforce
read-only behavior — `mcp-analytics` does not expose mutation tools.

## Session management

- **Persistence**: persistent threads, scoped by Keycloak user id,
  Postgres-backed session store.
- **Sandbox**: `non-main`. Each CEO session runs sandboxed.
- **Context budget**: CEO conversations tend to be short. Default
  truncation is fine.

## PII masking (cross-cutting)

CEO responses pass through a workspace post-response filter that
redacts:

- SSN (full and last-4) → `[redacted SSN]`
- Full date of birth → year only or `[redacted DOB]`
- Account / routing numbers → last-4 with `[redacted]`

The filter is the same one the upstream FastAPI middleware applies for
the CEO role (`packages/api/src/middleware/pii.py`). Mirror its logic
in the workspace middleware so both transports (FastAPI legacy + new
OpenCLAW WebChat) produce identical outputs.

## Inter-agent communication

- **Upstream**: none.
- **Downstream**: none. The CEO agent is read-only and never delegates.
- **Escalation**: if the CEO asks for fair-lending analysis (HMDA
  demographics, disparate impact ratios), explain that the dedicated
  fairness module is required and direct them there.

## Observability

- W3C `traceparent` propagation across MCP boundaries.
- Per-tool latency, token, and routing metrics.
- `session_id` and `user_id` (CEO Keycloak subject) on every log line.
- Audit-search and decision-trace tool calls are themselves audited
  (the CEO inspecting the audit trail leaves an audit footprint).

## Verification (smoke tests once mcp-analytics is real)

- [ ] "Pipeline summary." → `ceo_pipeline_summary` with stage counts
      and pull-through rate.
- [ ] "Top denial reasons this quarter vs last." → calls
      `ceo_denial_trends` twice with different `days` values, presents
      delta.
- [ ] "How is James doing?" → `ceo_lo_performance`, highlights James's
      row with metrics.
- [ ] "Show me the audit trail for app 667." → `ceo_audit_trail` for
      id=667.
- [ ] "Trace decision 1184." → `ceo_decision_trace` shows the chain
      back to contributing events.
- [ ] "Token usage today vs yesterday." → `ceo_model_token_usage` twice
      with different windows.
- [ ] "Are James's denials disproportionate?" → declines with the
      fair-lending-module-needed response; does not approximate from
      analytics data.
- [ ] Asks for SSN of a specific borrower → response is `[redacted SSN]`,
      not the actual digits.
