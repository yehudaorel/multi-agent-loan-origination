# 01 — Hardware Story: Xeon 6+ "Clearwater Forest"

## Headline specs (per Intel MWC 2026 announcement)
- **Up to 288 "Darkmont" E-cores** on a single socket (12 compute tiles × 24 E-cores).
- **Process / packaging:** Intel 18A compute tiles, Intel 3 active base tiles, Intel 7 I/O tiles; Foveros Direct 3D + EMIB 2.5D.
- **IPC:** ~17% gain over Sierra Forest's E-cores; wider front end, larger OoO window, more execution ports.
- **Cache:** ~4 MB L2 per 4-core cluster; 48 MB L3 per compute tile; 192 MB LLC per base tile; **>1 GB combined LLC** (~1,152 MB) per package.
- **Memory:** 12 channels, **DDR5-8000**, ~1.9× the bandwidth of Sierra Forest's DDR5-6400.
- **I/O:** 96 PCIe 5.0 lanes, 64 CXL 2.0 lanes, 192 UPI lanes.
- **Built-in accelerators:** 4× QAT, 4× DLB, 4× DSA, 4× IAA per CPU.
- **Perf vs Sierra Forest 6780E (144c, 330W):** Intel claims ~2× cores, ~+113% perf, ~+55% perf/W at 450 W TDP.
- **Launch:** H1 2026, branded **Xeon 6+** (not Xeon 7).

## Why this matters for agentic AI

Agentic workloads are **not** a single hot inference loop. A single user request fans out into:

- LLM token generation (the hot path).
- Many short, **bursty, mostly-IO-bound** tool calls (MCP servers, REST APIs, DB lookups, vector search, OCR, doc parsing).
- Sandboxed agent processes (containers, subprocesses) with their own runtime overhead.
- Audit/observability sidecars per session.

This profile maps poorly to "one giant GPU" and **very well** to a dense pool of latency-good cores with abundant memory bandwidth and integrated accelerators.

### The four sub-stories we can tell
1. **Density per socket — agents-as-a-fleet.** With 288 cores, we can dedicate cores per agent role and still run 50–100+ concurrent borrower sessions on one socket. Headline number for the booth.
2. **CPU-side RAG and embeddings.** pgvector / FAISS lookups, embedding generation, and re-ranking are well within reach for E-cores, especially with **IAA** for compression/decompression of vector payloads and **DSA** for memory movement.
3. **DDR5-8000 + >1 GB LLC.** Big enough working set to keep KV-cache, hot vector indices, and the agent registry in cache/near-memory — fewer trips to disk, more sessions per box.
4. **On-prem TCO + compliance.** FSI buyers can't ship borrower PII to a public GPU cloud. A single-socket Xeon 6+ box that runs the full agentic stack hits a price point and an audit boundary GPUs can't match.

## What we should *not* claim
- Don't claim CPU beats GPU on raw LLM tokens/sec at large model sizes — it doesn't.
- Don't claim Clearwater Forest replaces Granite Rapids / Diamond Rapids for AMX-heavy training/inference. Different silicon, different job.
- The story is **density, concurrency, TCO, and on-prem fit for agentic orchestration** — not peak FLOPS.

## Comparative baselines we could use
- **Sierra Forest (Xeon 6 6780E, 144c)** — same family, prior gen. Easiest apples-to-apples. Likely the primary baseline.
- **Granite Rapids (P-core Xeon 6)** — interesting "P-core vs E-core for agents" angle; risks muddying the message.
- **AMD Bergamo / Turin Dense** — competitive, but politically sensitive on an Intel booth.
- **Single mid-range GPU node (L40S / H100)** — for the TCO/$ per concurrent agent slide, not for raw LLM perf.
