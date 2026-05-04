# 10 — Production Readiness, Scale-Up & Scale-Out

Companion to [09-refactor-plan.md](09-refactor-plan.md). The refactor plan is about *changing what the system is*; this doc is about *making it run reliably and scale* — work that's largely independent of OpenCLAW vs LangGraph.

The repo is already MVP-shaped (async throughout, Alembic migrations, 101 tests, Prometheus metrics, vanilla Postgres schema, CPU-only PyTorch in the Containerfile). The gaps below are what stand between "demo on a laptop" and "credibly deployable, horizontally scalable on a cluster."

## Definitions

- **Scale up** = more sessions / throughput on a single node, by tuning the workload to the silicon (NUMA, core pinning, batch sizes, pool sizes). The Xeon 6+ headline number is a scale-up number.
- **Scale out** = more nodes, more replicas, each fungible. The vanilla K8s story is a scale-out story.

The two are independent levers; both have to work for the demo to be credible.

---

## Section A — Scale-Up Readiness (single node, single socket)

### A1. LLM serving is the first bottleneck
Current default: `LLM_BASE_URL=http://host.docker.internal:1234/v1` (LM Studio / dev convenience). Single, unsharded.

**For scale-up:**
- Serve via **vLLM-CPU** with continuous batching, or **OpenVINO Model Server** with dynamic batching. One process per NUMA node is the right starting point on Clearwater (288 cores is not a flat topology).
- Pin worker threads to core groups; don't let the LLM process float across all 288 cores.
- Tune `max_num_seqs` / batch size to match target concurrent-session count. Underestimating wastes cores; overestimating tanks p99.
- KV-cache sizing: with >1 GB LLC and DDR5-8000, keep KV-cache resident; measure miss rate.
- Pre-warm: load weights and run a few synthetic completions before opening the front door.

### A2. Embedding pipeline
Current default: in-process sentence-transformers (CPU). Fine at low N, becomes a tail-latency contributor at high N because every RAG call does an embedding.

**For scale-up:**
- Move embeddings behind a small dedicated process (OpenVINO Model Server with a CPU embedding model) so the API workers don't compete with embedding compute for cores.
- Cache embeddings for repeated queries (small LRU); RAG workloads have surprising query repetition.

### A3. Postgres + pgvector
Default Docker image is fine for dev. For the booth scale demo:

- Pin Postgres to its own core group to keep it out of the LLM/agent contention zone.
- Tune `shared_buffers`, `effective_cache_size`, `work_mem`, `max_connections` to the actual hardware. Defaults assume a tiny VM.
- Use **PgBouncer in transaction-pooling mode** in front of Postgres so 100+ async API workers don't blow the connection limit.
- pgvector index choice: HNSW for the compliance KB; warm the index before the demo opens.

### A4. Session sandboxing overhead
OpenCLAW's per-session Docker sandbox is the most likely scale-up surprise. Per [02-openclaw-framework.md](02-openclaw-framework.md):

- Measure cold-start time and steady-state RAM/CPU per sandbox container before week 3.
- If unworkable at 100+, fall back to **pooled pre-warmed runner pods** (the K8s plan from [07-kubernetes-deployment.md](07-kubernetes-deployment.md) applied to single-box too), or **non-sandbox sessions** for the booth.

### A5. NUMA / sub-NUMA awareness
On a 288-core single socket, NUMA still matters within the package.

- Document the NUMA topology of the actual Clearwater box once we have access.
- Place LLM pool, MCP servers, and Postgres on distinct core groups.
- Use `numactl` (single-box) and `topologyManager` policy `single-numa-node` (K8s) for guaranteed pods.
- Plan one tuning day specifically for this; it's where the last 30% of perf hides.

### A6. Async ceilings
The codebase is async-throughout, which is the right starting point. Watch for:

- `asyncio` event-loop saturation at very high N — split workers across multiple uvicorn processes (one per core group), not one mega-loop.
- `httpx.AsyncClient` connection-pool limits. Default is small; raise per-host limits for MCP traffic.
- DB pool: `asyncpg` pool size has to match the expected in-flight request count, sized against PgBouncer.

### A7. Hardware-counter visibility
Already covered in [05-scalability-benchmarks.md](05-scalability-benchmarks.md) but worth restating: scale-up tuning without `perf`, `pcm`, RAPL, and DDR-bandwidth telemetry is guesswork. Wire these in week 1 of bench work.

---

## Section B — Scale-Out Readiness (horizontal across replicas / nodes)

The repo is *almost* horizontally scalable. The audit confirmed:

- API routes are stateless.
- LangGraph agents are per-session, but state lives in the checkpointer (pluggable Postgres).
- MCP risk server is stateless.
- Postgres is the canonical state store.

These remaining items are needed to unlock **N replicas behind a load balancer** without breakage:

### B1. Conversation checkpointer must be Postgres-backed in cluster mode
SQLite-on-disk is not shareable across pods. Switch the lifespan in `packages/api/src/main.py` to async-Postgres checkpointer when running in cluster mode (env-flag controlled). Already supported in code; just enforce it.

After the OpenCLAW swap, the equivalent is OpenCLAW's session store. Same rule: must be backed by Postgres (or another shared store), not local disk per pod.

### B2. WebSocket affinity
WS connections terminate at one pod. That's fine — the connection sticks, and any work that pod kicks off persists state to Postgres before responding. But:

- Ingress controller must support WebSockets (NGINX Ingress: `nginx.org/websocket-services` annotation; Traefik handles natively).
- Use `sessionAffinity: ClientIP` on the Service if we ever introduce reconnect-resume, so a borrower lands back on the same pod when possible.

### B3. MCP client per-process global state
`packages/api/src/agents/mcp_integration.py` keeps `_client` and `_tools` as process-global singletons, populated at lifespan startup. This is fine for replicas (each replica connects independently), but:

- Add liveness probe that fails the pod if the MCP client connection dies and can't reconnect; let K8s restart it instead of the pod silently degrading.
- For new MCP servers (Track 2 of the refactor), the OpenCLAW Gateway connects directly — same rule applies on the Gateway side.

### B4. MinIO / object storage
Single-node MinIO is fine for dev. For multi-replica:

- Cluster MinIO (4-node erasure coding) or use an external S3-compatible service.
- Documents must be retrievable from any replica → already the design; just make sure the bucket isn't a host volume.

### B5. Idempotency at API boundaries
Multi-replica means duplicate POSTs from retries are real. Decision creation, condition lifecycle transitions, and audit chain writes need idempotency keys.

- Add `Idempotency-Key` header support on POSTs that mutate state. Postgres unique constraint on `(idempotency_key, route)` is the simplest implementation.
- Audit chain (`prev_hash` linking in `decisions`) is naturally append-only; just guard against double-append on retry.

### B6. Background workers
Today there aren't really any. If we add async work (e.g., async credit pull retry, async docusign callback), do it via:

- A Kubernetes `Job` per task, or
- A small Celery/RQ worker pool against Redis.

Don't add background tasks to FastAPI's `BackgroundTasks` — they die when the pod is rescheduled, and they break horizontal scale-out.

### B7. Configuration & secrets
Today: env vars in `.env` and Helm `values.yaml`.

For prod-shaped:
- Helm `Secret` for credentials (Postgres password, S3 keys, LLM API keys if any). Don't put these in `values.yaml`.
- External secret store integration optional; for the demo, sealed Helm secrets are enough.
- Per-env values files: `values-dev.yaml`, `values-bench.yaml`, `values-booth.yaml`.

### B8. Pod resource requests/limits
Currently underspecified in the upstream Helm chart (most replicas don't have requests/limits). For honest HPA behavior:

- Set `requests.cpu` and `requests.memory` for every Deployment based on measured usage from the bench.
- Set `limits.cpu` only where you actually want to throttle; usually leave CPU unlimited and limit memory only.
- HPAs configured against CPU utilization on the stateless services (MCP servers, OpenCLAW Gateway, embedder).

### B9. PodDisruptionBudgets
For any service with >1 replica that the demo depends on (Postgres, OpenCLAW Gateway, LLM pool, each MCP), add a PDB with `minAvailable: 1` so node maintenance doesn't take the demo down.

---

## Section C — Reliability & Operability

### C1. Health probes
Containerfiles already have HTTP health checks. Helm Deployment specs need:

- `livenessProbe` — restart if process is wedged.
- `readinessProbe` — separate from liveness; gate traffic until startup is genuinely complete (warm models loaded, MCP connected, DB reachable).
- `startupProbe` for the LLM pool — model load can take tens of seconds; without a startup probe, the liveness probe will kill it before it's ready.

### C2. Graceful shutdown
- `terminationGracePeriodSeconds` set high enough for in-flight WebSocket conversations to complete a turn.
- API and Gateway should drain connections on SIGTERM; FastAPI's lifespan handles this if we don't fight it.
- LLM pool: drain in-flight requests before exit; don't `kill -9`.

### C3. Logging
Today: Python `logging` to plain text. For prod:

- Structured JSON logs (one library: `structlog` or stdlib JSON formatter). Required for usable ELK / Loki ingestion.
- Correlation: `session_id` (already exists) and `trace_id` (from OTel) on every log line.
- Drop the noisy SQL-debug logging in any non-debug build.

### C4. Observability (the prod story, not just the booth visual)
[09-refactor-plan.md](09-refactor-plan.md) Track 7 lays out OTel + Prometheus + Tempo + Grafana. For prod-readiness add:

- **Service-level objectives:** define SLOs for the obvious ones (chat first-token latency, end-to-end loan-step latency, error rate).
- **Alerting** on Prometheus rules; Alertmanager wired even if no one's on call — the dashboards will use the alert state.
- **Trace sampling** policy: 100% in dev/bench, 1–10% in booth (we don't need traces for every one of 100 concurrent synthetic borrowers).

### C5. Database operations
- Migrations gated by an init-container or a Helm pre-install/pre-upgrade hook running `alembic upgrade head`. Don't run migrations from app pods.
- Backups for the demo: probably not necessary, but document the command.
- Connection-string rotation: ensure secrets can be rotated without rebuilding images (env-from-secret pattern).

### C6. Container images
Already multi-stage; already CPU-only; already non-root. Still needed:

- **SBOM** generated on build (syft or similar). Useful talk-track point for FSI buyers.
- **Image signing** via cosign — optional for booth, expected for prod.
- **Vulnerability scanning** in CI (trivy/grype). Repo has no CI yet (Track addition).

### C7. CI/CD
Repo has commitlint, pre-commit, Makefile — no GitHub Actions. Add at minimum:

- Lint + unit tests on every PR.
- Container build + scan on main.
- Helm chart lint (`helm lint`, `kubeconform`) on chart changes.

---

## Section D — Security Posture

The booth doesn't need a hardened security posture, but the *talk track* for FSI buyers does. Covering both with light effort:

### D1. Secrets handling
- No credentials in `values.yaml`. Use `Secret` resources, mounted via `envFrom`.
- Demo never touches a real credit bureau or DocuSign — leave this in the talk track as "swappable for your KMS / vault."

### D2. Network policy
- Default-deny `NetworkPolicy` in the namespace, then explicit allows: UI→Ingress, Ingress→UI/API/Gateway, Gateway→MCP, API→DB, MCP→DB. This is a cheap, high-credibility prod-readiness signal for FSI.

### D3. Pod security
- `runAsNonRoot: true`, `readOnlyRootFilesystem: true` where it works (LLM pool may need writable cache dirs — explicit volumes for those).
- Drop all capabilities; add back individually only if needed (none should be needed for this stack).
- Restricted PodSecurity admission label on the namespace.

### D4. AuthN/AuthZ
- For the booth: `AUTH_DISABLED=true`. UI exposes a role dropdown.
- For the talk track: Keycloak-backed OIDC is *already wired*. Re-enabling for a buyer's eval is a values-file toggle.
- PII masking middleware (`middleware/pii.py`) stays in place even when auth is off — it's defensive depth.

### D5. Audit chain integrity
The repo already implements hash-chained append-only audit events. For prod:

- Move audit table to compliance schema with append-only triggers (the upstream already does this — verify after refactor).
- Periodic integrity verification job (recompute the chain hashes, compare to stored).

### D6. Compliance schema isolation
Already there: separate Postgres role + schema for HMDA tables, separate connection string. Strong differentiator on the FSI booth talk-track. **Preserve this through the refactor**; it's tempting to simplify away, but the talk-track loss isn't worth the schema cleanup gain.

---

## Section E — Stretch ideas (nice but not required)

These come up naturally when reading the audit. Park them, don't commit.

- **CXL memory tier** for vector indices: pgvector on a CXL-attached memory expander as part of the Clearwater story. Hardware-specific; only attempt if we have CXL silicon on the test box.
- **Intel accelerators integration:** QAT for TLS termination at the Ingress, IAA for vector compression in pgvector, DSA for memory movement in the LLM pool's KV-cache eviction. Each one adds a sub-bullet to the booth narrative; each is its own tuning project.
- **Multi-tenant namespacing:** isolate the demo by "lender" tenant, with one OpenCLAW workspace per tenant. Cute, but adds complexity for no booth payoff.
- **Speculative decoding** in the LLM pool: real perf win on CPU; worth the half-day if vLLM-CPU supports it cleanly by demo time.

---

## Quick checklist (paste-able)

**Scale-up:**
- [ ] LLM pool sized + NUMA-pinned
- [ ] Embedder split out from API workers
- [ ] PgBouncer in front of Postgres
- [ ] Session sandbox cost measured at N=10/50/100
- [ ] NUMA topology documented and pods/processes pinned
- [ ] `perf`/`pcm`/RAPL telemetry wired

**Scale-out:**
- [ ] Postgres-backed session store (no per-pod SQLite)
- [ ] WebSocket-aware Ingress controller
- [ ] MinIO clustered or external S3
- [ ] Idempotency keys on mutating POSTs
- [ ] Resource requests + HPA on every stateless service
- [ ] PodDisruptionBudgets on the demo-critical services

**Reliability:**
- [ ] Liveness / readiness / startup probes everywhere
- [ ] Graceful shutdown verified end-to-end
- [ ] Structured JSON logging with `session_id` + `trace_id`
- [ ] OTel traces + Prometheus metrics + Grafana SLOs
- [ ] Migrations run via Helm hook, not app pod

**Security:**
- [ ] No secrets in `values.yaml`
- [ ] Default-deny `NetworkPolicy` with explicit allows
- [ ] Restricted PodSecurity, runAsNonRoot, no caps
- [ ] Compliance schema isolation preserved through refactor
- [ ] Audit chain integrity verifier scheduled
