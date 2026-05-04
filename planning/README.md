# Computex Demo — Planning Folder

**Demo concept:** Agentic AI showcase on Intel Xeon 6+ "Clearwater Forest" using the **OpenCLAW** agentic framework. Vertical: **FSI / Mortgage origination**.

**Tagline (working):** *"From days to minutes — an autonomous mortgage officer running a fleet of agents on a single Xeon 6+ socket."*

## Documents

1. [00-overview.md](00-overview.md) — Demo goals, audience, success criteria
2. [01-hardware-story.md](01-hardware-story.md) — Clearwater Forest / Xeon 6+ hardware angle and why it matters for agentic workloads
3. [02-openclaw-framework.md](02-openclaw-framework.md) — OpenCLAW framework profile, runtime, scaling model
4. [03-use-case-mortgage-officer.md](03-use-case-mortgage-officer.md) — Autonomous Mortgage Officer scenario, agents, flows
5. [04-architecture.md](04-architecture.md) — Proposed end-to-end architecture
6. [05-scalability-benchmarks.md](05-scalability-benchmarks.md) — What we measure to prove the Xeon 6+ E-core density story
7. [06-roadmap.md](06-roadmap.md) — Phased build plan
8. [07-kubernetes-deployment.md](07-kubernetes-deployment.md) — Vanilla K8s topology (stretch goal)
9. [08-reuse-from-rh-ai-quickstart.md](08-reuse-from-rh-ai-quickstart.md) — What we lift, modify, and drop from the upstream loan-origination repo
10. [09-refactor-plan.md](09-refactor-plan.md) — Concrete refactor plan for the cloned repo (LangGraph → OpenCLAW, vanilla K8s, 7 tracks)
11. [10-production-readiness.md](10-production-readiness.md) — Scale-up, scale-out, reliability, and security gaps
12. [11-track1-runbook.md](11-track1-runbook.md) — Step-by-step to verify the Public Assistant + mcp-compliance end-to-end
13. [12-local-test-guide.md](12-local-test-guide.md) — Home-Linux end-to-end testing path before K8s
14. [13-integration-with-agentic-intel-demo.md](13-integration-with-agentic-intel-demo.md) — How our work plugs into the booth-facing two-system K8s demo (supersedes parts of 04 / 07 / 09)
15. [14-home-validation-runbook.md](14-home-validation-runbook.md) — Single-Ubuntu-box validation pass with basic OpenCLAW
16. [99-references.md](99-references.md) — Source links

## Open questions (track here)

- [ ] Target Xeon 6+ SKU available for demo? (288c top-bin vs mid-bin)
- [ ] Comparison baseline: Sierra Forest 144c? AMD Bergamo? Or GPU node?
- [ ] LLM backend: local CPU inference (llama.cpp / OpenVINO / vLLM-CPU) vs hosted? Affects density story.
- [ ] OpenCLAW sandbox mode: Docker-per-agent at hundreds-of-agents scale — feasible on a single socket?
- [ ] Live audience interaction or pre-recorded loan flow?
- [ ] Compliance/PII story for live demo (synthetic borrowers required).
- [ ] **K8s stretch goal**: how does OpenCLAW's per-session sandbox map to pods? (See [07-kubernetes-deployment.md](07-kubernetes-deployment.md).)
