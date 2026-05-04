# Borrower Assistant — Agent Configuration

## Model

- **Primary**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}
- **Fallback**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}

The provider `openai-compatible` is defined in `../../openclaw.json` and
points at a local CPU-served OpenAI-compatible endpoint (vLLM-CPU,
llama.cpp, OpenVINO Model Server, or LM Studio for laptop dev).

One model per agent on Track 1; the upstream LangGraph "fast vs capable"
split can be reintroduced as a workspace skill if booth benchmarks show
it materially helps perf or cost.

## Tools

Sourced from MCP servers declared in `../../TOOLS.md` and
`../../openclaw.json`. RBAC is enforced both at the agent layer (this
list) and at the MCP server layer (defense in depth).

### Pipeline (`mcp-pipeline`)

- `list_my_applications` — list the borrower's mortgage applications.
- `start_application` — start a new application or return an existing one.
- `update_application_data` — validate and store field values.
- `get_application_summary` — show collected data and progress.
- `application_status` — overall status summary including stage,
  documents, and pending actions.
- `document_completeness` — uploaded vs. needed documents.
- `document_processing_status` — processing state of uploaded documents.
- `rate_lock_status` — locked rate, expiration, days remaining.

### Compliance (`mcp-compliance`)

- `product_info` — mortgage product catalog.
- `affordability_calc` — affordability estimate from income, debts, down
  payment.
- `regulatory_deadlines` — regulatory deadline lookup with disclaimer.
- `acknowledge_disclosure` — record borrower acknowledgment in the audit
  trail.
- `disclosure_status` — pending vs. acknowledged disclosures.

### Decision (`mcp-decision`)

- `list_conditions` — open underwriting conditions for the borrower's
  application.
- `respond_to_condition_tool` — record a borrower's text response to a
  condition.
- `check_condition_satisfaction` — review whether a condition is satisfied
  by linked documents and extraction results.

The agent must not access any other tool. The MCP servers enforce that
authenticated borrowers see only their own applications and documents
(`scope: own_data_only`).

## Session management

- **Persistence**: persistent threads, scoped by `keycloak_user_id` (or
  the dev-mode user id when `AUTH_DISABLED=true`). Conversations resume
  across reconnects. Backed by the same Postgres-backed checkpointer
  pattern used by the upstream LangGraph implementation; the OpenCLAW
  gateway must be configured to use a Postgres session store rather than
  per-pod local files (see `planning/10-production-readiness.md` § B1).
- **Sandbox**: `non-main`. Each authenticated borrower session runs in
  its own sandbox to keep state isolation crisp at booth-scale
  concurrency. Pooled pre-warmed runner pods on K8s; Docker-per-session
  on single-box.
- **Context budget**: long borrower conversations (50+ turns of intake +
  document Q&A) must stay coherent. If OpenCLAW's native session history
  drops context, fall back to passing condensed history per turn from
  Postgres.

## Inter-agent communication

- **Upstream**: none. The borrower talks directly to this agent.
- **Downstream**: none. This agent does not delegate to other personas.
  Underwriter / Loan Officer agents work the same data through their
  own agents and tools.
- **Escalation**: if a borrower asks something out of scope ("can you
  approve my application?"), explain that decisions are made by the
  underwriter and offer to record their request as a note instead.

## Observability

- W3C `traceparent` propagates from the gateway through MCP tool calls.
- Per-tool latency, tokens, and `agent_routing_total` metrics are
  emitted to the workspace Prometheus endpoint, keeping continuity with
  the upstream metrics schema.
- `session_id` and `user_id` (Keycloak subject) are included on every
  log line. PII (SSN, full DOB, account numbers) is redacted from logs
  by the workspace logging middleware.

## Verification (smoke tests once mcp-pipeline / mcp-decision are real)

- [ ] "Show me my application." → `list_my_applications` then
      `application_status` without asking the borrower for an ID.
- [ ] "I want to apply." → `start_application`; if active app exists,
      offer to continue.
- [ ] "I'm John Smith, $9,000/mo income, $400 in debts." → batched
      `update_application_data` with `first_name`, `last_name`,
      `gross_monthly_income`, `monthly_debts`.
- [ ] "What did I provide for SSN?" → refuses to echo, says it's stored
      securely.
- [ ] "I have reviewed and acknowledge the Loan Estimate." → calls
      `acknowledge_disclosure` once and stops.
- [ ] Condition response with vague text → asks one clarifying question
      rather than blindly recording.
- [ ] Tries to access another borrower's application via the prompt →
      MCP scope enforcement returns "not found".
