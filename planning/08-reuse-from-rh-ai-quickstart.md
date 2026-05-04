# 08 — Reuse from rh-ai-quickstart/multi-agent-loan-origination

Audit of [rh-ai-quickstart/multi-agent-loan-origination](https://github.com/rh-ai-quickstart/multi-agent-loan-origination) for what we lift, what we modify, and what we drop for our OpenCLAW + Xeon 6+ demo.

## TL;DR

- The repo is **~80% of what we need for the application logic** (agent roles, RAG corpus, UI, audit chain, risk math, fair-lending isolation).
- It is **0% reusable as-is for our framework choice**: the agents are Python LangGraph; OpenCLAW is Node/TS markdown-config.
- It is **partly reusable for deployment**: Compose works, Helm chart needs OpenShift- and GPU-specific bits removed.
- **Best news:** *no real external SaaS dependencies exist.* Credit, watchlist, DocuSign — all already simulated locally. Zero mocking work needed there.

## What we keep (high-leverage reuse)

| Asset | Path | Why keep |
|---|---|---|
| **Compliance-KB corpus** | `data/compliance-kb/{tier1-federal,tier2-agency,tier3-internal}/` | Hand-curated, three-tier regulatory RAG content. Hard to recreate. Drop straight into our pgvector. |
| **pgvector schema + seed job** | `deploy/helm/mortgage-ai/templates/seed-job.yaml`, `packages/db/` | Schema + ingestion pipeline. Re-point embedder to our local OpenVINO path. |
| **MCP risk server** | `mcp-risk-server` (port 8081), wired via `packages/api/src/agents/mcp_integration.py` | **Already MCP.** OpenCLAW consumes MCP natively. **Reuse unchanged.** |
| **React UI shell** | `packages/ui/` (React 19, Vite, TanStack Router, shadcn/ui, role-scoped routes) | Five persona views already built (prospect / borrower / loan officer / underwriter / CEO). Only rewire WebSocket transport + drop Keycloak. |
| **Audit chain + HMDA isolation** | `packages/api/src/routes/{audit.py,hmda.py}` | Hash-chained append-only events; demographic isolation for fair-lending. Strong on-stage talking points. Port to whatever language we settle on, or expose as their own MCP. |
| **Tool *logic*** | ~60 Python functions in `packages/api/src/agents/*_tools.py` (risk, conditions, decisions, disclosures, compliance, queue, KB search) | Pure functions over Postgres. The math and rules are reusable; only the language wrapper changes. |
| **Borrower / underwriter personas + scripts** | embedded in agent prompts, queue fixtures | Saves persona-design time. |

## What we modify

### LangGraph → OpenCLAW (the largest chunk of work)

The five Python agents (`public_assistant.py`, `borrower_assistant.py`, `loan_officer_assistant.py`, `underwriter_assistant.py`, `ceo_assistant.py`) become OpenCLAW config:

- One `AGENTS.md` entry per role.
- One `SOUL.md` per role (port the system prompts ~as-is).
- `TOOLS.md` lists the tools each role can call.
- WebSocket chat routes (`packages/api/src/routes/*_chat.py`) → OpenCLAW's native session/channel transport.

**Recommended shortcut for the ~60 tool functions:** rather than rewriting each one in Node/TS, **wrap them as additional MCP servers** (Python stays Python). The MCP boundary is the lingua franca; OpenCLAW already speaks it. This is the single highest-leverage decision in the port — turns "rewrite everything" into "stand up 3–5 small Python MCP servers and point OpenCLAW at them." Group by domain:

- `compliance-mcp` — `kb_search`, `compliance_check`, disclosure generation
- `underwriting-mcp` — risk, condition lifecycle, decision rendering, LE/CD
- `pipeline-mcp` — queue views, urgency scoring, application status
- `analytics-mcp` — CEO/audit/HMDA reporting

Net effect: minimal Python code is *rewritten*, most is *relocated* behind MCP, and the only real new code is OpenCLAW config + a thin Node/TS adapter layer (if any).

### OpenShift → vanilla upstream K8s

Per [07-kubernetes-deployment.md](07-kubernetes-deployment.md):

- `deploy/helm/mortgage-ai/templates/routes.yaml` (`route.openshift.io/v1`) → standard `networking.k8s.io/v1` Ingress.
- `kagenti-agentruntime.yaml` + `kagenti-authbridge` SCC → **drop entirely**. Kagenti is OpenShift-AI-only.
- Any `SecurityContextConstraints` refs → replace with PodSecurity admission labels or delete.
- ImageStream/BuildConfig — not present, so nothing to do; existing `quay.io/rh-ai-quickstart/*` image refs work on vanilla K8s.

### GPU → CPU

- **NeMo Guardrails** template requests `nvidia.com/mig-2g.35gb`. Options: (a) CPU-only guardrails path, (b) tiny safety model on vLLM-CPU / OpenVINO, or (c) drop guardrails for the booth narrative. Pick (b) or (c).
- `values.yaml` default LLM (`gpt-4o-mini` via remote vLLM) → local **vLLM-CPU / llama.cpp / OpenVINO Model Server** OpenAI-compatible endpoint. Same one used for the agents.
- Vision document extraction currently goes through the LLM endpoint (no separate vision model). Either keep that pattern with a multimodal CPU model (Qwen2-VL / similar via OpenVINO) or split out a dedicated vision MCP. Splitting is cleaner for the Fleet View visualization.

### Auth

Keycloak is optional in the upstream (`AUTH_DISABLED=true` in `.env.example`, gated by an `auth` Compose profile). For the booth: **leave it off.** Frees us from a Keycloak pod and simplifies the demo. Keep `middleware/pii.py` masking logic conceptually — it's still relevant for the CEO view.

## What we drop

- **Kagenti AgentRuntime** (Red Hat agent platform; OpenShift-only).
- **OpenShift Routes / SCC.**
- **NeMo Guardrails GPU model** (or CPU-swap if the safety story is needed for the talk track).
- **Keycloak** for the booth (keep the code paths but disable).
- **MLflow** unless we need it. Our observability path is OpenTelemetry → Prometheus + Tempo + Grafana for the Fleet View. MLflow is model-monitoring-flavored and adds little to the booth visual.

## What's missing in the upstream that we must add

1. **OpenCLAW workspace** — `AGENTS.md`, per-role `SOUL.md`, `TOOLS.md`, channel config (WebChat). Net new.
2. **Local CPU-only LLM serving** — vLLM-CPU or OpenVINO Model Server with continuous batching tuned for our concurrency targets. Upstream assumes a remote vLLM.
3. **CPU-only vision pipeline** — small VLM on OpenVINO. Upstream relies on the LLM endpoint's vision capability.
4. **Fleet View UI** — the operator-facing pane showing N concurrent sessions, per-step lights, CPU heatmap, comparison toggle. Upstream has per-persona views but nothing that visualizes a fleet at scale.
5. **Synthetic load generator** — async driver scripting borrower transcripts. Upstream has e2e tests, not load tests.
6. **Telemetry stack** — OpenTelemetry collector + Prometheus + Tempo + Grafana wiring. Upstream has MLflow only.
7. **Helm chart polish for vanilla K8s** — Ingress, no-SCC, no-Kagenti, no-GPU values profile.

## Reuse-vs-rewrite summary table

| Layer | Decision | Effort |
|---|---|---|
| Agent definitions (5 personas) | **Rewrite** as OpenCLAW markdown | M |
| Agent tools (~60 Python fns) | **Relocate** behind 3–5 MCP servers | S–M |
| MCP risk server | **Reuse as-is** | none |
| RAG corpus + schema | **Reuse** | none |
| Embedding/serving | **Re-point** to local OpenVINO | S |
| LLM serving | **Replace** remote vLLM with local CPU | M |
| Vision | **Add** CPU vision MCP (new) | M |
| React UI | **Reuse**, rewire WS + disable auth | S |
| Audit / HMDA | **Reuse** logic (port if abandoning Python entirely) | S |
| Helm chart | **Modify** — drop OpenShift/GPU, add Ingress | S |
| Compose | **Reuse** with edits | S |
| Keycloak | **Disable** | none |
| MLflow | **Drop** (replace with OTel stack) | S |
| Fleet View UI | **New** | M |
| Load generator | **New** | S |

## Key file paths cited (from upstream)

- `packages/api/src/agents/{public,borrower,loan_officer,underwriter,ceo}_assistant.py`
- `packages/api/src/agents/{*_tools.py, mcp_integration.py, registry.py}`
- `packages/api/src/routes/{*_chat.py, hmda.py, audit.py, model_monitoring.py}`
- `packages/api/src/middleware/{auth.py, pii.py}`
- `data/compliance-kb/{tier1-federal,tier2-agency,tier3-internal}/`
- `deploy/helm/mortgage-ai/templates/{routes.yaml, kagenti-agentruntime.yaml, nemo-guardrails*.yaml, seed-job.yaml}`
- `deploy/helm/mortgage-ai/values.yaml`
- `compose.yml`, `.env.example`
