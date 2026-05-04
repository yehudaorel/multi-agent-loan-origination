# env-profiles/

Drop-in `.env` profiles for switching the LLM backend without editing
code. The repo speaks any **OpenAI-compatible** endpoint via three
environment variables (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`),
so a profile change is just a copy.

## Usage

```bash
# From the repo root, pick a profile and copy it over .env
cp env-profiles/local-ollama.env .env       # laptop dev with a local model
cp env-profiles/minimax.env      .env       # MiniMax M2.7 hosted API
cp env-profiles/sambanova.env    .env       # SambaNova Cloud (token farm)

# Then edit .env to fill in your API key (search for FILL_IN)
```

The OpenCLAW workspace (`openclaw-workspace/openclaw.json`) reads the
same `LLM_*` env vars, so changing the profile flips the LLM for both
the upstream FastAPI/LangGraph stack AND the OpenCLAW gateway.

## Available profiles

| Profile | Use case | Endpoint | Tool calling | Notes |
|---|---|---|---|---|
| `local-ollama.env` | Laptop dev with a local model | `http://localhost:11434/v1` (or `host.docker.internal`) | yes (Qwen 2.5 7B+) | Free; CPU-only OK; needs `ollama serve` running |
| `minimax.env` | Test on a low-spec home box | `https://api.minimax.io/v1` | yes | Hosted; needs API key from `platform.minimax.io` |
| `sambanova.env` | Production / "token farm gen" | `https://api.sambanova.ai/v1` | yes | Free tier 10–30 RPM; key from `cloud.sambanova.ai/apis` |

## Container networking gotcha (Linux only)

When `LLM_BASE_URL` points at `localhost` on the **host machine** (the
`local-ollama` profile), the API container can't see the host's
localhost by default on Linux. Two options:

- **Podman**: bring up the stack with `--network=host`, OR change the
  URL to `http://host.containers.internal:11434/v1`.
- **Docker** on Linux: add `extra_hosts: ["host.docker.internal:host-gateway"]`
  to the `mortgage-ai-api` service in `compose.yml` and use
  `http://host.docker.internal:11434/v1`.

Hosted profiles (`minimax.env`, `sambanova.env`) don't have this
problem — their URL points at the public internet, which the
container reaches normally.

## What's NOT in these files

These profiles only set the `LLM_*` triple plus a couple of
networking comments. Everything else (Postgres, MinIO, Auth, MCP
URLs) is unchanged from `.env.example` and the same across profiles —
you only need to touch them if your local setup is non-standard.

If you previously edited `.env` heavily, save your edits before
copying a profile over it: `cp .env .env.bak`.

## OpenCLAW provider naming (validation pending)

The workspace's `openclaw.json` registers the LLM as a provider named
`openai-compatible`. OpenCLAW's actual provider key may differ —
their docs reference per-provider names (`minimax`, etc.) at
`docs.openclaw.ai/providers/`. When you run `openclaw onboard`
locally, watch the gateway log for any provider-resolution errors;
the fix is a one-line change to `openclaw.json`.
