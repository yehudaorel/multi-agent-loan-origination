# 03 — Use Case: Autonomous Mortgage Officer

## The promise
Transform mortgage origination from a **passive chat interface** into a **secure, end-to-end legal and financial execution engine**. Loan-to-close target: **days → minutes**.

Inspired by [rh-ai-quickstart/multi-agent-loan-origination](https://github.com/rh-ai-quickstart/multi-agent-loan-origination), but reframed to run on OpenCLAW + Xeon 6+, and tuned for a booth demo rather than a deployable product.

## Borrower-facing flow (the narrative on stage)
1. **Open WebChat (or Telegram).** "Hi, I'd like to see if I qualify for a $500k mortgage."
2. **Intake & policy lookup.** Agent pulls Underwriting Guidelines + current Fed rate and computes today's allowable DTI for the requested product. (RAG layer.)
3. **ID + paystub capture.** Camera/upload prompt; vision agent extracts and verifies. (Vision layer.)
4. **Credit pull.** MCP tool call to a (mocked) Experian/Equifax endpoint — real-time score.
5. **KYC / AML check.** MCP tool call to a (mocked) Global Watchlist database.
6. **Decision + closing.** Agent renders a term sheet, then calls a (mocked) DocuSign MCP tool to issue an envelope. Borrower signs on the same screen.
7. **Audit trail.** Hash-chained event log shown live on a side panel.

Total stage time target: **<5 minutes**, with all agent activity visualized on a "fleet view" panel.

## Agent roster

| Agent | Role | Backed by |
|---|---|---|
| **Orchestrator** | Per-session conversation lead, plans next step | OpenCLAW main agent, SOUL.md driven |
| **RAG / Policy** | Underwriting guidelines, rate feeds, product catalog | pgvector + embedding model, MCP tool |
| **Vision** | ID + paystub extraction & verification | Local VLM (e.g., Qwen2-VL / similar), MCP tool |
| **Credit Bureau** | Pull score (mocked Experian/Equifax) | MCP tool → mock service |
| **KYC / AML** | Watchlist screening | MCP tool → mock service |
| **Underwriter** | DTI calc, eligibility, risk flags | Deterministic Python + LLM rationale |
| **Closing / DocuSign** | Generate envelope, send for signature | MCP tool → mock DocuSign |
| **Audit** | Append hash-chained event log, redact PII | Sidecar service |

For the **scale demo**, replicate the **Orchestrator** per session. Specialists are shared services behind MCP — this is what lets one socket carry 100+ concurrent borrowers.

## Data model (synthetic only)
- **Borrower personas:** ~10 hand-crafted synthetic profiles (good credit, marginal, declined-for-DTI, watchlist hit, ID mismatch, etc.) so we can demo each branch live.
- **Knowledge base:** redacted/synthetic Underwriting Guidelines (~50 docs), a Fed rate feed mock, a product catalog (~20 products).
- **No real PII. Ever.** This is critical for a public booth.

## Why this is a great showcase for Clearwater Forest
- **Many short tool calls per turn** → benefits from core count and low per-task overhead.
- **RAG over a non-trivial KB** → DDR5-8000 + LLC headroom matter.
- **Vision step** → showcases CPU-side multimodal inference (with OpenVINO or similar) without a GPU.
- **Concurrent sessions** → the headline density chart writes itself.
- **On-prem regulated data** → the FSI compliance narrative lands without us having to argue for it.
