# Hybrid routing

The gateway can forward to two backends: an **on-premises** endpoint (whatever you run inside your network) and an optional **cloud** endpoint (an LLM API outside your network). Which backend a request goes to is decided by the **data classification** on the calling team's API key.

This document covers how that decision is made, how to configure each backend type, and what happens when one is unreachable.

---

## How routing decisions are made

Two settings drive the decision:

| Source | Variable | Default |
|---|---|---|
| `gateway_settings` table (or `VLLM_URL` env on first seed) | `vllm_url` | `http://localhost:11434/v1` |
| `gateway_settings` table (or `CLOUD_VLLM_URL` env on first seed) | `cloud_vllm_url` | *(empty)* |

Per-team:

| Field | Values |
|---|---|
| `data_classification` | `sensitive` *(default)* / `non_sensitive` |

The decision logic, applied to every chat completion:

```
if team.data_classification == "non_sensitive" and cloud_vllm_url is set:
    → forward to cloud_vllm_url
else:
    → forward to vllm_url   (on-prem)
```

That's the entire policy. Three properties are worth calling out:

1. **The default is on-prem.** A team without an explicit classification routes to the on-prem URL. A team marked `non_sensitive` with no cloud URL configured also routes to on-prem. The safe direction is the default.
2. **The application can't choose.** The classification is on the *key*, not the request. The application sends what it sends; the gateway decides where it goes.
3. **There's no per-request override.** If a key is `sensitive`, every request from it stays on-prem — there's no "but this one is fine, send it to GPT-4o" path. If you need both, issue two keys with two classifications.

---

## Configuring on-premises backends

The `vllm_url` setting can point at anything that speaks the OpenAI-compatible chat-completions protocol.

### Ollama

Most common for laptop / on-prem. Pull a model and point the gateway at the host:

```bash
ollama pull llama3.2
# Ollama listens on :11434 by default
```

In `.env` (or the admin **Settings** page):

```env
VLLM_URL=http://localhost:11434/v1
DEFAULT_MODEL=llama3.2:latest
```

If the gateway runs in Docker on the same host as Ollama:

```env
VLLM_URL=http://host.docker.internal:11434/v1
```

For Linux hosts that don't have Docker Desktop's automatic `host.docker.internal`, add this to the `backend` service in `docker-compose.yml`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Ollama also needs to be listening on an interface the gateway can reach. By default Ollama binds to `127.0.0.1`, which is unreachable from inside the container. Set `OLLAMA_HOST=0.0.0.0:11434` in Ollama's environment if the gateway can't connect.

### vLLM

vLLM exposes an OpenAI-compatible server. Run it:

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct \
  --host 0.0.0.0 --port 8000
```

Point the gateway:

```env
VLLM_URL=http://<vllm-host>:8000/v1
DEFAULT_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

vLLM is GPU-only. Production usually runs it on a dedicated inference VM with the gateway in front.

### Any OpenAI-compatible endpoint

If it accepts `POST /v1/chat/completions` with OpenAI's request and response shapes, it works. That includes self-hosted LocalAI, llama.cpp's server, TGI's OpenAI mode, LiteLLM running as a proxy, and many others. Just set `VLLM_URL` to the base URL with the `/v1` suffix.

### Timeouts

CPU inference can take 10–60 s for a cold load. If you see `504 Gateway Timeout` on the first call after startup:

```env
LLM_REQUEST_TIMEOUT_SEC=180
```

GPU production usually needs less: `30` is fine.

---

## Configuring cloud backends

The cloud URL has the same shape as the on-prem one: an OpenAI-compatible base ending in `/v1`.

### OpenAI (native)

OpenAI's API *is* the OpenAI-compatible API. Point and key:

```env
CLOUD_VLLM_URL=https://api.openai.com/v1
```

The team's request must carry a Bearer token that OpenAI accepts. The gateway forwards Authorization headers; you can either have applications send OpenAI keys as Bearer (not recommended — defeats the per-team isolation), or front the cloud endpoint with a small reverse proxy that swaps the gateway's bearer for the OpenAI key. The cleanest pattern is:

```
team key → gateway → reverse-proxy that owns the OpenAI key → OpenAI
```

The reverse proxy lives in your VPC, holds the API key in its secret store, and rewrites Authorization. Application teams never see the OpenAI key.

### Azure OpenAI

Azure OpenAI is OpenAI-compatible at the protocol level. Set `CLOUD_VLLM_URL` to:

```env
CLOUD_VLLM_URL=https://<your-resource>.openai.azure.com/openai/deployments/<deployment>
```

Note the path differs from openai.com — you point at a specific deployment. Same reverse-proxy pattern for the Azure key recommended.

### Anthropic Claude (native)

Anthropic's native API is **not** OpenAI-compatible. The request shape, headers, and streaming format all differ. Pointing `CLOUD_VLLM_URL` directly at `api.anthropic.com` will not work.

To use Anthropic, run a small translation layer in front of the gateway's cloud URL:

- **LiteLLM** in proxy mode supports this — it accepts OpenAI-shaped requests and translates to Anthropic. Run it inside your network and point `CLOUD_VLLM_URL` at it.
- A custom adapter — about 80 lines of Python — works too. The translation isn't complex; it's just not in this codebase.

### Google Gemini / Vertex AI

Same situation as Anthropic. Google's native APIs aren't OpenAI-shaped. Use a translator (LiteLLM, or your own adapter) and point `CLOUD_VLLM_URL` at the translator.

### Why not bake in adapters?

Adapters are a maintenance treadmill — every provider's API changes on its own schedule. Synapse's design choice is to be small and protocol-honest: it speaks OpenAI to anything that listens for OpenAI. Translation belongs in a separate layer with a different release cadence.

---

## Data classification

Classification is a property of the **team**, not the request. It's set at team creation and changed via `PATCH /admin/teams/{id}`.

| Classification | Default routing | Use for |
|---|---|---|
| `sensitive` *(default)* | Always on-prem (`vllm_url`) | Any team handling PII, regulated data, customer information, financial records, internal policy, or anything you wouldn't paste into a public chat. |
| `non_sensitive` | Cloud (`cloud_vllm_url`) if set; falls back to on-prem if not | Marketing copy generation, public knowledge Q&A, code completion against public-domain repos, sandbox / demo use cases. |

### Setting it on a team

```bash
curl -X PATCH http://localhost:8080/admin/teams/<team_id> \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"data_classification": "non_sensitive"}'
```

### Practical guidance

Classify **conservatively**. The cost of mis-classifying as `sensitive` is some latency and some compute on your own GPU. The cost of mis-classifying as `non_sensitive` is data leaving the network. The defaults reflect that asymmetry.

For mixed workloads — a team that does both sensitive support tickets *and* non-sensitive marketing copy — issue two keys. One classified each way. The application picks based on the call site, not the prompt content.

---

## Failover and fallback behaviour

This is the section where I have to be precise about what's built and what isn't.

### What's implemented

| Scenario | Behaviour |
|---|---|
| `non_sensitive` team, `cloud_vllm_url` is unset/empty | **Falls back to on-prem.** The team routes to `vllm_url` instead. No error, no warning — the safer destination wins by default. |
| `sensitive` team, on-prem backend returns 5xx or is unreachable | The gateway returns `502 Bad Gateway` or `504 Gateway Timeout` to the client. Audit row written with `status=error`. **No automatic retry to cloud.** |
| `non_sensitive` team, cloud backend returns 5xx or is unreachable | Same — `502`/`504` to the client. **No automatic failover to on-prem.** |
| Either backend returns 4xx (model not found, auth failure) | The 4xx body is forwarded back to the client as a `502` with the upstream's error detail. |

### What's not implemented

- **No active-active backend load balancing.** Each team has exactly one destination, decided by classification.
- **No automatic failover from cloud to on-prem.** If the cloud LLM is down and a `non_sensitive` team's request hits a `5xx`, the gateway returns the error. It does not retry against on-prem — which would be the wrong thing anyway, since "the cloud chose to fail" is not equivalent to "send this to a different model".
- **No retry-on-timeout.** A single attempt is made; if it times out, the client gets `504`.

### Why this is the design

Automatic failover sounds appealing but tends to mask underlying problems. If your cloud backend is slow, you want to see the timeouts, not silently double the request volume against on-prem. If your on-prem GPU is full, you want the rate limit to bite, not bounce overflow into a paid cloud account.

The right way to layer in availability is a reverse proxy in front (HAProxy, Envoy, nginx) that handles retries and failover policy at the network layer, where it belongs — not inside the governance gateway.

### Health check on the LLM backend

The gateway exposes `GET /admin/models` (admin-only) which proxies to `vllm_url/models`. A monitoring system can poll this — a non-2xx response means the on-prem backend is unreachable from the gateway, which is the symptom you actually care about.

For Postgres reachability and process health, `GET /` returns `200 OK` once the app is up.

---

## Related documents

- [docs/governance-model.md](governance-model.md) — where `data_classification` is set
- [docs/audit-logging.md](audit-logging.md) — `status=error` rows tell you which backend failed
- [`docker-compose.yml`](../docker-compose.yml) — the bundled stack uses `host.docker.internal` for the on-prem case
