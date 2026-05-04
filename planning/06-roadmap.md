# 06 — Roadmap

Phased so we can demo *something* early and harden toward the booth date.

## Phase 0 — Validate assumptions (week 1)
- [ ] Stand up OpenCLAW locally; run hello-world agent on WebChat.
- [ ] Confirm OpenCLAW can target a **local OpenAI-compatible LLM endpoint** (vLLM-CPU or llama.cpp). If not, scope a config patch.
- [ ] Measure baseline overhead: 1 sandboxed session idle RAM/CPU.
- [ ] Decide LLM stack: vLLM-CPU vs llama.cpp vs OpenVINO Model Server. **Owner:**
- [ ] Decide vision model + serving (OpenVINO Qwen2-VL-2B?). **Owner:**
- [ ] Confirm hardware availability + access window. **Owner:**

**Exit criteria:** one borrower can complete a happy-path conversation end-to-end with mocked tools, on a developer laptop.

## Phase 1 — Vertical slice (week 2)
- [ ] All 8 agents wired in (Orchestrator + 7 specialists), each with a SOUL.md and TOOLS.md.
- [ ] Mock MCP servers: Credit, KYC, DocuSign, Fed-rate, Underwriting-KB.
- [ ] pgvector populated with synthetic underwriting docs.
- [ ] Audit log writing hash-chained events.
- [ ] Borrower personas (~10) scripted.
- [ ] Demo flow runs end-to-end <5 min on a single session, on a developer-class CPU.

**Exit criteria:** the on-stage narrative works on dev hardware, single user.

## Phase 2 — Concurrency + observability (week 3)
- [ ] Specialists moved behind streaming-HTTP MCP and pooled.
- [ ] Shared LLM pool (continuous batching) tuned.
- [ ] Load generator producing N synthetic borrowers.
- [ ] OTel + Grafana wiring; Fleet View prototype.
- [ ] First sweep on Sierra Forest baseline: find sustained-N.

**Exit criteria:** can run ≥ 25 concurrent borrowers on dev/baseline hardware with stable latency.

## Phase 3 — Clearwater Forest tuning (week 4)
- [ ] Move workload to Xeon 6+ system.
- [ ] NUMA / sub-NUMA pinning; LLM pool sharding by core group.
- [ ] DSA / IAA / QAT integration where it actually helps (vector ops, compression, crypto). Skip if marginal.
- [ ] Power capture (RAPL/turbostat).
- [ ] Final concurrency sweep + comparison capture vs Sierra Forest.

**Exit criteria:** ≥ 80 concurrent borrowers sustained on Xeon 6+ at p95 target. Comparison numbers locked.

## Phase 4 — Booth polish (week 5)
- [ ] Final Fleet View visual.
- [ ] Borrower / Operator / Comparison views switchable from a single laptop.
- [ ] Failure-mode scripted demos (decline path, watchlist hit, ID mismatch).
- [ ] Talk track + 30-second / 2-minute / 5-minute versions of the pitch.
- [ ] Dry runs with floor staff.
- [ ] Backup recording in case of live failure.

**Exit criteria:** two staff can run the demo cold without a developer present.

## Phase 5 — Kubernetes (stretch goal)
Only attempt if Phase 0–4 are on-track. Detailed design in [07-kubernetes-deployment.md](07-kubernetes-deployment.md).

- [ ] Dockerfiles + local registry for every component (already an implicit dep of single-box if we containerize from day 1 — recommended).
- [ ] Single Helm chart, vanilla upstream K8s only (no OpenShift primitives, no GPU device plugin assumptions).
- [ ] Pooled sandbox-runner pods to bridge OpenCLAW's per-session sandbox to a K8s pod model.
- [ ] HPAs on Gateway and stateless specialists.
- [ ] `kind`-on-laptop profile for dev; `kubeadm`-on-Xeon-6+ profile for the booth-side run.
- [ ] Reproduce the concurrency sweep on a 2–4 node Xeon 6+ cluster; capture single-box vs cluster comparison numbers.

**Exit criteria:** same images, same demo flow, deployable to a vanilla K8s cluster via `helm install`. Cluster run does not need to beat the single-box number — only show horizontal scaling works.

## Risks worth tracking continuously
1. OpenCLAW maturity for local LLM endpoints + MCP at scale (Phase 0/1).
2. Sandbox overhead at high N (Phase 2).
3. Hardware access window — Clearwater Forest systems are scarce in early 2026 (Phase 3).
4. Demo fragility — live tool calls fail under booth Wi-Fi. Mitigation: every external service is mocked locally; the only network the demo needs is in-box.
5. Compliance optics — even with synthetic data, anything that *looks* like real PII on a public screen is a problem. Use obviously fake names/SSNs.
6. **K8s scope creep** (Phase 5). Easy to spend the final week on cluster polish instead of demo polish. Hard rule: K8s only ships if the single-box headline is already locked.
