# 13 — Integration with `agentic-intel-demo`

The booth-facing demo stack lives at
[`napetrov/agentic-intel-demo`](https://github.com/napetrov/agentic-intel-demo)
(cloned at `/home/orelyehu/workspace/computex_demo/agentic-intel-demo/`).
This is the **integration target**: our mortgage agents and MCP
servers plug *into* it, they do not replace it.

This doc supersedes parts of `04-architecture.md`,
`07-kubernetes-deployment.md`, and `09-refactor-plan.md` where they
assumed our work was the booth UI. Those still describe what we built
in `multi-agent-loan-origination/`; the demo-facing shape lives here.

## What changed in the picture

The audit (`Agent` results, prior turn) revealed:

- **Two-system Intel CPU architecture.** System A (Xeon 6+
  "Clearwater Forest") holds the OpenClawInstance gateway, control
  plane, LiteLLM, session pods. System B (GNR, "Granite Rapids")
  hosts vLLM + MinIO + offload-worker. The hardware story is now
  *Clearwater Forest density on System A* + *offload to GNR on System
  B* — richer than our single-socket plan.
- **OpenCLAW is operator-driven.** The `openclaw-rocks/openclaw-operator`
  v0.30.0 (external repo) manages an `OpenClawInstance` CR. The CR's
  `spec.config."openclaw.json"` is an inline JSON object; the
  workspace mounts as a 10Gi PVC.
- **Workspace today is single-persona.** The demo ships
  `demo-workspace/{SOUL.md, AGENTS.md, IDENTITY.md, BOOTSTRAP.md,
  MEMORY.md, USER.md}` for one persona ("Agent"). No multi-persona
  convention exists yet.
- **Scenarios are the integration unit.** `catalog/scenarios.yaml`
  declares scenarios with `execution_mode` (`local_standard` |
  `local_large` | `offload_system_b`) and `task_family` enums. Each
  scenario maps to a card in `web-demo/index.html` whose "Run demo"
  button POSTs a `liveScenario` payload to `/api/offload`.
- **No MCP plumbing today.** `runtimes/agent-stub/` exposes
  `POST /tools/invoke`; `runtimes/offload-worker/` has an
  `agent_invoke` task type. Neither speaks MCP. Our five MCP servers
  are net-new pattern in this stack.
- **State store is SQLite, not Postgres.** Sessions and jobs persist
  via `runtimes/control-plane/persistence.py::SqliteJsonStore`.
  Compliance KB pgvector is an additional service we add, not a
  replacement.
- **Provider routing goes through LiteLLM.** Aliases `fast`,
  `default`, `reasoning`, `sambanova` point at vLLM (Qwen3-4B-Instruct-2507),
  Bedrock (Claude Sonnet 4-5), and SambaNova (DeepSeek-V3.1). Booth
  default is **Bedrock for reasoning + vLLM Qwen3-4B for everything
  else**.
- **Telegram is the operator control channel, not the audience
  surface.** Audience uses the web portal; operator drives scenarios
  from a phone via Telegram bot.

## Strategic decisions (locked)

| Question | Choice |
|---|---|
| Persona shape | **Extend `demo-workspace/` to multi-persona** — five-persona layout we built lands as a new convention |
| MCP plumbing | **OpenCLAW plugins (allow-listed)** — register MCP servers in `OpenClawInstance.spec.config."openclaw.json".plugins.allow` |
| Scenario slot | **Add as fifth scenario** — additive; co-exists with `terminal_agent`, `market_research`, `large_build_test`, `taskflow_pull` |
| KB placement | **System A `platform` namespace** — pgvector Deployment alongside the OpenClawInstance gateway |

## Validation gates (pre-implementation)

Two assumptions are baked into the picks above. **Verify these
before committing code, locally on the home box once you bring up
Tier 2.**

### Gate 1 — Does operator v0.30.0 accept multi-persona workspaces?

The shipped `examples/openclawinstance-intel-demo.yaml` mounts
`demo-workspace/` flat. The OpenCLAW community pattern we built
toward (`shenhao-stu/openclaw-agents`) uses `.agents/<id>/{soul,agent,user}.md`
with a top-level `agents.yaml` manifest.

**To verify:** read the operator's CR controller for what it does
with `spec.storage.workspace`. If it just rsync's the contents of a
ConfigMap or PVC into `${OPENCLAW_WORKSPACE}` and lets OpenCLAW pick
up the file layout, we're fine — the OpenCLAW runtime handles
multi-persona discovery if the workspace is shaped right. If the
operator validates the workspace shape against a schema, we may need
a small upstream PR.

**Fallback if multi-persona is rejected:** collapse to **one
orchestrator persona with role-aware tools** (the alternative I
listed in the prior question). The five SOUL.md files we wrote
become a single SOUL.md with role-conditional sections, and RBAC
moves entirely to the MCP server side. Lossy but workable.

**Where to look:**
- Operator source: clone `https://github.com/openclaw-rocks/openclaw-operator`,
  check the controller code for `OpenClawInstance` reconciliation.
- Sample CR: `agentic-intel-demo/examples/openclawinstance-intel-demo.yaml`.
- Workspace mount path: per the operator's container env, default is
  `~/.openclaw/workspace`.

### Gate 2 — Does the OpenCLAW gateway register external MCP servers as plugins?

The OpenClawInstance config has a `plugins.allow` list with values
like `mcp-risk`, but the existing booth demo doesn't use it for
external MCP — its sample shows built-in plugins only.

**To verify:** read OpenCLAW's plugin loader docs (`docs.openclaw.ai`)
or the source. We need to confirm:

1. Whether `plugins.allow: ["mcp-foo"]` triggers OpenCLAW to load an
   MCP server with that name from a registry, or whether the entry
   refers to a built-in plugin.
2. Where the URL/transport is configured (a separate `plugins.config`
   block? or implicit?).

**Fallback if OpenCLAW doesn't speak external MCP:** wrap each MCP
server's catalog behind the **`agent_invoke` task type** in
`runtimes/offload-worker/app.py`. The agent calls one tool surface;
the offload-worker fans out to the right MCP server based on tool
name. We lose direct MCP semantics in OpenCLAW but keep our server
architecture and the demo's offload pattern.

## Two-system topology for the mortgage scenario

```
┌─ System A (Xeon 6+ "Clearwater Forest") ─────────────────────┐
│  namespace: openclaw-operator-system                          │
│    openclaw-operator (Deployment)                             │
│                                                               │
│  namespace: agents                                            │
│    OpenClawInstance/intel-demo                                │
│      gateway pod   (workspace volume = our demo-workspace)    │
│      session pods (per-user, density story)                   │
│                                                               │
│  namespace: inference                                         │
│    LiteLLM proxy                                              │
│                                                               │
│  namespace: platform   <- NEW for our work                    │
│    pgvector Deployment + PVC                                  │
│    pgvector Service                                           │
│    mcp-compliance Deployment + Service     (port 8082)        │
│    mcp-pipeline   Deployment + Service     (port 8083)        │
│    mcp-decision   Deployment + Service     (port 8084)        │
│    mcp-analytics  Deployment + Service     (port 8085)        │
│    (mcp-risk lives here too OR moves to System B — see below) │
└──────────────────────────────────────────────────────────────┘

┌─ System B (Granite Rapids) ──────────────────────────────────┐
│  namespace: system-b                                          │
│    vllm                                                       │
│    minio                                                      │
│    offload-worker                                             │
│    mcp-risk (optional, if we move heavy risk math here)       │
└──────────────────────────────────────────────────────────────┘
```

**Why MCP servers on System A by default.** They're stateless,
DB-bound (Postgres), low-CPU. They live next to the OpenClawInstance
gateway so tool calls don't cross the system boundary. Density on A
isn't hurt because each MCP server is small (FastAPI process, ~50MB
RAM each).

**`mcp-risk` is the candidate to migrate to System B** — its
`generate_risk_recommendation` tool runs the predictive ML model
(once configured), and the booth narrative for "scale up vs scale out"
benefits from one tool that *demonstrably* offloads. Optional,
defer to the implementation pass.

## File-level integration map

Files in `agentic-intel-demo/` we add or modify:

| Path | Action | Purpose |
|---|---|---|
| `catalog/scenarios.yaml` | Add `mortgage_officer` entry | Scenario declaration |
| `catalog/tasks.yaml` | Add `loan_origination` task family | New task family |
| `schemas/scenarios.schema.json` | Add `loan_origination` to enum | Schema validation passes |
| `schemas/tasks.schema.json` | Possibly extend if new fields needed | Schema |
| `agents/scenarios/mortgage-officer/flow.md` | Create | Per-scenario flow content |
| `agents/scenarios/mortgage-officer/run.sh` | Create | Run script (also embedded into offload-worker ConfigMap) |
| `agents/scenarios/mortgage-officer/task-brief.md` | Create | Task brief content |
| `agents/orchestrator.md` | Modify | Add `scenario:mortgage_officer` callback |
| `agents/context-map.md` | Modify | Add mortgage-officer file load list |
| `demo-workspace/agents/public-assistant/{SOUL,AGENT,USER}.md` | Create (copy from `multi-agent-loan-origination/openclaw-workspace/`) | Persona content |
| `demo-workspace/agents/borrower-assistant/{SOUL,AGENT,USER}.md` | Create | Persona content |
| `demo-workspace/agents/loan-officer-assistant/{SOUL,AGENT,USER}.md` | Create | Persona content |
| `demo-workspace/agents/underwriter-assistant/{SOUL,AGENT,USER}.md` | Create | Persona content |
| `demo-workspace/agents/ceo-assistant/{SOUL,AGENT,USER}.md` | Create | Persona content |
| `demo-workspace/AGENTS.md` | Modify | Multi-persona roster + path-based routing rules |
| `examples/openclawinstance-intel-demo.yaml` | Modify | Add `plugins.allow: [mcp-risk, mcp-compliance, ...]`; bump `storage.workspace.size` if 10Gi tight |
| `config/agents.yaml` | Modify | Add five mortgage agents to registry (DNS-1035 ids ≤59 chars) |
| `config/pod-profiles/profiles.yaml` | Possibly modify | Add a `mortgage` profile or alias `medium` |
| `config/model-routing/litellm-config.yaml` | Modify | Add `minimax` and ensure `sambanova` aliases for our env-profiles concept |
| `runtimes/control-plane/agent_registry.py` | Possibly modify | Surface mortgage personas if we want them in `GET /api/agents` |
| `runtimes/offload-worker/app.py` | Possibly modify | Add `mortgage_invoke` task type *if Gate 2 fails* |
| `k8s/system-a/pgvector.yaml` | Create | pgvector Deployment + PVC + Service |
| `k8s/system-a/mcp-compliance.yaml` | Create | mcp-compliance Deployment + Service |
| `k8s/system-a/mcp-pipeline.yaml` | Create | mcp-pipeline Deployment + Service |
| `k8s/system-a/mcp-decision.yaml` | Create | mcp-decision Deployment + Service |
| `k8s/system-a/mcp-analytics.yaml` | Create | mcp-analytics Deployment + Service |
| `k8s/system-a/mcp-risk.yaml` (or `system-b/`) | Create | mcp-risk Deployment + Service |
| `k8s/shared/intel-demo-operator-secrets.yaml.template` | Modify | Add MCP-server credentials (DB password, etc.) |
| `web-demo/index.html` | Modify | Fifth scenario card |
| `web-demo/app.js` | Modify | `liveScenario` entry for `mortgage_officer` |
| `web-demo/scenarios` map | Modify | Mortgage scenario metadata |

Files in `multi-agent-loan-origination/` we keep as **source of
truth for mortgage logic**:

| Path | Role going forward |
|---|---|
| `packages/api/src/services/` | Business logic library (imported by MCP servers) |
| `packages/api/src/agents/*_tools.py` | Tool function bodies (referenced when filling MCP stubs) |
| `packages/api/src/mcp_compliance.py` etc. | MCP server entrypoints (containerized for K8s) |
| `data/compliance-kb/` | Compliance KB corpus (loaded into pgvector) |
| `packages/db/` | Postgres schema + Alembic migrations (used by both stacks) |
| `openclaw-workspace/agents/*/SOUL.md` | Persona prompts (copied verbatim into `agentic-intel-demo/demo-workspace/agents/`) |

Files in `multi-agent-loan-origination/` we **drop or shelve** for
the booth demo:

| Path | Reason |
|---|---|
| `packages/ui/` | Booth UI is `agentic-intel-demo/web-demo/`. Keep the React UI as a *secondary* dev surface for non-booth showcase if useful, but it's not the booth. |
| `packages/api/src/routes/*_chat.py` | Replaced by OpenCLAW gateway → MCP path |
| `packages/api/src/agents/*_assistant.py` | LangGraph layer — replaced by OpenCLAW SOUL/AGENT/USER files |
| `compose.yml` | Useful for *MCP-server-only* dev (boot the five MCP servers locally to test against). Still keeps value. |
| `env-profiles/` | Concept stays; mechanism changes (LiteLLM aliases, not direct `LLM_BASE_URL`) |

## How env-profiles translate to LiteLLM aliases

Our `env-profiles/{local-ollama,minimax,sambanova}.env` was about
pointing the upstream FastAPI/LangGraph at different OpenAI-compatible
endpoints. In `agentic-intel-demo` the agent talks to **LiteLLM**
which fans out to providers via aliases. Translation:

| env-profile concept | LiteLLM equivalent (in `config/model-routing/litellm-config.yaml`) |
|---|---|
| `local-ollama.env` | Add a `local` model alias pointing at Ollama on the host. Today's `default` is `vllm`; switch via env override `MODEL_DEFAULT=local` if needed. |
| `minimax.env` | Add a `minimax` alias mapping to `openai/MiniMax-M2.7` with `api_base: https://api.minimax.io/v1`. (No shim today.) |
| `sambanova.env` | **Already exists** as the `sambanova` alias in the LiteLLM config. |

The `OpenClawInstance.spec.config."openclaw.json".agents.defaults.model`
references aliases by name (`litellm/fast`, `litellm/sambanova`,
etc.). Switching providers for the booth means flipping that field.

## What stays useful from prior work

The substance is portable; the deployment shape is what changes.

- **All five SOUL.md files**: persona prompts, behavioral rules,
  multi-step workflows (underwriter risk-assessment chain,
  two-phase decision flow, condition-category picker). Copy verbatim
  into `agentic-intel-demo/demo-workspace/agents/`.
- **All five MCP server skeletons**: tool definitions with correct
  signatures and `_stub` payloads pointing at upstream service
  functions. Stays in `multi-agent-loan-origination/packages/api/src/`,
  containerized, deployed to System A.
- **Compliance KB corpus** (`data/compliance-kb/`): three-tier
  federal/agency/internal content, ingested into pgvector at boot.
- **Postgres schema** (`packages/db/`): vanilla pg16 + pgvector,
  Alembic-managed. Deploys to `agents` namespace or new `platform`
  namespace.
- **Audit chain, HMDA isolation, two-phase decision invariant**: the
  defensible mortgage-domain patterns. Preserve when filling MCP stubs.
- **Hardware story**: Clearwater Forest density on System A is now
  paired with GNR offload on System B — strictly more compelling.

## What's net-new from this integration

Things we didn't plan for in the prior tracks:

1. **Operator-managed lifecycle.** We never had to deal with an
   operator + CRD before. Three new artifacts to learn:
   - `OpenClawInstance` CR shape (`examples/openclawinstance-intel-demo.yaml`).
   - The operator's reconcile loop (we don't write code here, but we
     need to understand the workspace mount + secret refs).
   - Operator install flow (`scripts/install-openclaw-operator.sh`).

2. **Scenario / catalog discipline.** Adding a scenario isn't free — it
   requires schema changes, orchestrator callback wiring, web-demo card
   updates, and a `run.sh` that lives in two places (`agents/scenarios/`
   AND `k8s/system-b/offload-worker.yaml` ConfigMap). All of this is
   CI-gated by JSON Schema validation.

3. **LiteLLM aliasing.** Provider routing is now a YAML config
   change, not an env override. Operationally cleaner; requires a
   one-line PR pattern.

4. **Telegram operator role.** The booth narrative includes the
   operator driving scenarios from a phone. Our `webchat` channel
   plans pivot — webchat may still serve the audience-facing chat,
   but Telegram is the control surface.

5. **CI gates.** `make validate-templates`, `make lint`, `make test`,
   `make tier1-scenario-slice` must all pass for every change.

## Sequencing

The implementation order should be **validation-gated**: don't write
code that depends on Gates 1 and 2 until they're confirmed.

### Phase A — Validation (do first, on home box)

1. Stand up Tier 1 (`make tier1-up`) on the home box. Verify the
   four shipped scenarios work.
2. Stand up Tier 2 (`make tier2-*`). This is the canonical
   end-to-end. Apply `examples/openclawinstance-intel-demo.yaml`,
   verify the gateway pod boots and the demo task succeeds.
3. **Gate 1**: read operator source; test multi-persona workspace
   layout (drop a fake `agents/<id>/SOUL.md` into `demo-workspace/`,
   apply, see if OpenCLAW picks it up).
4. **Gate 2**: read OpenCLAW plugin docs; test
   `plugins.allow: ["mcp-foo"]` with a tiny test MCP server.
5. Document findings in `agentic-intel-demo`'s docs and decide: full
   path forward, or fall back per the gate fallback notes above.

### Phase B — MCP plumbing (System A platform namespace)

6. Build and push the four new MCP server images (built from
   `multi-agent-loan-origination/packages/api/Containerfile` with the
   correct `python -m src.mcp_*` command).
7. K8s manifests for `pgvector`, `mcp-compliance`, `mcp-pipeline`,
   `mcp-decision`, `mcp-analytics`, `mcp-risk` in `k8s/system-a/`.
   Run `kubectl apply` and confirm health endpoints.
8. Wire MCP servers into `OpenClawInstance.spec.config."openclaw.json".plugins`
   (or to the `agent_invoke` fallback if Gate 2 fails).
9. Smoke-test a single MCP tool call from the OpenClawInstance
   gateway.

### Phase C — Persona content (multi-persona workspace)

10. Copy the five `SOUL.md` / `AGENT.md` / `USER.md` files into
    `agentic-intel-demo/demo-workspace/agents/`.
11. Author the workspace-level `AGENTS.md` for path-based routing.
12. Apply / re-apply the OpenClawInstance; verify each persona
    responds to its routed path.

### Phase D — Scenario plumbing

13. Add `mortgage_officer` to `catalog/scenarios.yaml` and
    `catalog/tasks.yaml`. Update schemas. Pass `make validate-templates`.
14. Author `agents/scenarios/mortgage-officer/{flow.md, run.sh,
    task-brief.md}`. Update `agents/orchestrator.md` and
    `agents/context-map.md`.
15. Add the fifth scenario card to `web-demo/index.html` and the
    matching `liveScenario` to `web-demo/app.js`.
16. End-to-end smoke: click the card → POST /api/offload → tool
    calls land on MCP servers → response renders.

### Phase E — Compliance KB ingestion

17. Mount or copy `data/compliance-kb/` into pgvector at boot via a
    one-shot init Job.
18. Verify `kb_search` against pgvector returns ranked results.
19. Tier-priority enforcement (federal > agency > internal) in the
    MCP server.

### Phase F — Provider profile aliasing

20. Add `minimax` LiteLLM alias to `config/model-routing/litellm-config.yaml`
    and the deployed copy in `k8s/system-a/litellm.yaml`.
21. Document booth-day provider switch ("flip
    `agents.defaults.model` to `litellm/sambanova`").

### Phase G — Tier 2 end-to-end + booth dry-run

22. Full flow on Tier 2: open the web demo → mortgage card → run
    scenario → see Telegram operator menu update → see audit chain
    write → see offload to System B (if `mcp-risk` is on B) →
    success.
23. Update the demo-checklist runbook with mortgage-specific
    pre-flight items.

## Risks specific to this integration

1. **Gate 1 fails (multi-persona unsupported).** Fallback adds
   complexity but is workable. ETA risk: +1 week if a controller PR
   is needed.
2. **Gate 2 fails (MCP plugins unsupported).** Fallback via
   `agent_invoke` task type is straightforward but loses the "MCP
   plugins" talk-track point. ETA risk: +0.5 week.
3. **Scenario schema enum is closed.** Adding `loan_origination`
   task family requires schema edit; ensure the schema PR lands
   before content PRs.
4. **Workspace volume size.** Default 10Gi may be tight if compliance
   KB embeddings live there (they should live in pgvector instead —
   already the design).
5. **Telegram bot conflicts.** The booth `OpenClawInstance` registers
   one Telegram bot; multi-persona doesn't multiply bots. The
   `session-agent` account behavior under multi-persona load needs
   verification.
6. **Web-demo proxy path.** The `liveScenario` payload shape today is
   `{task_type: 'shell', payload: {scenario, timeout_seconds}}`. For
   our scenario we likely want `task_type: 'agent_invoke'` (or
   `'mortgage_invoke'`) to flow through the agent rather than a
   shell script. Confirm the worker accepts the new shape.
7. **Booth-day provider lock-in.** Bedrock Sonnet is the booth
   default. If Bedrock access is a surprise dependency, fallback path
   is `litellm/fast` (vLLM Qwen3-4B, lower quality) or pre-paid
   SambaNova credits.

## Where prior planning docs still apply

- `00-overview.md`, `01-hardware-story.md`, `03-use-case-mortgage-officer.md`,
  `05-scalability-benchmarks.md` → still describe the **value
  proposition** and benchmarks. Update to reflect the
  System-A-density + System-B-offload story.
- `02-openclaw-framework.md` → still describes OpenCLAW; add a note
  pointing here for the operator-driven path.
- `04-architecture.md` → **partially superseded** by this doc. Keep
  it as the single-box dev architecture; this doc is the
  booth-deployment architecture.
- `06-roadmap.md` → still useful as a phase plan, but Phase 4-5 are
  rewritten by Phase A–G above.
- `07-kubernetes-deployment.md` → **superseded**. The agentic-intel-demo
  K8s topology replaces our `kind`/`kubeadm` plan.
- `08-reuse-from-rh-ai-quickstart.md` → still accurate.
- `09-refactor-plan.md` → **partially superseded**. Tracks 1, 2, 3
  remain valid as work to do *inside multi-agent-loan-origination*;
  Tracks 4 (Helm), 5 (Compose), 6 (UI), 7 (Fleet View) are
  reframed: 4 is replaced by `k8s/system-a/` patches in
  `agentic-intel-demo`; 5 stays useful for dev; 6 is dropped (booth
  UI is the demo's web-demo); 7 is reframed (Fleet View becomes
  whatever the demo's `scalability.html` already provides).
- `10-production-readiness.md` → still applies.
- `11-track1-runbook.md`, `12-local-test-guide.md` → still accurate
  for testing `multi-agent-loan-origination` in isolation. Tier 1
  bring-up of `agentic-intel-demo` is its own runbook
  (`docs/demo-setup.md` in that repo).

## Open questions to revisit

- Should `mcp-risk` move to System B for the offload-narrative point?
  Defer until Phase B is real.
- Do we want a `mortgage_audit` or `mortgage_intake` *secondary*
  scenario card alongside `mortgage_officer`? Defer until the first
  one is working.
- Does the workspace `MEMORY.md` participate in our multi-persona
  layout (one shared, or per-persona)? Defer to Phase C
  implementation.
- Is there a clean way to render the **Fleet View** density panel
  (which `web-demo/scalability.html` already implements) from
  mortgage-session metadata, so the existing density story shows
  borrower throughput? Likely yes — investigate when wiring web-demo.
