# 09 — Refactor Plan

Plan for refactoring `multi-agent-loan-origination` (cloned at `./multi-agent-loan-origination/`) into the Computex demo: **OpenCLAW + Xeon 6+ Clearwater Forest, vanilla K8s, scale-up + scale-out ready.**

**Strategic decision (locked):** **Full swap LangGraph → OpenCLAW.** The five Python LangGraph agents are rewritten as OpenCLAW config (`SOUL.md` / `AGENTS.md` / `TOOLS.md`); the existing tool *logic* is preserved by relocating it behind a small set of Python MCP servers that OpenCLAW consumes. The FastAPI backend shrinks to a thin REST/WebSocket integration layer for the React UI.

> Production-hardening work that is orthogonal to the refactor lives in [10-production-readiness.md](10-production-readiness.md). This doc focuses on *what changes structurally* to get to the demo target.

## What we keep unchanged

These are the parts of the repo that already pull their weight; touching them would be churn.

- **Postgres schema + Alembic migrations** (`packages/db/`) — vanilla pg16 + pgvector, no OpenShift coupling. Compliance schema isolation (`COMPLIANCE_DATABASE_URL`) is good architecture; keep it.
- **React UI shell** (`packages/ui/`) — TanStack Router, five persona views, role-gated routes. Only the WebSocket transport target and auth glue change.
- **MCP risk server** (`packages/api/src/mcp_server.py`) — already FastMCP / Streamable HTTP / stateless / health-checked. **Keep as-is.**
- **Compliance KB corpus** (`data/compliance-kb/{tier1-federal,tier2-agency,tier3-internal}/`) — hand-curated, hard to recreate. Keep.
- **Containerfile CPU-only path** (`packages/api/Containerfile`) — already pulls CPU-only PyTorch from the PyTorch CPU index. No change needed.
- **Prometheus instrumentation** (`packages/api/src/core/metrics.py` + `prometheus-fastapi-instrumentator`) — `agent_routing_total`, `llm_tokens_total`, `tool_calls_total`, etc. Foundation of the Fleet View; expand, don't replace.
- **Auth bypass** (`AUTH_DISABLED=true`) — already first-class. Use it for the booth.

## What changes (refactor tracks)

The work splits into seven independent tracks. Tracks 1–4 are the critical path; 5–7 can run in parallel.

### Track 1 — OpenCLAW orchestration layer (the largest track)

**Owner deliverable:** an `openclaw-workspace/` directory at repo root that, when launched, exposes the five mortgage personas as OpenCLAW agents over WebChat (and optionally Telegram for booth wow-factor).

Files to create:
```
openclaw-workspace/
├── AGENTS.md                  # roster + routing rules
├── channels.yaml              # WebChat (always) + Telegram (optional)
├── agents/
│   ├── public/SOUL.md         # ported from config/agents/public-assistant.yaml + system prompt in public_assistant.py
│   ├── borrower/SOUL.md
│   ├── loan-officer/SOUL.md
│   ├── underwriter/SOUL.md
│   └── ceo/SOUL.md
├── TOOLS.md                   # references the MCP servers in Track 2
└── skills/                    # any cross-cutting skills (audit logging, etc.)
```

Per-agent porting recipe (apply five times):
1. Read `config/agents/<role>-assistant.yaml` and `packages/api/src/agents/<role>_assistant.py` — extract the system prompt, the tool list, the role ACLs, and the model-routing strategy.
2. Write `agents/<role>/SOUL.md` with the ported persona + instructions. Translate role ACLs into OpenCLAW's per-agent tool permissions.
3. Add an entry in `AGENTS.md` that names the agent and its inbound channel routing.
4. Fast/capable model routing currently happens inside `base.py` (`agent_fast` vs `agent_capable` graph nodes). Two options:
   - **Recommended:** push routing into OpenCLAW config via per-agent model overrides + a small classifier skill that returns `simple|complex`.
   - Or, drop the fast/capable split for the demo; one model per agent is simpler and the booth narrative doesn't need it.

Sandbox model: per-session OpenCLAW sandbox (Docker backend on single-box; pooled runner pods on K8s — see [07-kubernetes-deployment.md](07-kubernetes-deployment.md)). The **specialist agents are NOT per-session** — they're shared services called via MCP. This is what makes 100+ concurrent borrowers fit on one socket.

**Out of scope for this track:** rewriting tool logic. Tools stay in Python, behind MCP (Track 2).

### Track 2 — MCP-ify the existing tools

The repo has ~15 tools today, organized as `*_tools.py` modules. The MCP risk server already hosts the pure-computation risk math. The other tools are mostly DB-backed CRUD over Postgres. We expose them as a small set of additional MCP servers so OpenCLAW can call them without us porting any business logic.

Target topology:
```
mcp-risk         (existing)   - DTI, LTV, credit risk, income/asset stability, affordability
mcp-compliance   (new)        - kb_search (RAG), HMDA/ECOA checks, disclosure generation
mcp-pipeline     (new)        - application status, queue views, urgency, document lookup
mcp-decision     (new)        - condition lifecycle, decision rendering, audit chain writes
mcp-analytics    (new)        - CEO dashboards, model monitoring queries
```

Implementation:
- Each new MCP server is a tiny FastMCP app following the pattern of `packages/api/src/mcp_server.py`.
- Tool *bodies* are imported directly from the existing `packages/api/src/agents/*_tools.py` modules — no rewrite, just re-exposure.
- Each MCP server gets its own Containerfile and Helm Deployment, scaled independently. Stateless; horizontally scalable.
- Health endpoint, Prometheus metrics, structured logs on every server (Track 7).

**Pgvector + KB:** the `kb_search` tool stays in `mcp-compliance`. Embedding generation can run in-process (sentence-transformers, CPU) or as a separate service — keep in-process to start; split out only if it shows up as a hotspot under load.

**Why this is the highest-leverage move:** the tool logic — risk math, condition lifecycle, decision rendering, HMDA isolation — is the actual mortgage-domain code. Keeping it in Python, behind MCP, means the LangGraph → OpenCLAW swap is a *transport* swap, not a logic rewrite.

### Track 3 — FastAPI backend trim

After Tracks 1 and 2, the FastAPI app no longer hosts the agents — OpenCLAW does. The FastAPI service shrinks to:

- `routes/applications.py`, `routes/decisions.py`, `routes/documents.py`, `routes/audit.py`, `routes/hmda.py`, `routes/analytics.py` — REST endpoints the React UI needs. **Keep.**
- `routes/*_chat.py` — WebSocket chat endpoints. **Replace.** The UI now talks to the OpenCLAW Gateway's WebChat endpoint, not FastAPI. We add a thin proxy if needed for same-origin convenience.
- `agents/*` — **delete** after Track 1 cuts over.
- `middleware/auth.py`, `middleware/pii.py` — **keep**. Still apply to REST endpoints.
- `observability.py`, `core/metrics.py` — **keep and extend** (Track 7).

### Track 4 — Vanilla K8s Helm chart

Strip OpenShift / Kagenti / GPU bits and add the new components.

**Delete:**
- `deploy/helm/mortgage-ai/templates/routes.yaml` (4 OpenShift Routes).
- `deploy/helm/mortgage-ai/templates/kagenti-agentruntime.yaml`.
- `deploy/helm/mortgage-ai/templates/nemo-guardrails-*.yaml` (or replace with a CPU-only safety service if we keep the safety story).
- Knative annotations, KServe `ServingRuntime` / `InferenceService` resources.
- `nvidia.com/mig-2g.35gb` resource requests, GPU `nodeSelector`s and tolerations.
- `kagenti-authbridge` SCC reference in `serviceaccount.yaml`.

**Add:**
- `templates/ingress.yaml` — single `networking.k8s.io/v1` Ingress fronting UI + API + (optional) OpenCLAW Gateway.
- `templates/openclaw-gateway.yaml` — Deployment + Service for the Gateway.
- `templates/sandbox-runner-pool.yaml` — pre-warmed sandbox-runner pods (per [07-kubernetes-deployment.md](07-kubernetes-deployment.md)).
- `templates/mcp-{compliance,pipeline,decision,analytics}.yaml` — Deployment + Service per new MCP server, with HPAs.
- `templates/llm-pool.yaml` — vLLM-CPU (or OpenVINO Model Server) Deployment exposing an OpenAI-compatible service. CPU resource requests sized for Clearwater.
- `templates/otel-collector.yaml` + `templates/grafana-stack.yaml` — observability (Track 7).

**Restructure `values.yaml`:**
- `singleNode: true|false` — toggle for compose-equivalent vs cluster mode.
- `gpu.enabled: false` (default) — gate any GPU-only paths behind it.
- Replica counts per MCP / OpenCLAW Gateway.
- HPA targets per service.
- LLM pool sizing.
- CPU node-selector labels (e.g., `intel.feature.node.kubernetes.io/cpu-model: clearwater-forest` if the hardware is labelled).

### Track 5 — Compose stack updates

Single-box / dev path stays primary, but it now has more services.

Edits to `compose.yml`:
- Add `openclaw-gateway` service (Node 24, mounts `openclaw-workspace/`).
- Add `mcp-compliance`, `mcp-pipeline`, `mcp-decision`, `mcp-analytics` services (reuse the API Containerfile, override `command`).
- Add `llm-pool` service (vLLM-CPU or llama.cpp server, OpenAI-compatible).
- Add `vision-pool` service (OpenVINO Model Server with a small VLM).
- Add `otel-collector`, `prometheus`, `tempo`, `grafana` services under an `observability` profile (replace MLflow as the default observability path).
- UI service now points at the Gateway, not the API, for chat traffic.
- API service shrinks (no more chat WS handlers).
- Drop `mortgage-ai-api` dependency on `mcp-risk-server` from chat handlers (only the MCP servers themselves talk to it now, indirectly via the Gateway).

`host.docker.internal` defaults stay for laptop-LM-Studio dev convenience but the chart values for K8s point at `llm-pool.<ns>.svc.cluster.local`.

### Track 6 — UI wiring

The UI needs minimal changes — that's the whole point of keeping the contracts stable.

- WebSocket client (`packages/ui/src/services/`) repointed at the OpenCLAW Gateway WebChat URL.
- Auth glue: keep it gated by an env flag; for the booth, `AUTH_DISABLED=true` and the role is selected from a dropdown.
- New **Fleet View** page (`/fleet`) — net new, see Track 7.

### Track 7 — Observability + Fleet View (the booth visual)

Replace MLflow with the OTel/Prometheus/Tempo/Grafana stack. MLflow is a model-monitoring tool; we need a *concurrency-and-density* visualization.

Components:
- **OpenTelemetry SDK** in every service (FastAPI, Gateway, each MCP). Trace context propagation across MCP boundaries. Use the existing custom Prometheus metrics as well.
- **OTel Collector** receives OTLP, fans out to Prometheus (metrics) and Tempo (traces).
- **Grafana** dashboards:
  - *Fleet View*: N concurrent sessions, per-session step indicator, p50/p95/p99 per step, tokens/sec across the LLM pool.
  - *Hardware*: CPU heatmap (288 cores), DDR bandwidth, LLC hit rate, RAPL power.
  - *Comparison*: side-by-side replay overlay of Sierra Forest baseline.
- **Fleet View React page** — embeds Grafana panels via the Grafana panel-iframe, plus a custom session-grid component that subscribes to OpenCLAW Gateway events for the per-session light-up effect.

### Track 8 — Load generator

Net-new. Async Python or k6 driving the Gateway's WebChat endpoint with scripted borrower transcripts. Lives at `tools/loadgen/`. Used for the concurrency sweep in [05-scalability-benchmarks.md](05-scalability-benchmarks.md).

## Sequencing & critical path

```
Track 2 (MCP-ify tools)  ──────┐
                                ├──→ Track 1 (OpenCLAW)  ──→ Track 6 (UI rewire)  ──┐
Track 3 (FastAPI trim)   ──────┘                                                     ├──→ booth
                                                                                      │
Track 4 (vanilla K8s)    (parallel, depends on Track 5 stabilizing image set) ───────┤
Track 5 (Compose)        (parallel; first to land — that's how we develop) ──────────┤
Track 7 (OTel + Fleet)   (parallel from week 1; foundation needed before Track 8) ───┤
Track 8 (Load gen)       (after Track 7 + an end-to-end happy path)  ────────────────┘
```

Critical path runs through Track 2 → Track 1 → Track 6. Everything else is parallelizable with enough hands.

## Map to existing repo file paths

| Track | Touch | Action |
|---|---|---|
| 1 | `openclaw-workspace/**` | Create |
| 1 | `config/agents/*.yaml`, `packages/api/src/agents/*_assistant.py` | Read & port (then delete) |
| 2 | `packages/mcp-compliance/`, `packages/mcp-pipeline/`, `packages/mcp-decision/`, `packages/mcp-analytics/` | Create new sub-packages |
| 2 | `packages/api/src/agents/*_tools.py` | Move/relocate behind MCP servers |
| 2 | `packages/api/src/mcp_server.py` | Keep as-is (template for new servers) |
| 3 | `packages/api/src/main.py` | Trim (drop chat route registrations, drop agent lifespan) |
| 3 | `packages/api/src/routes/*_chat.py` | Delete |
| 3 | `packages/api/src/agents/` | Delete after cutover |
| 4 | `deploy/helm/mortgage-ai/templates/routes.yaml` | Delete |
| 4 | `deploy/helm/mortgage-ai/templates/kagenti-agentruntime.yaml` | Delete |
| 4 | `deploy/helm/mortgage-ai/templates/nemo-guardrails-*.yaml` | Delete (or CPU-replace) |
| 4 | `deploy/helm/mortgage-ai/templates/ingress.yaml` | Create |
| 4 | `deploy/helm/mortgage-ai/templates/openclaw-gateway.yaml` | Create |
| 4 | `deploy/helm/mortgage-ai/templates/sandbox-runner-pool.yaml` | Create |
| 4 | `deploy/helm/mortgage-ai/templates/mcp-*.yaml` | Create (one per new MCP) |
| 4 | `deploy/helm/mortgage-ai/templates/llm-pool.yaml` | Create |
| 4 | `deploy/helm/mortgage-ai/values.yaml` | Restructure |
| 5 | `compose.yml` | Edit (add gateway, MCP services, OTel stack; trim API) |
| 6 | `packages/ui/src/services/` | Repoint WS client |
| 6 | `packages/ui/src/routes/_authenticated/fleet.tsx` | Create |
| 7 | `packages/api/src/observability.py` + new components | Extend; add OTel SDK setup |
| 7 | `deploy/helm/mortgage-ai/templates/otel-collector.yaml`, `grafana-stack.yaml` | Create |
| 8 | `tools/loadgen/` | Create |

## Risks specific to this refactor

1. **OpenCLAW message-history parity with LangGraph checkpointer.** LangGraph's per-thread message persistence is mature; OpenCLAW's session model is younger. Validate that long borrower conversations (50+ turns) keep coherent context. **Mitigation:** prototype with the Public agent first; if OpenCLAW's session store falls short, store conversation history in Postgres ourselves and pass it in as context per turn.
2. **OpenCLAW WebChat protocol vs the existing UI's WebSocket framing.** The repo's UI expects a specific event stream (`token`, `tool_start`, `tool_end`, `done`). If OpenCLAW's WebChat events differ, write a tiny adapter rather than rewriting the UI.
3. **Per-session sandbox at 100+ concurrent borrowers.** Already flagged in [02-openclaw-framework.md](02-openclaw-framework.md). Measure early; fall back to pooled non-sandboxed sessions if Docker-per-session won't fit.
4. **Trace context across MCP boundaries.** Standard OTel HTTP propagation works for Streamable HTTP MCP. Verify in week 1; the rh-ai-quickstart sibling repo `it-self-service-agent` has a working pattern to copy.
5. **Loss of NeMo Guardrails safety shields.** If the safety narrative matters for the FSI talk track, replace with a CPU-only safety model on OpenVINO; otherwise drop and rely on agent-prompt-level guardrails.
6. **Per-agent "fast vs capable" model routing.** Currently inside `base.py`. Don't recreate it on day 1 — start with one model per agent. Add the routing skill back if perf/cost demands it.

## Success criteria for the refactor

- A single OpenCLAW Gateway can serve all five personas to the existing React UI, end-to-end, on a developer laptop.
- All five personas' agents are defined entirely in markdown config — zero Python in `openclaw-workspace/`.
- Helm chart deploys cleanly to a fresh `kind` cluster (`helm install` with no flags). No CRDs required.
- No GPU resource requests anywhere in the chart (or all gated behind `gpu.enabled`).
- A single-page Grafana dashboard renders Fleet View metrics for at least 25 concurrent synthetic borrowers driven by the load generator.
