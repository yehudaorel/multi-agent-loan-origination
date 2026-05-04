# 00 — Demo Overview

## One-liner
An **Autonomous Mortgage Officer** built on the **OpenCLAW** agentic framework, running entirely on a single Intel **Xeon 6+ "Clearwater Forest"** socket — demonstrating that latest-gen E-core density makes large agent fleets and CPU-side RAG/inference economically viable on-prem for regulated FSI workloads.

## Why this demo
- **Vertical relevance:** FSI is one of the most-requested verticals for agentic AI. Mortgage origination is a tangible, multi-step, multi-system flow that audiences immediately understand.
- **Hardware story:** Clearwater Forest's defining trait is **288 Darkmont E-cores per socket** with ~17% IPC uplift over Sierra Forest, DDR5-8000, and >1 GB of last-level cache. That maps cleanly onto a workload of **many concurrent, mostly-stateless agent tasks** rather than a single monolithic GPU job.
- **Framework relevance:** OpenCLAW is config-first (SOUL.md / TOOLS.md / AGENTS.md), local-first, sandboxed per agent — a natural fit to spin up dozens-to-hundreds of specialist agents on a dense E-core socket.

## Target audience
- Computex floor visitors (mixed: enterprise architects, FSI ISVs, press, channel).
- Secondary: Intel field/AE, partner ISVs evaluating CPU-side agentic stacks.

## Success criteria
1. **Visceral demo moment:** a borrower goes from "Can I get a $500k loan?" to a signed DocuSign envelope in **<5 minutes**, on stage.
2. **Scale headline:** show **N concurrent borrower sessions** (target: 50–100+) on one Xeon 6+ socket without queueing — a number that's hard to reach without 288 E-cores.
3. **Comparative chart:** side-by-side throughput / sessions-per-socket vs Sierra Forest (or other baseline). Aim for ~2× the prior-gen number, consistent with Intel's own claims.
4. **Trust story:** entire flow runs on-prem; no borrower PII leaves the box. Resonates with FSI compliance buyers.

## Non-goals
- Not a production loan-origination system. Synthetic data only.
- Not a GPU vs CPU benchmark in absolute terms — the story is **density and TCO for agentic workloads on CPU**, not "CPU beats GPU at LLM inference."
- Not a deep OpenCLAW tutorial. The framework is the vehicle; the star is the workload + the silicon.
