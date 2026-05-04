# OpenCLAW Workspace

OpenCLAW agentic-orchestration layer for the Computex demo. This directory replaces
the LangGraph agents previously living under `packages/api/src/agents/` (see
`/home/orelyehu/workspace/computex_demo/planning/09-refactor-plan.md`, Track 1).

## Status

**Track 1 complete.** All five personas are ported (SOUL.md / AGENT.md /
USER.md per agent). Three new MCP servers (`mcp-pipeline`,
`mcp-decision`, `mcp-analytics`) are scaffolded as skeletons with
correct tool signatures and stub bodies; the existing `mcp-risk` and
the public-tier subset of `mcp-compliance` are fully implemented.

**Track 2 (filling in stub MCP tool bodies)** is the next critical
milestone. Until those bodies are wired to the upstream service-layer
functions, authenticated personas will receive `_stub: true` responses
on most tool calls — by design. The agent SOUL.md instructions tell
the LLM to surface that gracefully, but the booth demo cannot ship
until Track 2 is done.

**Schema verification is still pending**: the workspace has not yet
been validated against `openclaw onboard`. Run that locally once IT
unblocks OpenCLAW; reconcile any field renames; document the verified
schema in this README before doing further porting work.

## Layout

```
openclaw-workspace/
├── README.md             this file
├── AGENTS.md             agent roster + routing rules (workspace-level)
├── TOOLS.md              tool registry (points at MCP servers from Track 2)
├── openclaw.json         gateway config: model, port, channels
├── agents.yaml           agent manifest (id, model, workspace path, bindings)
└── agents/
    └── public-assistant/
        ├── SOUL.md       persona, capabilities, rules, output format
        ├── AGENT.md      model + tools + session/inter-agent config
        └── USER.md       per-agent user context (role, scope)
```

All five persona directories now exist:

```
agents/
├── public-assistant/
├── borrower-assistant/
├── loan-officer-assistant/
├── underwriter-assistant/
└── ceo-assistant/
```

Each directory contains `SOUL.md`, `AGENT.md`, and `USER.md` following
the `shenhao-stu/openclaw-agents` community convention.

## File-format provenance

OpenCLAW's documented "injected prompt files" are `AGENTS.md`, `SOUL.md`, and
`TOOLS.md` at the workspace root. Multi-agent layout (per-agent subdirectories
with `SOUL.md` / `AGENT.md` / `USER.md`) follows the community pattern from
`shenhao-stu/openclaw-agents` and `mergisi/awesome-openclaw-agents`. The exact
schema OpenCLAW's runtime expects should be verified by running
`openclaw onboard` once and diffing against this layout. Until then, treat
this as a working scaffold, not a frozen contract.

## Source material ported

The Public Assistant SOUL.md is ported from:

- `config/agents/public-assistant.yaml` (system prompt, tool list, role ACLs)
- `packages/api/src/agents/public_assistant.py` (LangGraph wiring; minimal)
- `packages/api/src/agents/tools.py` (`product_info`, `affordability_calc`)

Tool *implementations* are not duplicated here. They remain in Python and will
be exposed to OpenCLAW via MCP servers in Track 2 (see `../planning/09-refactor-plan.md`).
For Track 1 verification, the Public Assistant calls a temporary MCP shim or
falls back to direct stub responses if MCP is not yet wired (documented in
`AGENT.md`).

## Running locally (target shape, not yet verified)

```bash
# Install OpenCLAW (Node 24 recommended)
npm install -g openclaw@latest

# From repo root
cd openclaw-workspace
openclaw gateway --port 18789 --workspace .

# Connect via WebChat at http://localhost:18789
```

The existing React UI (`packages/ui/`) is repointed at the gateway WebChat
endpoint as part of Track 6 of the refactor plan; until then, use OpenCLAW's
built-in chat surface for verification.

## Open verification items

- [ ] Run `openclaw onboard` against this workspace; reconcile any schema
      mismatches with the framework's actual expectations.
- [ ] Confirm OpenCLAW supports an OpenAI-compatible `LLM_BASE_URL` env override
      (we need this for local CPU LLM serving on Xeon 6+).
- [ ] Confirm OpenCLAW's session-history persistence handles long borrower
      conversations (50+ turns) without context drop. If not, store history
      in Postgres and pass on each turn.
- [ ] Confirm OpenCLAW emits a WebSocket event stream the existing UI can
      consume, or write a thin adapter (`token` / `tool_start` / `tool_end` /
      `done` framing per the upstream UI contract).
