# Public Assistant — Agent Configuration

## Model

- **Primary**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}
- **Fallback**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}

The provider `openai-compatible` is defined in `../../openclaw.json` and
points at a local CPU-served OpenAI-compatible endpoint
(vLLM-CPU, llama.cpp server, OpenVINO Model Server, or LM Studio for
laptop dev).

This agent does not use the upstream LangGraph "fast vs capable" model
routing. One model per agent is the deliberate Track 1 simplification; the
classifier-driven split can be reintroduced as a workspace skill if booth
benchmarks show it materially helps perf or cost.

## Tools

Sourced from MCP servers declared in `../../TOOLS.md` and `../../openclaw.json`.
This agent has access to the public-tier tools only.

- `product_info` (server: `compliance`)
  - Retrieve mortgage product catalog.
  - Required for any question about products, rates, loan types, or what we
    offer.
- `affordability_calc` (server: `compliance`)
  - Compute an affordability estimate from income, monthly debts, and down
    payment.
  - Required inputs: `gross_annual_income`, `monthly_debts`, `down_payment`.
  - Optional inputs: `interest_rate`, `loan_term_years`.
- `current_date` (server: `compliance`)
  - Today's date in ISO format. Use when reasoning about rate freshness,
    closing dates, or any time-sensitive guidance.

The agent must not access any other tool. RBAC enforcement is duplicated at
the MCP server side (defense in depth).

## Session management

- **Persistence**: ephemeral. Public sessions do not persist conversation
  history across reconnects. Each WebSocket connection starts a fresh
  thread. This matches the upstream behavior of the FastAPI `/chat` route.
- **Sandbox**: off. Public sessions run on the gateway main loop to keep
  cold-start latency minimal for first-impression demo moments. The agent
  has no tool access beyond the two listed tools, so the blast radius of
  no-sandbox is limited.
- **Context budget**: keep conversation history within a single LLM context
  window. Truncate oldest turns first. This is acceptable for prospects
  who typically converse for fewer than 20 turns.

## Inter-agent communication

- **Upstream**: none. The Public Assistant is the entry point for
  unauthenticated traffic; there is no orchestrator above it in the booth
  demo.
- **Downstream**: none. The Public Assistant does not delegate to other
  agents. If a user signs up and authenticates mid-conversation (a flow
  not in scope for the booth demo), the gateway re-routes new turns to
  the Borrower Assistant; it does not chain agents within a turn.
- **Escalation**: if the user asks for something requiring authentication
  (application status, document upload, credit-pull), the agent declines
  with a guided next step ("To check on a specific application, you'll
  need to sign in") rather than escalating.

## Observability

- Trace context propagates from the gateway through MCP tool calls
  (W3C `traceparent` headers).
- Per-tool latency and token-count metrics are emitted to the workspace
  Prometheus endpoint via the gateway, matching the upstream metrics
  schema (`agent_routing_total`, `llm_tokens_total`, `tool_calls_total`).
- Session-id is included in every log line for correlation with the
  Fleet View dashboard.

## Verification (Track 1 exit criteria)

- [ ] Agent responds to "What products do you offer?" by calling
      `product_info` and rendering the catalog in plain text.
- [ ] Agent prompts for missing inputs before calling `affordability_calc`
      (does not invent placeholder values).
- [ ] Agent declines customer-data questions with the exact rule-defined
      response text.
- [ ] Agent ignores prompt-injection attempts that ask it to bypass tool use.
- [ ] All tool calls show up in the OTel trace with role-tagged metadata.
