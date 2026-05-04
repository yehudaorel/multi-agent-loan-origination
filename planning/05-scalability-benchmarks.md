# 05 — Scalability & Benchmarks

The number on the booth wall comes from this document. Everything here is what we measure and how.

## Headline metrics (the slides)

1. **Concurrent borrower sessions sustained per socket** at p95 step latency ≤ target.
2. **End-to-end loan-flow completions per minute** (whole-flow throughput).
3. **Perf/Watt** for the agentic workload (sessions/W) — Intel's own claim is +55% perf/W vs Sierra Forest at 6780E baseline; we want to land in that neighborhood.
4. **Cost per concurrent agent** — derived chart, not measured. Use list price / sessions sustained.

## Secondary metrics (the operator screen)
- p50 / p95 / p99 latency per step (RAG, Vision, Credit, KYC, Underwrite, Closing).
- Tokens/sec aggregate across the shared LLM pool.
- CPU utilization heatmap across 288 cores.
- DDR bandwidth (proxy for whether we're memory-bound).
- LLC hit rate.
- Per-session memory footprint (sandbox overhead).
- Sandbox cold-start latency.

## Workloads to define

### A. Steady-state concurrency sweep
Open N parallel synthetic borrowers (5, 10, 25, 50, 75, 100, 150, ...) doing the full flow on a loop. Find the largest N where p95 step latency ≤ threshold (e.g., 3 s for non-LLM steps, 8 s for LLM steps).

### B. Burst test
N=0 → spike to target N over 30 s. Measure time-to-stable and any failed sessions.

### C. Mixed branch load
Mix borrower personas so all branches (decline, watchlist hit, ID mismatch, approve) are exercised in proportion. Avoids the all-happy-path artifact.

### D. Comparison runs (baseline)
Same workload, same software, on:
- Sierra Forest 144c (primary baseline). 
- Optionally: Granite Rapids P-core SKU (informative, not for the headline slide).

Record everything; replay as a side-by-side video on the booth comparison toggle.

## Tooling
- **Load gen:** custom async Python or k6 driving the WebChat WS endpoint with scripted borrower transcripts.
- **Telemetry:** OpenTelemetry in every component → local OTel collector → Prometheus + Tempo → Grafana.
- **Hardware counters:** `perf`, `pcm`, Intel PMU; pull DDR BW and LLC stats for the heatmap.
- **Power:** RAPL via `turbostat` for the perf/W slide.

## Targets to commit to (placeholders — refine after first run)
- ≥ **80 concurrent borrowers** sustained on Xeon 6+ 288c at p95 ≤ 8 s end-to-end LLM step.
- ≥ **2.0×** sessions-sustained vs Sierra Forest 6780E 144c on identical workload.
- ≥ **1.5×** perf/W vs the same baseline.

If we don't hit these in the first measurement pass, the right move is to tune (LLM serving config, sandbox backend, MCP worker pools) before moving the targets.

## Things that will trip us up (pre-mortem)
- **Sandbox overhead at 100+ Docker containers.** May force a switch to OpenShell sandbox or no-sandbox-for-demo. Quantify early.
- **Single LLM pool becomes the bottleneck.** Need vLLM-CPU continuous batching tuned, or split into 2–4 pools pinned to NUMA-ish core groups.
- **NUMA / sub-NUMA clustering on 288c.** A 288-core socket isn't flat; pinning matters. Plan a tuning day.
- **Memory pressure from per-session orchestrator state.** Keep orchestrators lean; push heavy state to shared services.
- **Vision model latency dominating end-to-end time.** Mitigate with a small VLM and pre-warmed pool.
