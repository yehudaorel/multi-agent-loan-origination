# This project was developed with assistance from AI tools.
"""MCP server exposing condition-lifecycle and decision-rendering tools.

Hosts the tools the OpenCLAW Borrower and Underwriter agents use to
move state on conditions and underwriting decisions. Sibling to
``mcp_server.py`` (risk math), ``mcp_compliance.py`` (public + KB
tools), and ``mcp_pipeline.py`` (application / document state).

Critical invariant for ``uw_render_decision``: defense-in-depth check
that ``confirmed=True`` is rejected on first call. The SOUL.md tells
the LLM to always start with ``confirmed=False``; the server should
back that up with a session-level guard so a misbehaving model can't
silently auto-approve.

Track 1 status: skeleton. See ``mcp_pipeline.py`` for the porting
recipe; the same pattern applies here. Each tool body returns a
structured ``_stub`` JSON object pointing at the upstream LangGraph
implementation that is the source of truth.
"""

import json

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("decision", host="0.0.0.0", port=8084)


def _stub(tool: str, source: str, **echo: object) -> str:
    """Return a structured placeholder so callers can detect non-wired tools."""
    return json.dumps(
        {
            "_stub": True,
            "tool": tool,
            "see": source,
            "echo": echo,
            "next": "Track 2: implement using the referenced service-layer function.",
        }
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(request):  # noqa: ARG001
    """Liveness/readiness probe for K8s."""
    return JSONResponse({"status": "healthy"})


# -----------------------------------------------------------------------------
# Borrower-facing condition tools
# -----------------------------------------------------------------------------


@mcp.tool()
async def list_conditions(application_id: int, user_id: str) -> str:
    """List open underwriting conditions for an application."""
    return _stub(
        "list_conditions",
        "packages/api/src/services/condition.py:get_conditions",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def respond_to_condition_tool(
    condition_id: int, user_id: str, response_text: str
) -> str:
    """Record the borrower's text response to an underwriting condition."""
    return _stub(
        "respond_to_condition_tool",
        "packages/api/src/services/condition.py:respond_to_condition",
        condition_id=condition_id,
        user_id=user_id,
        response_text=response_text,
    )


@mcp.tool()
async def check_condition_satisfaction(condition_id: int, user_id: str) -> str:
    """Check whether a condition has been satisfied by reviewing linked documents.

    Reviews extraction results and quality flags to determine if the
    borrower's submission adequately addresses the condition.
    """
    return _stub(
        "check_condition_satisfaction",
        "packages/api/src/services/condition.py:check_condition_documents",
        condition_id=condition_id,
        user_id=user_id,
    )


# -----------------------------------------------------------------------------
# Underwriter risk-assessment persistence
# -----------------------------------------------------------------------------


@mcp.tool()
async def uw_save_risk_assessment(
    application_id: int,
    user_id: str,
    dti: dict,
    ltv: dict,
    credit: dict,
    income_stability: dict,
    asset_sufficiency: dict,
    overall_risk: str,
    recommendation: str,
    rationale: list[str],
    conditions: list[str],
    compensating_factors: list[str],
    warnings: list[str],
    predictive_model_result: str | None = None,
    predictive_model_available: bool = False,
) -> str:
    """Persist a completed risk assessment with audit trail.

    All five risk-tool outputs from mcp-risk plus the optional ML
    predictor result must be passed in. The SOUL.md enforces that the
    underwriter agent runs the full risk assessment chain before
    calling this tool; the server should reject saves that are missing
    any required risk dimension.
    """
    return _stub(
        "uw_save_risk_assessment",
        "packages/api/src/services/risk_assessment.py",
        application_id=application_id,
        user_id=user_id,
        overall_risk=overall_risk,
        recommendation=recommendation,
        predictive_model_available=predictive_model_available,
    )


@mcp.tool()
async def uw_preliminary_recommendation(application_id: int, user_id: str) -> str:
    """Generate a preliminary underwriting recommendation.

    Decision tree returning Approve, Approve with Conditions, Suspend
    (missing data), or Deny (hard limits exceeded). Advisory only.
    """
    return _stub(
        "uw_preliminary_recommendation",
        "packages/api/src/agents/underwriter_tools.py:uw_preliminary_recommendation",
        application_id=application_id,
        user_id=user_id,
    )


# -----------------------------------------------------------------------------
# Underwriter condition lifecycle
# -----------------------------------------------------------------------------


@mcp.tool()
async def uw_issue_condition(
    application_id: int,
    user_id: str,
    description: str,
    severity: str = "prior_to_docs",
    due_date: str | None = None,
) -> str:
    """Issue a new underwriting condition on an application.

    Args:
        application_id: Target application.
        user_id: Authenticated underwriter.
        description: Plain-English description of what's required.
        severity: One of prior_to_approval, prior_to_docs (default),
            prior_to_closing, prior_to_funding. Translated to natural
            language by the agent before showing the borrower.
        due_date: Optional ISO date (YYYY-MM-DD).
    """
    return _stub(
        "uw_issue_condition",
        "packages/api/src/agents/condition_tools.py",
        application_id=application_id,
        user_id=user_id,
        description=description,
        severity=severity,
        due_date=due_date,
    )


@mcp.tool()
async def uw_review_condition(condition_id: int, user_id: str) -> str:
    """Move a condition from RESPONDED to UNDER_REVIEW."""
    return _stub(
        "uw_review_condition",
        "packages/api/src/agents/condition_tools.py",
        condition_id=condition_id,
        user_id=user_id,
    )


@mcp.tool()
async def uw_clear_condition(condition_id: int, user_id: str, note: str | None = None) -> str:
    """Clear a condition after reviewing the borrower's response."""
    return _stub(
        "uw_clear_condition",
        "packages/api/src/agents/condition_tools.py",
        condition_id=condition_id,
        user_id=user_id,
        note=note,
    )


@mcp.tool()
async def uw_waive_condition(condition_id: int, user_id: str, rationale: str) -> str:
    """Waive a condition.

    Only PRIOR_TO_CLOSING and PRIOR_TO_FUNDING conditions may be waived.
    PRIOR_TO_APPROVAL and PRIOR_TO_DOCS conditions are blocking and
    cannot be waived. Rationale is required and persisted on the audit
    trail.
    """
    return _stub(
        "uw_waive_condition",
        "packages/api/src/agents/condition_tools.py",
        condition_id=condition_id,
        user_id=user_id,
        rationale=rationale,
    )


@mcp.tool()
async def uw_return_condition(condition_id: int, user_id: str, note: str) -> str:
    """Return a condition to the borrower with a note about what's missing."""
    return _stub(
        "uw_return_condition",
        "packages/api/src/agents/condition_tools.py",
        condition_id=condition_id,
        user_id=user_id,
        note=note,
    )


@mcp.tool()
async def uw_condition_summary(application_id: int, user_id: str) -> str:
    """Get a summary of condition counts by status for an application."""
    return _stub(
        "uw_condition_summary",
        "packages/api/src/agents/condition_tools.py",
        application_id=application_id,
        user_id=user_id,
    )


# -----------------------------------------------------------------------------
# Decision rendering (two-phase propose-then-confirm)
# -----------------------------------------------------------------------------


@mcp.tool()
async def uw_render_decision(
    application_id: int,
    user_id: str,
    decision_type: str,
    confirmed: bool = False,
    denial_reasons: list[str] | None = None,
    credit_score_used: int | None = None,
    credit_score_source: str | None = None,
    override_rationale: str | None = None,
) -> str:
    """Two-phase decision tool: propose (default) then confirm after approval.

    Args:
        application_id: Target application.
        user_id: Authenticated underwriter.
        decision_type: "approve", "deny", or "suspend".
        confirmed: MUST be False on first call. The agent presents the
            proposal to the underwriter; only after explicit human
            approval ("yes", "confirm", "proceed") is the tool called
            again with confirmed=True.
        denial_reasons: Required when decision_type is "deny" (ECOA).
        credit_score_used: Score the decision was based on, if known.
        credit_score_source: "bureau_hard_pull" or "self_reported".
        override_rationale: Required when overriding the AI
            recommendation.

    Server-side guards (Track 2 implementation must enforce):
        - confirmed=True on first call for a given (application_id,
          user_id, decision_type) is rejected.
        - "deny" without denial_reasons is rejected.
        - "approve" without prior compliance_check pass is rejected
          (compliance gate).
        - "approve" while uncleared blocking conditions exist
          (PRIOR_TO_APPROVAL / PRIOR_TO_DOCS) is rejected.
    """
    return _stub(
        "uw_render_decision",
        "packages/api/src/agents/decision_tools.py",
        application_id=application_id,
        user_id=user_id,
        decision_type=decision_type,
        confirmed=confirmed,
        denial_reasons=denial_reasons,
        override_rationale=override_rationale,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
