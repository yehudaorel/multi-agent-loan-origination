# 04 — Proposed Architecture

## Layered view

```
                ┌──────────────────────────────────────────────────────────┐
                │  Booth UI                                                 │
                │  - WebChat (borrower view)                                │
                │  - Fleet View (operator view: agents, traffic, metrics)  │
                └───────────────────────────┬──────────────────────────────┘
                                            │  HTTPS / WebSocket
                ┌───────────────────────────▼──────────────────────────────┐
                │  OpenCLAW Gateway                                         │
                │  - Channel routing (WebChat, Telegram)                    │
                │  - Per-session orchestrator agents (sandboxed)            │
                │  - Skill / tool registry                                  │
                └─────┬───────────────┬──────────────────┬─────────────────┘
                      │ MCP           │ MCP              │ MCP
       ┌──────────────▼──┐  ┌─────────▼────────┐  ┌──────▼────────┐
       │ RAG / Policy    │  │ Vision           │  │ Credit / KYC  │
       │ (pgvector +     │  │ (local VLM via   │  │ (mock         │
       │ embedder)       │  │ OpenVINO)        │  │ Experian/     │
       │                 │  │                  │  │ Watchlist)    │
       └──────┬──────────┘  └────────┬─────────┘  └──────┬────────┘
              │                      │                    │
              └──────────────┬───────┴────────────────────┘
                             │
                ┌────────────▼─────────────┐     ┌──────────────────┐
                │ Underwriter (decision)   │     │ DocuSign (mock)  │
                └────────────┬─────────────┘     └────────┬─────────┘
                             │                            │
                             └─────────────┬──────────────┘
                                           │
                                ┌──────────▼──────────┐
                                │ Audit / Event Log   │
                                │ (hash-chained,      │
                                │ append-only)        │
                                └─────────────────────┘
```

All boxes run on **one Xeon 6+ Clearwater Forest socket** for the headline single-box demo. The same components are designed to deploy on **vanilla upstream Kubernetes** as a stretch goal — see [07-kubernetes-deployment.md](07-kubernetes-deployment.md). Practically this means: every component is containerized, no host-only services, and no OpenShift- or GPU-specific primitives.

## Component choices (proposed, to validate)

| Layer | Choice | Rationale | Alt |
|---|---|---|---|
| Agent framework | **OpenCLAW** | Per spec / user request | n/a |
| LLM serving (text) | **vLLM-CPU** or **llama.cpp** behind OpenAI-compatible endpoint | Local, on-prem, OpenAI-compatible URL → drops into OpenCLAW cleanly | OpenVINO Model Server (GenAI) |
| Default model | **Qwen2.5-7B-Instruct** or **Llama-3.1-8B-Instruct** (4-bit) | Small enough for CPU concurrency; strong tool-use | Mistral-Small, Phi-4 |
| Vision model | **Qwen2-VL-2B** via OpenVINO | CPU-friendly, good doc/ID extraction | InternVL2-2B |
| Embeddings | **bge-small-en-v1.5** via OpenVINO | Fast on CPU, fine for KB scale | e5-small |
| Vector store | **pgvector** | Same DB as audit log, simple ops | qdrant |
| Audit DB | **PostgreSQL** | Already there for pgvector | sqlite for booth |
| MCP runtime | **Stateless streaming-HTTP MCP servers** | Scales horizontally on the same socket | stdio MCP |
| Sandbox | **Docker** (OpenCLAW default) for non-main sessions | Aligns with framework | OpenShell for lighter footprint at high N |
| Observability | **OpenTelemetry → local Tempo/Grafana** for the Fleet View | Lets us drive booth visuals from real spans | LangSmith (cloud — avoid for on-prem story) |

## Concurrency model

- **N borrower sessions** = N orchestrator agents, each in its own OpenCLAW sandbox.
- **Specialist agents are shared:** one process per specialist, each fronted by an MCP server, scaled with worker pools sized to E-core count.
- LLM serving is a **single shared inference pool** (vLLM-CPU continuous batching) — critical: do NOT run one LLM process per session.
- Embedding + vector search shared.
- Audit/event sink shared, single writer.

This is the architecture that turns "lots of cores" into "lots of concurrent borrowers" instead of "lots of idle cores waiting on one bottleneck."

## What goes on the booth screen
- **Borrower pane:** the WebChat conversation — for the audience-facing narrative.
- **Fleet pane:** live grid of N session tiles, each lighting up by current step (RAG → Vision → Credit → KYC → Closing).
- **Telemetry strip:** active sessions count, p50/p95 step latency, CPU utilization across all 288 cores (heatmap), DDR bandwidth, LLC hit rate.
- **Comparison toggle:** flip between "Xeon 6+ 288c" and the recorded "Sierra Forest 144c" baseline run.
