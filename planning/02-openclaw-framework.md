# 02 — OpenCLAW Framework Profile

> Source of truth: https://github.com/openclaw/openclaw — verify details against the repo before committing demo code; the project is young and moving fast.

## What it is
OpenCLAW is a **local-first agentic AI framework** built around a **Gateway** (control plane) plus per-agent **workspaces** and **skills**. It is positioned as an end-user/operator product more than a developer SDK — agents are configured via markdown files rather than Python graphs.

- **Created by:** Peter Steinberger and community (originally for "Molty" the space-lobster assistant).
- **Runtime:** Node.js (≥22.14, recommends 24), TypeScript, pnpm workspaces.
- **Distribution:** npm packages, Docker images, source checkout.

## Configuration model (config-first)
Agents are defined by injected markdown files in a workspace:
- `AGENTS.md` — agent roster and routing.
- `SOUL.md` — persona / system prompt.
- `TOOLS.md` — tool inventory.
- Skills live under `~/.openclaw/workspace/skills/<skill>/SKILL.md` and are registered through **ClawHub** (the skill directory).

This is a notable contrast with LangChain/LangGraph (Python, code-first) or AutoGen (Python, multi-agent code). For a demo, this means **less code on stage**, more "watch a fleet light up from config."

## Channels (input surface)
25+ messaging channels supported out of the box: WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, Microsoft Teams, Matrix, Mattermost, IRC, Nostr, WeChat, QQ, WebChat, etc. For our demo: **WebChat** is the most controllable; Telegram or WhatsApp could add a "wow" moment for live booth interaction.

## Sandbox / runtime modes
- **Default:** main session runs on host with full tool access (single-user trust model).
- **`agents.defaults.sandbox.mode = "non-main"`:** non-main sessions run in sandboxes — Docker (default), SSH, or OpenShell backends.
- For our demo, sandboxing every borrower session is the right posture — and conveniently maps to "many isolated processes" which is exactly what 288 cores eat for breakfast.

## Multi-agent scaling model
Per project README: *"Route inbound channels/accounts/peers to isolated agents (workspaces + per-agent sessions)."* The Gateway is the routing layer; isolation boundary is the workspace + sandbox.

**Implications for our scale demo:**
- Each concurrent borrower = its own session, optionally its own sandboxed container.
- Specialist agents (RAG, KYC, Credit, Vision, Closing) can be either:
  - **Per-session subagents** (more isolation, more memory pressure), or
  - **Shared services** the orchestrator agent calls via tools/MCP (more efficient at scale).
- Recommendation: shared specialist agents behind MCP tools, **per-session orchestrator** only. This is what gives us the "100 concurrent borrowers on one socket" number.

## LLM backend support
Documented: OpenAI / ChatGPT / Codex subscriptions. Generic guidance: "a current flagship model from the provider you trust." Need to verify support for:
- **Local OpenAI-compatible endpoints** (vLLM-CPU, llama.cpp server, Ollama, OpenVINO Model Server) — critical for the on-prem story.
- Model failover / per-agent model selection.

If OpenCLAW doesn't yet support arbitrary OpenAI-compatible base URLs natively, we'll need a thin adapter or a config patch. **Track as risk #1.**

## Risks / unknowns to verify before commit
1. ❓ Local LLM endpoint support — needed for the "runs entirely on the Xeon box" narrative.
2. ❓ Docker-per-session footprint at 100+ sessions — measure cold-start and steady-state RAM/CPU per sandbox.
3. ❓ MCP server support maturity — the demo leans heavily on MCP for Credit/KYC/DocuSign tool calls.
4. ❓ Observability hooks — we'll want per-agent traces to drive the visualization on the booth screen.
5. ❓ License posture and any Intel co-marketing constraints around an external framework.
