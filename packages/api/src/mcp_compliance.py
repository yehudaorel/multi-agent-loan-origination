# This project was developed with assistance from AI tools.
"""MCP server exposing public-tier and compliance tools.

Hosts the tools the OpenCLAW Public Assistant calls today (product
catalog lookup, affordability estimation, current date) and the
compliance-flavored tools the authenticated personas need (KB search,
regulatory deadlines, structured compliance checks, disclosure
acknowledgment, LE/CD generation, adverse action drafting).

Sibling to ``mcp_server.py`` (risk math), ``mcp_pipeline.py`` (state),
``mcp_decision.py`` (conditions + decisions), and ``mcp_analytics.py``
(read-only CEO analytics). Kept inside ``packages/api/`` so it can
import directly from ``src.services.*``.

Status:

- ``product_info``, ``affordability_calc``, ``current_date`` are fully
  implemented and stateless.
- The remaining tools (KB search, deadlines, compliance check,
  disclosures, LE/CD, adverse action) are skeleton stubs returning a
  structured ``_stub`` JSON payload. See ``mcp_pipeline.py`` for the
  porting recipe; the same pattern applies here.
"""

import json
from datetime import date

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .schemas.calculator import AffordabilityRequest
from .services.calculator import calculate_affordability
from .services.products import PRODUCTS

mcp = FastMCP("compliance", host="0.0.0.0", port=8082)


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


@mcp.tool()
def product_info() -> str:
    """Retrieve the available mortgage product catalog.

    Returns a plain-text summary of every active product the company
    offers, with id, name, description, minimum down payment, and
    typical rate. The agent should translate this into natural prose
    when surfacing it to the user.
    """
    lines = []
    for product in PRODUCTS:
        lines.append(
            f"- {product.name} ({product.id}): {product.description} "
            f"Min down payment: {product.min_down_payment_pct}%, "
            f"typical rate: {product.typical_rate}%"
        )
    return "\n".join(lines)


@mcp.tool()
def affordability_calc(
    gross_annual_income: float,
    monthly_debts: float = 0,
    down_payment: float = 0,
    interest_rate: float = 6.5,
    loan_term_years: int = 30,
) -> str:
    """Estimate maximum loan amount and monthly payment.

    Pure math, no database access. The agent must collect required
    inputs from the user before calling this tool; it must not invent
    placeholder values.

    Args:
        gross_annual_income: Borrower's total annual income before taxes.
        monthly_debts: Total monthly debt obligations (car, student
            loans, credit cards, child support).
        down_payment: Cash available for down payment.
        interest_rate: Expected interest rate (default 6.5%).
        loan_term_years: Loan term in years (default 30).
    """
    req = AffordabilityRequest(
        gross_annual_income=gross_annual_income,
        monthly_debts=monthly_debts,
        down_payment=down_payment,
        interest_rate=interest_rate,
        loan_term_years=loan_term_years,
    )
    result = calculate_affordability(req)

    parts = [
        f"Max loan amount: ${result.max_loan_amount:,.2f}",
        f"Estimated monthly payment: ${result.estimated_monthly_payment:,.2f}",
        f"Estimated purchase price: ${result.estimated_purchase_price:,.2f}",
        f"DTI ratio: {result.dti_ratio}%",
    ]
    if result.dti_warning:
        parts.append(f"Warning: {result.dti_warning}")
    if result.pmi_warning:
        parts.append(f"Note: {result.pmi_warning}")
    return "\n".join(parts)


@mcp.tool()
def current_date() -> str:
    """Return today's date in ISO format (YYYY-MM-DD).

    Use this when reasoning about due dates, rate freshness, or any
    time-sensitive guidance. Do not infer the date from training data.
    """
    return date.today().isoformat()


# -----------------------------------------------------------------------------
# Authenticated-tier tools (skeleton; Track 2 implementation)
# -----------------------------------------------------------------------------


@mcp.tool()
async def kb_search(query: str, user_id: str, user_role: str) -> str:
    """Search the compliance knowledge base for regulatory guidance.

    Searches federal regulations, agency guidelines, and internal
    policies using semantic similarity. Results are ranked by relevance
    with tier-based priority (federal > agency > internal). Conflicts
    between sources are detected automatically. All searches are logged
    to the audit trail.
    """
    return _stub(
        "kb_search",
        "packages/api/src/agents/compliance_tools.py:kb_search",
        query=query,
        user_id=user_id,
        user_role=user_role,
    )


@mcp.tool()
async def regulatory_deadlines(application_id: int, user_id: str) -> str:
    """Look up regulatory deadlines for a loan application.

    Returns the deadlines (e.g., 3-day TRID window) plus the standard
    regulatory disclaimer. The agent must include the disclaimer when
    surfacing the response.
    """
    return _stub(
        "regulatory_deadlines",
        "packages/api/src/agents/borrower_tools.py:regulatory_deadlines",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def compliance_check(
    application_id: int, user_id: str, regulation_type: str = "ALL"
) -> str:
    """Run structured compliance checks on an application.

    Args:
        application_id: Target application.
        user_id: Authenticated underwriter or admin.
        regulation_type: One of "ECOA", "ATR_QM", "TRID", or "ALL"
            (default). When "ALL", returns each regulation's status
            plus an overall verdict.

    Returns each regulation's status (PASS, CONDITIONAL_PASS, WARNING,
    FAIL) with rationale and detail items. The decision-rendering
    pipeline gates on this tool's results: a FAIL must block approval.
    """
    return _stub(
        "compliance_check",
        "packages/api/src/agents/compliance_check_tool.py",
        application_id=application_id,
        user_id=user_id,
        regulation_type=regulation_type,
    )


@mcp.tool()
async def acknowledge_disclosure(
    user_id: str, application_id: int, disclosure_text: str
) -> str:
    """Record a borrower's acknowledgment of a required disclosure.

    Persists to the audit trail. The borrower's UI presents the full
    disclosure content; this tool records the acknowledgment after the
    borrower clicks "I Acknowledge" in the dashboard.

    Args:
        user_id: Authenticated borrower.
        application_id: Target application.
        disclosure_text: The borrower's acknowledgment message
            (typically "I have reviewed and acknowledge the [Loan
            Estimate / Closing Disclosure / etc.]"). The server parses
            the disclosure name from the text.
    """
    return _stub(
        "acknowledge_disclosure",
        "packages/api/src/services/disclosure.py",
        user_id=user_id,
        application_id=application_id,
        disclosure_text=disclosure_text,
    )


@mcp.tool()
async def disclosure_status(application_id: int, user_id: str) -> str:
    """Check which required disclosures are pending vs acknowledged."""
    return _stub(
        "disclosure_status",
        "packages/api/src/services/disclosure.py:get_disclosure_status",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def uw_generate_le(application_id: int, user_id: str) -> str:
    """Generate a simulated Loan Estimate at application/underwriting stage.

    Records the generated LE in the disclosure audit trail. The
    borrower's view picks it up on the next ``disclosure_status`` call.
    """
    return _stub(
        "uw_generate_le",
        "packages/api/src/agents/disclosure_tools.py",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def uw_generate_cd(application_id: int, user_id: str) -> str:
    """Generate a simulated Closing Disclosure at clear_to_close stage.

    Server-side guard (Track 2 must enforce): this tool must reject
    calls when any non-waived condition is still open.
    """
    return _stub(
        "uw_generate_cd",
        "packages/api/src/agents/disclosure_tools.py",
        application_id=application_id,
        user_id=user_id,
    )


@mcp.tool()
async def uw_draft_adverse_action(
    application_id: int,
    user_id: str,
    denial_reasons: list[str],
    credit_score_used: int | None = None,
    credit_score_source: str | None = None,
) -> str:
    """Draft an ECOA/FCRA adverse action notice for a denied application.

    The output is a draft for the underwriter to review and edit; it is
    not delivered automatically. ECOA requires specific denial reasons
    and disclosure of the credit score used (when one was used).
    """
    return _stub(
        "uw_draft_adverse_action",
        "packages/api/src/agents/disclosure_tools.py",
        application_id=application_id,
        user_id=user_id,
        denial_reasons=denial_reasons,
        credit_score_used=credit_score_used,
        credit_score_source=credit_score_source,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
