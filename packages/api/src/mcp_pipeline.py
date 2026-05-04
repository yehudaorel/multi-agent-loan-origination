# This project was developed with assistance from AI tools.
"""MCP server exposing pipeline / application-state tools.

Hosts the read-and-mutate tools the OpenCLAW Borrower, Loan Officer, and
Underwriter agents need to navigate applications, documents, queues, and
rate locks. Sibling to ``mcp_server.py`` (risk math) and
``mcp_compliance.py`` (public + KB tools).

Track 1 status: skeleton. Every tool below is registered with the
correct signature and docstring so OpenCLAW's ``tools/list`` returns a
proper schema and the LLM can call them. Bodies return a structured
``_stub`` JSON object pointing at the upstream LangGraph implementation
that is the source of truth for the actual logic. Filling in each body
is mechanical:

1. Read the referenced ``packages/api/src/agents/<persona>_tools.py``
   tool body.
2. Strip the ``InjectedState`` argument; replace with explicit
   ``user_id``, ``user_role``, and (where relevant) ``application_id``
   parameters that OpenCLAW will pass from session metadata.
3. Open ``SessionLocal()`` directly and call the same underlying
   service-layer function the upstream tool calls.
4. Return the same formatted string the upstream tool returned.

Doing this in Track 2 (after schema validation locally) keeps the work
unambiguous and avoids re-porting if OpenCLAW's session-metadata
contract differs from what we assumed.
"""

import json

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("pipeline", host="0.0.0.0", port=8083)


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
# Borrower-tier tools
# -----------------------------------------------------------------------------


@mcp.tool()
async def list_my_applications(user_id: str) -> str:
    """List the authenticated borrower's mortgage applications.

    Use this to discover the borrower's application IDs before calling
    other tools that require an application_id. Most borrowers have one
    active application.
    """
    return _stub(
        "list_my_applications",
        "packages/api/src/agents/borrower_tools.py:list_my_applications",
        user_id=user_id,
    )


@mcp.tool()
async def start_application(user_id: str) -> str:
    """Start a new mortgage application or return the existing active one."""
    return _stub(
        "start_application",
        "packages/api/src/services/intake.py:start_application",
        user_id=user_id,
    )


@mcp.tool()
async def update_application_data(
    application_id: int, user_id: str, fields: dict
) -> str:
    """Validate and store field values for a mortgage application.

    Args:
        application_id: The application to update.
        user_id: Authenticated borrower's id.
        fields: A JSON object mapping field names to values. Valid keys:
            first_name, last_name, email, ssn, date_of_birth,
            employment_status, loan_type, property_address, loan_amount,
            property_value, gross_monthly_income, monthly_debts,
            total_assets, credit_score.
    """
    return _stub(
        "update_application_data",
        "packages/api/src/services/intake.py:update_application_fields",
        application_id=application_id,
        user_id=user_id,
        fields=fields,
    )


@mcp.tool()
async def get_application_summary(application_id: int, user_id: str) -> str:
    """Show collected application data, progress, and remaining fields.

    SSN is always masked to last 4 digits. Other PII is shown verbatim
    only to the authenticated borrower; loan officer / underwriter / CEO
    callers see the role-appropriate masked variant per RBAC.
    """
    return _stub(
        "get_application_summary",
        "packages/api/src/services/intake.py:get_application_progress",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def application_status(application_id: int, user_id: str) -> str:
    """Get the application's overall status: stage, documents, pending actions."""
    return _stub(
        "application_status",
        "packages/api/src/services/status.py:get_application_status",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def document_completeness(application_id: int, user_id: str) -> str:
    """Check which documents are uploaded and which are still needed."""
    return _stub(
        "document_completeness",
        "packages/api/src/services/completeness.py:check_completeness",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def document_processing_status(application_id: int, user_id: str) -> str:
    """Check the processing status of uploaded documents (processing, complete, failed)."""
    return _stub(
        "document_processing_status",
        "packages/api/src/services/document.py:list_documents",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def rate_lock_status(application_id: int, user_id: str) -> str:
    """Check rate lock status: locked rate, expiration, days remaining."""
    return _stub(
        "rate_lock_status",
        "packages/api/src/services/rate_lock.py:get_rate_lock_status",
        application_id=application_id,
        user_id=user_id,
    )


# -----------------------------------------------------------------------------
# Loan officer tools
# -----------------------------------------------------------------------------


@mcp.tool()
async def lo_pipeline_summary(user_id: str) -> str:
    """Summary of all applications in the loan officer's pipeline, by stage."""
    return _stub(
        "lo_pipeline_summary",
        "packages/api/src/agents/loan_officer_tools.py:lo_pipeline_summary",
        user_id=user_id,
    )


@mcp.tool()
async def lo_application_detail(application_id: int, user_id: str) -> str:
    """Detailed application summary: borrower, financials, stage, conditions."""
    return _stub(
        "lo_application_detail",
        "packages/api/src/agents/loan_officer_tools.py:lo_application_detail",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_document_review(application_id: int, user_id: str) -> str:
    """List all documents for an application with status and quality flags."""
    return _stub(
        "lo_document_review",
        "packages/api/src/agents/loan_officer_tools.py:lo_document_review",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_document_quality(document_id: int, user_id: str) -> str:
    """Inspect detailed quality info for a specific document."""
    return _stub(
        "lo_document_quality",
        "packages/api/src/agents/loan_officer_tools.py:lo_document_quality",
        document_id=document_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_completeness_check(application_id: int, user_id: str) -> str:
    """Check document completeness for a loan-officer view of an application."""
    return _stub(
        "lo_completeness_check",
        "packages/api/src/agents/loan_officer_tools.py:lo_completeness_check",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_mark_resubmission(document_id: int, user_id: str, reason: str) -> str:
    """Flag a document for resubmission with a reason explaining what to fix."""
    return _stub(
        "lo_mark_resubmission",
        "packages/api/src/agents/loan_officer_tools.py:lo_mark_resubmission",
        document_id=document_id,
        user_id=user_id,
        reason=reason,
    )


@mcp.tool()
async def lo_underwriting_readiness(application_id: int, user_id: str) -> str:
    """Check if an application is ready for underwriting submission."""
    return _stub(
        "lo_underwriting_readiness",
        "packages/api/src/agents/loan_officer_tools.py:lo_underwriting_readiness",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_submit_to_underwriting(application_id: int, user_id: str) -> str:
    """Submit an application to underwriting (APPLICATION -> PROCESSING -> UNDERWRITING).

    Caller must have already confirmed with the loan officer; the agent's
    SOUL.md enforces explicit confirmation before this is invoked.
    """
    return _stub(
        "lo_submit_to_underwriting",
        "packages/api/src/agents/loan_officer_tools.py:lo_submit_to_underwriting",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def lo_draft_communication(
    application_id: int, user_id: str, communication_type: str
) -> str:
    """Gather full application context for drafting a borrower communication.

    Args:
        application_id: The target application.
        user_id: Authenticated loan officer.
        communication_type: One of "document_request", "condition_explanation",
            "status_update", "resubmission_notice".
    """
    return _stub(
        "lo_draft_communication",
        "packages/api/src/agents/loan_officer_tools.py:lo_draft_communication",
        application_id=application_id,
        user_id=user_id,
        communication_type=communication_type,
    )


@mcp.tool()
async def lo_send_communication(
    application_id: int, user_id: str, draft_text: str, communication_type: str
) -> str:
    """Record that a borrower communication was sent (audit only at MVP)."""
    return _stub(
        "lo_send_communication",
        "packages/api/src/agents/loan_officer_tools.py:lo_send_communication",
        application_id=application_id,
        user_id=user_id,
        draft_text=draft_text,
        communication_type=communication_type,
    )


# -----------------------------------------------------------------------------
# Underwriter pipeline tools (queue + detail; risk math lives in mcp-risk,
# decisioning in mcp-decision)
# -----------------------------------------------------------------------------


@mcp.tool()
async def uw_queue_view(user_id: str) -> str:
    """View the underwriting queue sorted by urgency (critical, high, normal)."""
    return _stub(
        "uw_queue_view",
        "packages/api/src/agents/underwriter_tools.py:uw_queue_view",
        user_id=user_id,
    )


@mcp.tool()
async def uw_application_detail(application_id: int, user_id: str) -> str:
    """Get full application details: borrower, financials, documents, conditions."""
    return _stub(
        "uw_application_detail",
        "packages/api/src/agents/underwriter_tools.py:uw_application_detail",
        application_id=application_id,
        user_id=user_id,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
