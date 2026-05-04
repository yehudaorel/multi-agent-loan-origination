# Loan Officer Assistant — Agent Configuration

## Model

- **Primary**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}
- **Fallback**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}

Same provider config as the other personas; see
`agents/public-assistant/AGENT.md` for the rationale on a single model
per agent at Track 1.

## Tools

Sourced from MCP servers declared in `../../TOOLS.md` and
`../../openclaw.json`. RBAC is enforced both here and at the MCP server.

### Pipeline (`mcp-pipeline`)

- `lo_pipeline_summary` — applications across pipeline grouped by stage.
- `lo_application_detail` — full picture for one application.
- `lo_document_review` — document list with status and quality flags.
- `lo_document_quality` — detailed quality info for a single document.
- `lo_completeness_check` — document completeness for one application.
- `lo_mark_resubmission` — flag a document for resubmission with reason.
- `lo_underwriting_readiness` — readiness gate for UW submission.
- `lo_submit_to_underwriting` — APPLICATION → PROCESSING → UNDERWRITING.
- `lo_draft_communication` — gather full context for a borrower draft.
- `lo_send_communication` — record a sent communication (audit only at
  MVP; no real email send).

### Compliance (`mcp-compliance`)

- `product_info` — product catalog lookup.
- `affordability_calc` — affordability estimate.
- `kb_search` — semantic search across federal / agency / internal
  compliance KB tiers, with conflict detection.

The agent must not access any other tool. MCP servers enforce that the
LO can only see applications assigned to them
(`scope: assigned_applications`).

## Session management

- **Persistence**: persistent threads, scoped by Keycloak user id.
  Conversations resume across reconnects through a Postgres-backed
  session store.
- **Sandbox**: `non-main`. Each LO session runs sandboxed.
- **Context budget**: LOs may keep a long session open while reviewing a
  pipeline. Truncation strategy: drop oldest non-tool turns first; keep
  the most recent application context fresh.

## Inter-agent communication

- **Upstream**: none. The LO talks directly to this agent.
- **Downstream**: none. This agent does not delegate. State changes that
  cross persona boundaries (submit to UW) go through the MCP-pipeline
  state machine, not through agent-to-agent calls.
- **Escalation**: if the LO asks for an underwriter-only action
  (issuing a condition, rendering a decision), explain that the action
  is performed in the underwriter view, not the loan officer view.

## Observability

- W3C `traceparent` propagation across MCP boundaries.
- Per-tool latency, token, and routing metrics emitted to the workspace
  Prometheus endpoint.
- `session_id` and `user_id` (LO Keycloak subject) on every log line.
- Audit chain entries written by MCP servers on every state change
  (resubmission flag, submission to UW, communication sent).

## Verification (smoke tests once mcp-pipeline is real)

- [ ] "Summarize my pipeline." → `lo_pipeline_summary`, no app ID asked.
- [ ] "Review app 667." → `lo_application_detail` with id=667.
- [ ] "What's the document quality on app 92?" → `lo_document_review`
      then `lo_document_quality` if drilled into.
- [ ] "Submit app 667 to underwriting." → `lo_underwriting_readiness`
      first; if blockers, explain; if clear, ask for confirmation;
      `lo_submit_to_underwriting` only after explicit "yes".
- [ ] "Draft a resubmission notice for the W-2 on app 667." →
      `lo_draft_communication`, present draft, iterate, send only on
      explicit confirmation.
- [ ] "What's the QM safe-harbor DTI cap?" → `kb_search` (not memory),
      cite tier and section.
- [ ] Asks about an unassigned application → "not found" handled
      gracefully.
