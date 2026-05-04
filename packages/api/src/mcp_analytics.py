# This project was developed with assistance from AI tools.
"""MCP server exposing read-only analytics tools for the CEO agent.

Hosts pipeline-wide aggregates, denial trends, LO performance, audit
search, and model-monitoring queries. All tools are read-only by
design; this server should never expose mutation tools. The CEO agent
relies on workspace-side PII masking middleware to redact SSN/DOB/account
numbers from responses.

Sibling to ``mcp_server.py`` (risk math), ``mcp_compliance.py`` (public
+ KB), ``mcp_pipeline.py`` (state), and ``mcp_decision.py`` (decision
+ conditions).

Track 1 status: skeleton. See ``mcp_pipeline.py`` for the porting
recipe; the same pattern applies. Bodies return a structured ``_stub``
JSON object pointing at the upstream LangGraph implementation that is
the source of truth.
"""

import json

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("analytics", host="0.0.0.0", port=8085)


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
# Business analytics
# -----------------------------------------------------------------------------


@mcp.tool()
async def ceo_pipeline_summary(user_id: str, days: int = 30) -> str:
    """Pipeline summary: stage counts, pull-through, turn times.

    Args:
        user_id: Authenticated CEO/admin.
        days: Lookback window. Default 30 days.
    """
    return _stub(
        "ceo_pipeline_summary",
        "packages/api/src/services/analytics.py",
        user_id=user_id,
        days=days,
    )


@mcp.tool()
async def ceo_denial_trends(
    user_id: str, days: int = 30, product: str | None = None
) -> str:
    """Denial rate trends, top denial reasons, optional product filter."""
    return _stub(
        "ceo_denial_trends",
        "packages/api/src/services/analytics.py",
        user_id=user_id,
        days=days,
        product=product,
    )


@mcp.tool()
async def ceo_lo_performance(user_id: str, days: int = 30) -> str:
    """Per-LO performance: pipeline, pull-through, denial rate, turn times."""
    return _stub(
        "ceo_lo_performance",
        "packages/api/src/services/analytics.py",
        user_id=user_id,
        days=days,
    )


@mcp.tool()
async def ceo_application_lookup(
    user_id: str, query: str, limit: int = 10
) -> str:
    """Look up applications by borrower name or application ID.

    PII (SSN, DOB, account numbers) is redacted before responses leave
    the server.
    """
    return _stub(
        "ceo_application_lookup",
        "packages/api/src/services/analytics.py",
        user_id=user_id,
        query=query,
        limit=limit,
    )


# -----------------------------------------------------------------------------
# Audit trail
# -----------------------------------------------------------------------------


@mcp.tool()
async def ceo_audit_trail(application_id: int, user_id: str, limit: int = 100) -> str:
    """Audit trail for a specific application, with hash-chain integrity."""
    return _stub(
        "ceo_audit_trail",
        "packages/api/src/services/audit.py",
        application_id=application_id,
        user_id=user_id,
        limit=limit,
    )


@mcp.tool()
async def ceo_decision_trace(decision_id: int, user_id: str) -> str:
    """Backward trace from a decision to all contributing audit events."""
    return _stub(
        "ceo_decision_trace",
        "packages/api/src/services/audit.py",
        decision_id=decision_id,
        user_id=user_id,
    )


@mcp.tool()
async def ceo_audit_search(
    user_id: str,
    event_type: str | None = None,
    days: int = 7,
    limit: int = 100,
) -> str:
    """Search audit events by time range and/or event type."""
    return _stub(
        "ceo_audit_search",
        "packages/api/src/services/audit.py",
        user_id=user_id,
        event_type=event_type,
        days=days,
        limit=limit,
    )


# -----------------------------------------------------------------------------
# Model monitoring (depends on the observability backend; degrades gracefully
# when monitoring is unavailable)
# -----------------------------------------------------------------------------


@mcp.tool()
async def ceo_model_latency(user_id: str, days: int = 7) -> str:
    """Model latency percentiles (p50, p95, p99) and trend."""
    return _stub(
        "ceo_model_latency",
        "packages/api/src/services/model_monitoring.py",
        user_id=user_id,
        days=days,
    )


@mcp.tool()
async def ceo_model_token_usage(user_id: str, days: int = 7) -> str:
    """Token usage totals and per-model breakdown."""
    return _stub(
        "ceo_model_token_usage",
        "packages/api/src/services/model_monitoring.py",
        user_id=user_id,
        days=days,
    )


@mcp.tool()
async def ceo_model_errors(user_id: str, days: int = 7) -> str:
    """Model error rates and top error types."""
    return _stub(
        "ceo_model_errors",
        "packages/api/src/services/model_monitoring.py",
        user_id=user_id,
        days=days,
    )


@mcp.tool()
async def ceo_model_routing(user_id: str, days: int = 7) -> str:
    """Model routing distribution across all configured models."""
    return _stub(
        "ceo_model_routing",
        "packages/api/src/services/model_monitoring.py",
        user_id=user_id,
        days=days,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
