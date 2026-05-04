# 07 — Kubernetes Deployment (Stretch Goal)

**Status:** stretch goal. The booth headline stays "one Xeon 6+ socket, N concurrent borrowers." K8s is a parallel deliverable that demonstrates the **same workload, same images, scaled horizontally** across multiple Xeon 6+ nodes — useful for FSI buyers who will only deploy on their own clusters.

**Target distro:** **Vanilla upstream Kubernetes** (no OpenShift / Tiber assumptions). Anything we build should run on `kubeadm`, `kind`, k3s, or a managed cluster without modification.

## Design constraints this implies

1. **Every component containerized from day 1** — even in the single-box path. No host-only services, no "dev runs differently from prod" gaps. The single-box demo runs the same images via Docker Compose; the K8s demo runs them as Deployments.
2. **No OpenShift-only primitives.** No `Route`, no `SecurityContextConstraints`, no `ImageStream`. Use `Ingress`, standard `PodSecurityAdmission`, plain registries.
3. **No GPU-only paths.** All inference paths must work CPU-only. CPU node selectors, no nvidia device plugin assumed.
4. **Stateless where possible.** Specialist agents and MCP servers stateless and horizontally scalable. State pushed to Postgres/pgvector and an object store.

## Topology sketch

```
┌─────────────────────── Vanilla K8s cluster ───────────────────────┐
│                                                                   │
│  Namespace: openclaw-demo                                         │
│                                                                   │
│  ┌─ Ingress (NGINX) ──────────────────────────────────────────┐   │
│  │  /chat  → openclaw-gateway   /ui → fleet-view              │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                       │
│  ┌──────────────────────┐ │ ┌──────────────────────────────────┐  │
│  │ openclaw-gateway     │◄┘ │ fleet-view (React)               │  │
│  │ Deployment, HPA      │   │ Deployment                       │  │
│  └──────┬───────────────┘   └──────────────────────────────────┘  │
│         │                                                         │
│         │ MCP (HTTP streaming)                                    │
│         ▼                                                         │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐   │
│  │ rag-mcp          │ │ vision-mcp       │ │ credit-mcp       │   │
│  │ Deployment, HPA  │ │ Deployment, HPA  │ │ Deployment, HPA  │   │
│  └─────────┬────────┘ └────────┬─────────┘ └────────┬─────────┘   │
│            │                   │                    │              │
│  ┌─────────▼────────┐ ┌────────▼─────────┐ ┌────────▼─────────┐   │
│  │ kyc-mcp          │ │ docusign-mcp     │ │ underwriter      │   │
│  │ Deployment       │ │ Deployment       │ │ Deployment       │   │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ llm-pool (vLLM-CPU)                                      │     │
│  │ Deployment, large CPU+memory request, OpenAI-compat svc  │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐    │
│  │ postgres    │  │ minio       │  │ otel-collector +        │    │
│  │ +pgvector   │  │ (objects)   │  │ prometheus + tempo +    │    │
│  │ StatefulSet │  │ StatefulSet │  │ grafana                 │    │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘    │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## Sandbox model on K8s

OpenCLAW's per-session Docker sandbox does **not** translate cleanly into a standard K8s pod model — pods aren't typically created per inbound user. Two viable approaches:

- **A. Pool of sandbox-runner pods.** Pre-warmed pods that accept session assignments from the Gateway via a queue. Bounded blast radius, predictable resources. **Recommended.**
- **B. Per-session pod via a controller.** Gateway calls the K8s API to spin a Pod per session. More faithful to OpenCLAW's design, but Pod cold-start and API-server load become real at booth scale.
- **C. No-sandbox mode.** Single Gateway pod runs all sessions in-process. Simplest, weakest isolation. Acceptable for a stretch-goal demo where we control the borrower scripts.

Pick (A) for the stretch demo unless OpenCLAW upstream lands a first-class K8s session backend by then.

## Packaging

- **Helm chart** (`deploy/helm/computex-demo/`) — single chart, values.yaml toggles for `singleNode: true|false`, replica counts per specialist, LLM pool sizing, and CPU node-selector labels.
- **Container images** built once, pushed to a local registry (`ttl.sh` or in-cluster registry for booth resilience).
- **Resource requests** set conservatively so the chart works on a small dev cluster (kind / k3s on a laptop) and scales up on Xeon 6+ nodes.

## What the K8s view adds to the booth narrative

- **Same images, two topologies:** "this is the dev box, this is the cluster — no rewrite."
- **Horizontal scale:** flip a Helm value, watch HPAs ramp specialist replicas under burst load.
- **Cluster of Xeon 6+ nodes:** if hardware allows, show the same workload on a 2–4 node Xeon 6+ cluster with aggregated session counts.
- **FSI buyer relevance:** "you can run this on your existing K8s — vanilla, no vendor distro required."

## Concrete stretch-goal deliverables

- [ ] Dockerfiles for every component (Gateway, each MCP, LLM pool, fleet-view UI).
- [ ] Single Helm chart with the topology above.
- [ ] `kind` profile for laptop validation; documented `kubeadm`-on-Xeon-6+ profile for the real run.
- [ ] HPA on Gateway, RAG, Vision, Credit, KYC.
- [ ] Smoke test job that runs one synthetic borrower end-to-end against the cluster.
- [ ] Load-gen run reproduced on K8s; numbers captured for a side-by-side single-box vs cluster slide.

## Risks specific to the K8s path

- **Sandbox-on-K8s gap in OpenCLAW** (covered above). Mitigation: pooled runner pods.
- **Pod cold-start latency** if we go per-session. Mitigation: pool + warm replicas.
- **CPU pinning / NUMA awareness** is harder on K8s than on a single host. May leave perf on the floor vs the bare-metal run — that's expected; the K8s number doesn't have to beat the single-box number, only show that the workload scales.
- **Networking overhead** (CNI, service mesh if any) adds latency to MCP calls. Skip a service mesh for the demo unless we already need mTLS for the FSI talk track.
