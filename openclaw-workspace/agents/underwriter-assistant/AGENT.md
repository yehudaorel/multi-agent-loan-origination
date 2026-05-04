# Underwriter Assistant — Agent Configuration

## Model

- **Primary**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}
- **Fallback**: openai-compatible/${LLM_MODEL:-qwen3-30b-a3b}

The underwriter is the most tool-heavy persona; the LLM has to chain ~5
tool calls in a row for risk assessment without commentary between
steps. Pick a model that handles tool use cleanly. If a smaller model
falters on the multi-step risk-assessment chain, escalate to a larger
one — this is the agent most likely to need a "fast vs capable" split
reintroduced as a workspace skill in a future iteration.

## Tools

This agent has the broadest tool set in the workspace (~25 tools across
four MCP servers). RBAC is enforced both here and at the MCP server.

### Risk (`mcp-risk`)

Pure-computation risk math. Stateless; safe to fan out across replicas.

- `calculate_dti` — DTI ratio and risk rating.
- `calculate_ltv` — LTV ratio and risk rating.
- `evaluate_credit_risk` — credit-score-based risk rating.
- `assess_income_stability` — employment-status-based stability rating.
- `assess_asset_sufficiency` — assets vs loan-amount rating.
- `generate_risk_recommendation` — rule-based recommendation from all
  five risk inputs plus optional ML signal.
- `uw_predict_loan_approval` — optional predictive ML model. Returns
  "not configured" when `PREDICTIVE_MODEL_MCP_URL` is empty (default).

### Pipeline (`mcp-pipeline`)

- `uw_queue_view` — UW queue sorted by urgency.
- `uw_application_detail` — full application detail.

### Compliance (`mcp-compliance`)

- `current_date` — today's date for due-date math.
- `product_info` — mortgage product catalog.
- `affordability_calc` — affordability estimate.
- `kb_search` — semantic search over federal/agency/internal compliance
  KB tiers, with conflict detection.
- `compliance_check` — ECOA, ATR/QM, TRID structured checks.
- `uw_generate_le` — generate a simulated Loan Estimate.
- `uw_generate_cd` — generate a simulated Closing Disclosure (requires
  all conditions cleared/waived).
- `uw_draft_adverse_action` — draft an ECOA/FCRA adverse action notice.

### Decision (`mcp-decision`)

- `uw_save_risk_assessment` — persist a completed risk assessment with
  audit trail.
- `uw_preliminary_recommendation` — rule-based preliminary
  recommendation (Approve / Approve with Conditions / Suspend / Deny).
- `uw_issue_condition` — create a new underwriting condition.
- `uw_review_condition` — RESPONDED → UNDER_REVIEW.
- `uw_clear_condition` — clear after reviewing borrower's response.
- `uw_waive_condition` — waive (PRIOR_TO_CLOSING/FUNDING only,
  rationale required).
- `uw_return_condition` — return to borrower with a note.
- `uw_condition_summary` — counts by status for an application.
- `uw_render_decision` — two-phase decision tool: propose, then confirm.

The agent must not access any other tool. The MCP servers enforce that
the underwriter can act on any application in the underwriting pipeline
(`scope: full_pipeline`).

## Session management

- **Persistence**: persistent threads, scoped by Keycloak user id,
  Postgres-backed session store.
- **Sandbox**: `non-main`. Each underwriter session runs sandboxed.
- **Context budget**: an underwriter walking through a single
  application from queue to decision can fill a context window. Pin
  the application's `application_id` in the OpenCLAW session metadata
  so it survives history truncation. If history truncation drops
  context, re-fetch via `uw_application_detail`.

## Inter-agent communication

- **Upstream**: none. The underwriter talks directly to this agent.
- **Downstream**: none. State changes that affect the borrower's view
  (condition issued, decision rendered) flow through MCP-decision
  state changes; the borrower's agent picks them up on the next
  `list_conditions` / `application_status` call.
- **Escalation**: only the underwriter (a human) escalates between
  decisions. The agent does not auto-escalate to a senior underwriter
  or compliance officer — those are organizational decisions, not
  workflow rules.

## Observability

- W3C `traceparent` propagation across all MCP boundaries.
- Multi-step flows (risk assessment, decision rendering) emit a single
  parent span per workflow with child spans per tool call. Useful for
  debugging incomplete chains.
- Per-tool latency, token, and routing metrics.
- `session_id`, `user_id` (UW Keycloak subject), and `application_id`
  on every log line. PII never logged.
- Audit chain entries on every state change (condition lifecycle,
  decision rendered, LE/CD generated, adverse action drafted).

## Verification (smoke tests once mcp-decision and full mcp-compliance
are real)

- [ ] "Show my queue." → `uw_queue_view` ordered by urgency.
- [ ] "Assess risk on app 667." → executes all five risk tools, then
      ML predictor, then `generate_risk_recommendation`, then
      `uw_save_risk_assessment` — silently — before responding.
- [ ] "Issue a condition on app 667." → presents the eight-category
      list as a numbered list, waits for the underwriter's pick, then
      narrows to that category's options. Does not skip steps.
- [ ] "Approve app 667." → blocks until `compliance_check` and
      `uw_preliminary_recommendation` have run; calls
      `uw_render_decision` with `confirmed=false` first; only sets
      `confirmed=true` after explicit "yes".
- [ ] "Approve app 667." after `compliance_check` returned a FAIL →
      refuses, explains which check failed.
- [ ] "What's the QM safe-harbor DTI cap?" → `kb_search`, not memory,
      with tier and section citation.
- [ ] "Generate the closing disclosure for app 667." while conditions
      remain → tool refuses, agent explains.
