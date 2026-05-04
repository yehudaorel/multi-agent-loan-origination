# TOOLS.md — Workspace Tool Registry

Tool inventory available to agents in this workspace. Tool
*implementations* live in five Python MCP servers (sibling modules
under `packages/api/src/mcp_*.py`). This file is the workspace-level
contract that agents reference from their `AGENT.md` files.

## MCP servers (transport: streamable HTTP)

| Server | Module | Status | Endpoint (single-box) | Owns |
|---|---|---|---|---|
| `mcp-risk` | `src.mcp_server` | implemented (upstream) | `http://mcp-risk-server:8081/mcp` | DTI, LTV, credit, income/asset stability, recommendation, optional ML predictor |
| `mcp-compliance` | `src.mcp_compliance` | partial: public-tier implemented; auth-tier stubbed | `http://mcp-compliance:8082/mcp` | product info, affordability, current date, KB search, regulatory deadlines, compliance check, disclosures, LE/CD, adverse action |
| `mcp-pipeline` | `src.mcp_pipeline` | skeleton (Track 1) | `http://mcp-pipeline:8083/mcp` | application state, intake, documents, queues, rate lock, LO workflow |
| `mcp-decision` | `src.mcp_decision` | skeleton (Track 1) | `http://mcp-decision:8084/mcp` | conditions lifecycle, risk-assessment persistence, two-phase decision rendering |
| `mcp-analytics` | `src.mcp_analytics` | skeleton (Track 1) | `http://mcp-analytics:8085/mcp` | read-only CEO analytics, audit search, model monitoring |

Endpoints are overridable per environment via env vars
(`MCP_*_URL`). The OpenCLAW gateway resolves these from
`openclaw.json`. RBAC enforcement is duplicated at the MCP server side
as defense in depth.

**Stub responses.** Every skeleton tool returns a structured payload of
the form
`{"_stub": true, "tool": "...", "see": "<source path>", "echo": {...}, "next": "..."}`.
The agent layer will surface these gracefully ("That feature isn't
fully wired up yet — here's what's missing"). Production verification
(once Track 2 lands) requires that no `_stub: true` responses appear in
the booth-demo flow.

## Tool catalog

Each entry: tool name, owning MCP server, role ACL (which agents may
call), purpose. Roles map to the persona of the calling agent.

### Public-tier tools (no auth required, public_only data scope)

| Tool | Server | Roles | Purpose |
|---|---|---|---|
| `product_info` | `mcp-compliance` | prospect, borrower, loan_officer, underwriter, ceo, admin | Mortgage product catalog |
| `affordability_calc` | `mcp-compliance` | prospect, borrower, loan_officer, underwriter, ceo, admin | Estimate affordability from income, debts, down payment |
| `current_date` | `mcp-compliance` | all | Today's date for due-date / rate-freshness math |

### Borrower-tier tools

| Tool | Server | Roles | Purpose |
|---|---|---|---|
| `list_my_applications` | `mcp-pipeline` | borrower (self), admin | Discover the borrower's application IDs |
| `start_application` | `mcp-pipeline` | borrower, admin | Start new application or return existing |
| `update_application_data` | `mcp-pipeline` | borrower (self), admin | Validate and store field values |
| `get_application_summary` | `mcp-pipeline` | borrower (self), loan_officer, underwriter, ceo, admin | Show collected data and progress |
| `application_status` | `mcp-pipeline` | borrower (self), loan_officer, underwriter, ceo, admin | Stage, documents, pending actions |
| `document_completeness` | `mcp-pipeline` | borrower (self), loan_officer, underwriter, ceo, admin | Uploaded vs needed |
| `document_processing_status` | `mcp-pipeline` | borrower (self), loan_officer, underwriter, ceo, admin | Processing state of uploads |
| `rate_lock_status` | `mcp-pipeline` | borrower (self), loan_officer, underwriter, ceo, admin | Locked rate, expiration, days remaining |
| `regulatory_deadlines` | `mcp-compliance` | borrower (self), loan_officer, underwriter, ceo, admin | Deadlines + disclaimer |
| `acknowledge_disclosure` | `mcp-compliance` | borrower (self), loan_officer, admin | Record borrower acknowledgment in audit trail |
| `disclosure_status` | `mcp-compliance` | borrower (self), loan_officer, underwriter, ceo, admin | Pending vs acknowledged disclosures |
| `list_conditions` | `mcp-decision` | borrower (self), loan_officer, underwriter, admin | Open conditions for the application |
| `respond_to_condition_tool` | `mcp-decision` | borrower (self), admin | Record borrower text response |
| `check_condition_satisfaction` | `mcp-decision` | borrower (self), loan_officer, underwriter, admin | Verify condition satisfied via documents |

### Loan officer tools (privileged, scope: assigned_applications)

| Tool | Server | Roles | Purpose |
|---|---|---|---|
| `lo_pipeline_summary` | `mcp-pipeline` | loan_officer, admin | Pipeline by stage |
| `lo_application_detail` | `mcp-pipeline` | loan_officer, admin | Full application view |
| `lo_document_review` | `mcp-pipeline` | loan_officer, admin | Documents with status and quality flags |
| `lo_document_quality` | `mcp-pipeline` | loan_officer, admin | Single-document quality detail |
| `lo_completeness_check` | `mcp-pipeline` | loan_officer, admin | Document completeness for LO view |
| `lo_mark_resubmission` | `mcp-pipeline` | loan_officer, admin | Flag a document for resubmission |
| `lo_underwriting_readiness` | `mcp-pipeline` | loan_officer, admin | Readiness gate |
| `lo_submit_to_underwriting` | `mcp-pipeline` | loan_officer, admin | APPLICATION → UNDERWRITING transition |
| `lo_draft_communication` | `mcp-pipeline` | loan_officer, admin | Gather context for borrower draft |
| `lo_send_communication` | `mcp-pipeline` | loan_officer, admin | Record sent communication (audit only) |
| `kb_search` | `mcp-compliance` | loan_officer, underwriter, admin | Compliance KB semantic search |

### Underwriter tools (privileged, scope: full_pipeline)

| Tool | Server | Roles | Purpose |
|---|---|---|---|
| `uw_queue_view` | `mcp-pipeline` | underwriter, admin | UW queue by urgency |
| `uw_application_detail` | `mcp-pipeline` | underwriter, admin | Full application view |
| `calculate_dti` | `mcp-risk` | underwriter, admin | DTI ratio + risk rating |
| `calculate_ltv` | `mcp-risk` | underwriter, admin | LTV ratio + risk rating |
| `evaluate_credit_risk` | `mcp-risk` | underwriter, admin | Credit-score-based risk rating |
| `assess_income_stability` | `mcp-risk` | underwriter, admin | Employment-status-based stability |
| `assess_asset_sufficiency` | `mcp-risk` | underwriter, admin | Asset/loan ratio rating |
| `generate_risk_recommendation` | `mcp-risk` | underwriter, admin | Rule-based recommendation from all five risk signals |
| `uw_predict_loan_approval` | `mcp-risk` | underwriter, admin | Optional ML predictor (returns "not configured" if absent) |
| `uw_save_risk_assessment` | `mcp-decision` | underwriter, admin | Persist completed assessment with audit trail |
| `uw_preliminary_recommendation` | `mcp-decision` | underwriter, admin | Approve / Approve with Conditions / Suspend / Deny |
| `compliance_check` | `mcp-compliance` | underwriter, admin | ECOA / ATR-QM / TRID structured checks |
| `uw_issue_condition` | `mcp-decision` | underwriter, admin | Issue a new condition |
| `uw_review_condition` | `mcp-decision` | underwriter, admin | RESPONDED → UNDER_REVIEW |
| `uw_clear_condition` | `mcp-decision` | underwriter, admin | Clear after review |
| `uw_waive_condition` | `mcp-decision` | underwriter, admin | Waive (PRIOR_TO_CLOSING/FUNDING only) |
| `uw_return_condition` | `mcp-decision` | underwriter, admin | Return to borrower with note |
| `uw_condition_summary` | `mcp-decision` | underwriter, admin | Status counts |
| `uw_render_decision` | `mcp-decision` | underwriter, admin | Two-phase propose-then-confirm decision |
| `uw_draft_adverse_action` | `mcp-compliance` | underwriter, admin | ECOA/FCRA adverse action draft |
| `uw_generate_le` | `mcp-compliance` | underwriter, admin | Loan Estimate generator |
| `uw_generate_cd` | `mcp-compliance` | underwriter, admin | Closing Disclosure generator (post-conditions) |

### CEO-tier tools (read-only, full pipeline, PII-masked responses)

| Tool | Server | Roles | Purpose |
|---|---|---|---|
| `ceo_pipeline_summary` | `mcp-analytics` | ceo, admin | Stage counts, pull-through, turn times |
| `ceo_denial_trends` | `mcp-analytics` | ceo, admin | Denial rate trends, top reasons, per-product |
| `ceo_lo_performance` | `mcp-analytics` | ceo, admin | Per-LO metrics |
| `ceo_application_lookup` | `mcp-analytics` | ceo, admin | By borrower name or app ID |
| `ceo_audit_trail` | `mcp-analytics` | ceo, admin | Per-application audit history |
| `ceo_decision_trace` | `mcp-analytics` | ceo, admin | Backward trace from decision |
| `ceo_audit_search` | `mcp-analytics` | ceo, admin | By time / event type |
| `ceo_model_latency` | `mcp-analytics` | ceo, admin | p50/p95/p99 latency + trend |
| `ceo_model_token_usage` | `mcp-analytics` | ceo, admin | Token totals + per-model breakdown |
| `ceo_model_errors` | `mcp-analytics` | ceo, admin | Error rates and top error types |
| `ceo_model_routing` | `mcp-analytics` | ceo, admin | Model routing distribution |

## RBAC enforcement

The OpenCLAW gateway resolves the calling agent's persona (from the
routed agent ID) and the authenticated user's role (from JWT claims,
or the dev dropdown when `AUTH_DISABLED=true`). The agent's `AGENT.md`
lists which tools it may call; the MCP server enforces the role check
on every call as defense in depth.

`scope: own_data_only` (borrower) is enforced by the MCP server
joining query results on the authenticated `keycloak_user_id`.
`scope: assigned_applications` (loan officer) is enforced by joining
on `applications.assigned_lo_id`. `scope: full_pipeline` (underwriter,
CEO) has no row-level filter beyond HMDA isolation (CEO and
underwriter cannot see HMDA demographic tables).

## PII masking

CEO-role responses pass through a workspace post-response filter that
redacts SSN (full and last-4), full date of birth, and account /
routing numbers. Mirror the upstream FastAPI middleware
(`packages/api/src/middleware/pii.py`) so both transports produce
identical outputs.

## Discoverability

Agents see only the tools allowed for their persona. The full catalog
above is for human reference; an individual `AGENT.md` lists only the
subset that agent uses.
