# Synapse AI Gateway

**A lightweight, governance-first AI gateway for regulated organisations. Route to local and cloud LLMs with built-in DLP, audit logging, and per-key use-case scoping.**

[![CI](https://github.com/synapse-ai-gateway/synapse-ai-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/synapse-ai-gateway/synapse-ai-gateway/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/synapse-ai-gateway/synapse-ai-gateway/branch/main/graph/badge.svg)](https://codecov.io/gh/synapse-ai-gateway/synapse-ai-gateway)
[![Container](https://img.shields.io/badge/ghcr.io-synapse--ai--gateway-blue?logo=docker)](https://github.com/synapse-ai-gateway/synapse-ai-gateway/pkgs/container/synapse-ai-gateway)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)

---

## Screenshots

The admin console gives operators a single place to manage teams, review audit
records, and configure DLP. All screens use the per-key governance model — every
team has a bound system prompt, model allowlist, classification, and rate limit.

| Dashboard | Audit log |
|-----------|-----------|
| ![Dashboard — request volume, DLP block count, rate-limit hits, active teams, and recent incidents](docs/screenshots/01-dashboard.png) | ![Audit log — every request, including DLP blocks and rate-limit blocks, with prompt hash and latency](docs/screenshots/02-audit-logs.png) |

| DLP incidents | Teams |
|---------------|-------|
| ![DLP incidents — per-incident pattern matches, severity, and source side (request vs response)](docs/screenshots/03-dlp-incidents.png) | ![Teams — per-team model assignment, masked API key, rate limit, and enable/disable toggle](docs/screenshots/04-teams.png) |

| DLP patterns |   |
|--------------|---|
| ![DLP patterns — regex pattern library with per-pattern severity and enable toggle, configurable from the UI](docs/screenshots/05-dlp-patterns.png) | |

---

## Why Synapse?

There are plenty of AI gateways. Synapse exists because *governance-first, self-hosted, and lightweight* is a combination none of the alternatives cover well.

- **Governance is the product, not a plugin.** Per-API-key system prompts, prompt-layer DLP, model allowlists and immutable audit live in the request path, not in optional middleware you have to wire up. They can't be bypassed by a consuming application no matter what it sends.
- **No data leaves your network.** Self-hosted only. Postgres is your Postgres, the LLM endpoint is whichever address you point it at. Hosted SaaS gateways are non-starters for regulated workloads; this is built for those workloads first.
- **One command, real machines.** `docker compose up` brings the whole stack — postgres + backend + admin console — in five minutes. Backend is ~195 MB image with ~50 MB idle RSS. Runs on a laptop for development and on a single VM for a small team. No Redis, no Celery, no message broker required to get started.
- **Hybrid local + cloud routing as a first-class control.** Sensitive teams stay on your on-prem LLM (Ollama, vLLM, anything OpenAI-compatible). Non-sensitive teams may route to a cloud endpoint — but only when the data classification on the *API key* permits it. The application can't override that.

If you need 100+ provider adapters and don't care about deep audit, use [LiteLLM](https://github.com/BerriAI/litellm). If you want polished dashboards and can send data to a SaaS, use a commercial gateway. If you need governance-first behaviour you can audit line-by-line and host yourself, this is for you.

---

## Architecture

Every chat-completion request passes through five layers in order:

```mermaid
flowchart LR
    A[Client app] --> L1
    L1[Layer 1<br/>Auth + scope<br/>━━━<br/>API key lookup<br/>key expiry<br/>rate limit<br/>daily token budget]
    L1 --> L2[Layer 2<br/>DLP request scan<br/>━━━<br/>regex patterns<br/>block / redact / alert<br/>incident logged]
    L2 --> L3[Layer 3<br/>Hybrid routing<br/>━━━<br/>data_classification<br/>sensitive → on-prem<br/>non-sensitive → cloud]
    L3 --> LLM[(LLM backend<br/>Ollama / vLLM /<br/>OpenAI-compatible)]
    LLM --> L5[Layer 5<br/>DLP response scan<br/>━━━<br/>block on PII leak<br/>incident logged]
    L5 --> L4[Layer 4<br/>Audit log<br/>━━━<br/>SHA-256 hashes<br/>never plaintext<br/>append-only Postgres]
    L4 --> R[Response to client]
```

Layer 4 (audit) is written for every outcome — success, blocked_auth, blocked_dlp, blocked_rate_limit, and error. Prompt and response are stored as SHA-256 hashes only; the plaintext never enters the database.

---

## Quick Start

Working in about five minutes on any machine with Docker.

### Prerequisites

- Docker 24+ with Compose v2 (Docker Desktop on Mac/Windows, or Docker Engine + compose plugin on Linux)
- A local LLM. The defaults point at [Ollama](https://ollama.com) on the host: `ollama pull llama3.2` covers it. Or set `VLLM_URL` to any OpenAI-compatible endpoint (vLLM, OpenAI, Azure, an internal gateway, …).

### Bring the stack up

```bash
git clone https://github.com/synapse-ai-gateway/synapse-ai-gateway.git
cd synapse-ai-gateway
cp .env.example .env
docker compose up -d
```

That brings up three containers: `synapse-postgres`, `synapse-backend` (port 8080), and `synapse-frontend` (port 5173).

Wait ~15 seconds, then verify:

```bash
curl http://localhost:8080/
# {"status":"ok","service":"Synapse AI Gateway"}
```

### Or use the quickstart script

The script handles prerequisite checks, generates a real `JWT_SECRET`, prompts for the admin password, polls health, and runs a smoke test:

```bash
# Linux / macOS
scripts/quickstart.sh

# Windows
scripts\quickstart.bat
```

Both support `--reset` (wipe the postgres volume) and `--reconfigure` (re-prompt for secrets).

### Create your first API key

Teams are **not** auto-seeded — their `api_key` is a credential, and printing it to `docker logs` would leak it permanently. Instead:

1. Open the admin console: <http://localhost:5173>
2. Log in: `admin` / `ChangeMe_At_First_Login_123!` (you'll be forced to change the password)
3. **Teams → Add Team**. Pick a name, a model (e.g. `llama3.2:latest`), a rate limit, an optional system prompt
4. The `api_key` is shown **once** in the create dialog — copy it now

### First request

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_TEAM_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:latest",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

That's a standard OpenAI-compatible chat completion. Any OpenAI SDK works against it — just point `base_url` at `http://localhost:8080/v1` and pass the team key.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="<YOUR_TEAM_API_KEY>",
)
response = client.chat.completions.create(
    model="llama3.2:latest",
    messages=[{"role": "user", "content": "hello"}],
)
print(response.choices[0].message.content)
```

---

## Demo data and mock mode

Two separate features for showing the gateway to other people. They are designed for
demos and screenshots — **never enable either in production**.

### Demo data seeder (real backend, fake content)

`backend/seed_demo.py` populates the real database with realistic-looking rows so
every screen has something to show: 5 teams with varied governance config, 2 extra
users, ~5,800 audit log entries spread across the last 30 days (weighted to business
hours, with weekends quieter), and ~490 DLP incidents tied to the blocked-DLP rows.

The script wipes its own data first, so re-running is safe. The `admin` user, DLP
patterns, and gateway settings are always preserved.

```bash
# Seed
docker compose exec backend python seed_demo.py

# Wipe demo data again (leaves admin, DLP patterns, gateway settings intact)
docker compose exec backend python seed_demo.py --wipe
```

The two extra users (`sarah.analyst`, `dev.viewer`) are seeded with password
`ChangeMe_At_First_Login_123!` and the force-change flag set, so logging in as them
will prompt for a new password — useful if you want to screenshot the
password-change flow itself.

### Mock data mode (no backend at all)

The admin console has a toggle at the bottom of **Settings → Mock Data Mode** that
swaps every API call for an in-memory fixture. The real backend is not touched at
all. Useful for UI-only demos (sales calls, design reviews, talks) where you don't
want to spin up the stack.

When mock mode is on:

- A confirmation modal warns you before flipping the switch — including that you
  will be signed out and that **your real credentials will not work**.
- The login becomes `admin` / `password`.
- An amber "Active" pill appears on the toggle so it is obvious mock mode is on.

To turn mock mode off, log in with the demo credentials and toggle it off again, or
clear the `sg_use_mock` key from your browser's local storage:

```js
// Paste in the browser console on the login page:
localStorage.removeItem('sg_use_mock'); location.reload();
```

The flag is per-browser (localStorage), not per-user — clearing it on one machine
does not affect anyone else.

---

## Configuration reference

Every value the gateway reads is environment-driven. Two `.env` files matter:

- **`./.env`** — read by `docker compose` to substitute into the stack (`${VAR}` references). See `.env.example`.
- **`backend/.env`** — read by the FastAPI process itself (loaded by `python-dotenv`). See `backend/.env.example`.

Documented values below come from `backend/.env.example`. Anything not set falls through to the default.

### Database

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/synapse_ai_gateway` | **Yes** for production | Async SQLAlchemy URL. Postgres via asyncpg primary; MSSQL via `mssql+aioodbc://…` also supported. |
| `DB_POOL_SIZE` | `10` | No | SQLAlchemy connection-pool size. |
| `DB_MAX_OVERFLOW` | `20` | No | Extra connections allowed beyond `DB_POOL_SIZE`. |
| `DB_POOL_PRE_PING` | `true` | No | Test connections before use (recovers from dropped DB connections). |
| `DB_ECHO` | `false` | No | Echo every SQL statement to the log. Dev only. |

### LLM backend

| Variable | Default | Required | Description |
|---|---|---|---|
| `VLLM_URL` | `http://localhost:11434/v1` | No | OpenAI-compatible endpoint, including `/v1`. Defaults to a host Ollama. |
| `CLOUD_VLLM_URL` | *(empty)* | No | Optional cloud endpoint for `non_sensitive` teams. Empty disables hybrid routing — all traffic stays on-prem. |
| `DEFAULT_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | No | Model assigned to new teams. Must be one your `VLLM_URL` can serve. |
| `LLM_REQUEST_TIMEOUT_SEC` | `30` | No | Maximum time to wait for a completion. Bump to ~180 for CPU cold-load. |
| `MODELS_FETCH_TIMEOUT_SEC` | `5.0` | No | Timeout for the admin `GET /admin/models` proxy call. |

### Outbound HTTP client (gateway → LLM)

| Variable | Default | Required | Description |
|---|---|---|---|
| `HTTP_CONNECT_TIMEOUT_SEC` | `5.0` | No | TCP connect timeout. |
| `HTTP_WRITE_TIMEOUT_SEC` | `10.0` | No | Write timeout. |
| `HTTP_POOL_TIMEOUT_SEC` | `5.0` | No | Time to wait for a connection from the pool. |
| `HTTP_MAX_KEEPALIVE_CONNECTIONS` | `10` | No | httpx connection-pool sizing. |
| `HTTP_MAX_CONNECTIONS` | `20` | No | httpx connection-pool sizing. |

### Authentication / JWT

| Variable | Default | Required | Description |
|---|---|---|---|
| `ADMIN_PASSWORD` | `ChangeMe_At_First_Login_123!` | **Yes** before first run | Initial password for the seeded `admin` superadmin. Forced change on first login. |
| `JWT_SECRET` | `change-this-to-a-32-char-random-string-now` | **Yes** | JWT signing secret. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `JWT_ALGORITHM` | `HS256` | No | Signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_HOURS` | `8` | No | Admin session token lifetime. |
| `BCRYPT_ROUNDS` | `12` | No | Password hashing cost factor. |
| `PASSWORD_MIN_LENGTH` | `12` | No | Minimum length for new/changed admin passwords. |
| `TEMP_PASSWORD_LENGTH` | `16` | No | Length of admin-reset temporary passwords. |

### Security policy

These both **seed** the editable `gateway_settings` table on first start *and* act as runtime fallbacks if the row is missing.

| Variable | Default | Description |
|---|---|---|
| `MAX_FAILED_LOGINS` | `5` | Failed logins before temporary lockout. |
| `LOCKOUT_MINUTES` | `30` | Lockout duration after the threshold. |
| `INACTIVITY_DISABLE_DAYS` | `90` | Auto-disable admin accounts after this many idle days (0 = never). |
| `MIN_PASSWORD_AGE_DAYS` | `1` | Minimum gap between admin password changes (prevents cycling). |
| `MAX_PASSWORD_AGE_DAYS` | `90` | Force rotation after this many days (0 = never). |
| `PASSWORD_HISTORY_COUNT` | `24` | Reject reuse of the last N admin passwords. |
| `SESSION_WARNING_MINUTES` | `2` | UI warns the admin this many minutes before token expiry. |
| `SINGLE_SESSION_PER_USER` | `true` | New login invalidates the previous one. |

### Rate limit + prompt defaults

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_REQUESTS` | `10` | Default per-team request allowance within `DEFAULT_WINDOW_SEC`. |
| `DEFAULT_WINDOW_SEC` | `60` | Default rate-limit window in seconds. |
| `DEFAULT_SYSTEM_PROMPT` | (see file) | Default system prompt for teams that have none. |

### DLP

| Variable | Default | Description |
|---|---|---|
| `DLP_PATTERNS_FILE` | `backend/dlp_patterns.json` | JSON array of `{name, pattern, severity, action}` definitions to seed an empty DB. Editable via admin API afterwards. |

### CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGIN` | `http://localhost:5173` | Comma-separated list of allowed admin-console origins. |

### Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Root log level (`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`). Logs to stdout/stderr — no log files. |

### Deploy-time (compose / scripts)

| Variable | Default | Description |
|---|---|---|
| `BACKEND_PORT` | `8080` | Port the backend container listens on. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `synapse_ai_gateway` | Used by both the `postgres` service and the backend's composed `DATABASE_URL` in `docker-compose.yml`. |

### Frontend

The admin console (`frontend/`) reads its own `.env`. These get baked into the SPA bundle at build time.

| Variable | Default | Description |
|---|---|---|
| `VITE_GATEWAY_URL` | `http://localhost:8080` | Where the browser bundle sends API calls. |
| `VITE_USE_MOCK` | `false` | If `true`, the UI runs against an in-memory mock — useful for design work without a backend. |
| `VITE_DEV_PORT` | `5173` | `npm run dev` listen port. |
| `VITE_DEV_HOST` | `0.0.0.0` | `npm run dev` bind address. |

---

## Core concepts

### API keys

Every chat-completion request is authenticated by a Bearer token that's a team API key — **not** a user JWT. (JWTs are for the admin console only.)

An API key is bound at issuance to:

- a **team name** (logged with every request)
- an **assigned model** (caller cannot override; mismatch → 403)
- a **rate limit** (requests per sliding window)
- an optional **`expires_at`** (NULL = never expires; expired key → 403)
- an optional **`tokens_per_day`** budget (NULL = unlimited; exhausted → 429 with token headers)
- a **`data_classification`** of `sensitive` or `non_sensitive` (drives hybrid routing)
- an optional team-specific **system prompt** (prepended to every request, see below)

Keys are returned **once** in the create response and **masked** everywhere else (audit log, incident export, team list).

### System prompt enforcement

The team-bound system prompt is prepended to every chat-completion request. Any `system` message the caller includes is stripped first. The application cannot override the governance prompt by sending its own. If the team has no prompt, the global `default_system_prompt` setting is used.

### DLP

Every chat completion runs through two DLP passes:

- **Request side** — the most recent user message is scanned against the patterns in `dlp_patterns` (or whatever's in `DLP_PATTERNS_FILE` on first seed).
- **Response side** — the assistant's reply is scanned the same way.

Each pattern has an **action**:

| Action | Outcome on match |
|---|---|
| `block` | Reject with `400`, body `{"error": "Request blocked by DLP policy", "incident_id": …, "findings": …}`. Audit row status = `blocked_dlp`. |
| `redact` | Replace matches in the prompt with `[REDACTED:<pattern_name>]` and forward. Incident logged with `action=redact`; the request still completes (success audit, `dlp_flagged=True`). |
| `alert` | Log an incident and forward the prompt unchanged. Same success outcome with `dlp_flagged=True`. |

When multiple patterns match, the strongest action wins: `block > redact > alert`.

The shipped `backend/dlp_patterns.json` covers credit-card numbers, IBAN, account numbers, email, and two jurisdiction-specific national-ID / phone patterns. Add or change patterns through the admin **DLP Patterns** page or `PATCH /admin/dlp-patterns/{name}`.

### Hybrid routing

Each team carries a `data_classification`:

- **`sensitive`** (default) — always routes to `VLLM_URL` (your on-prem backend).
- **`non_sensitive`** — routes to `CLOUD_VLLM_URL` when one is configured; otherwise falls back to on-prem (the safe direction).

The classification is on the *API key*. The application can't smuggle "non-sensitive" by claiming so in a header — it's whichever value the admin set when creating the team.

### Audit schema

Every outcome — `success`, `blocked_auth`, `blocked_rate_limit`, `blocked_dlp`, `error` — writes a row to `audit_logs`. The columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | int | PK |
| `api_key` | str(36) | Team key (masked when read via the admin API) |
| `team_name` | str(100) | For dashboards without joining `teams` |
| `model` | str(200) | Model actually forwarded to (or `""` for auth failures) |
| `status` | str(30) | `success` / `blocked_auth` / `blocked_dlp` / `blocked_rate_limit` / `error` |
| `prompt_hash` | str(64) | SHA-256 of the request's last user message. **Plaintext is never stored.** |
| `response_hash` | str(64) | SHA-256 of the assistant content (non-streaming only; NULL for streamed). |
| `dlp_flagged` | bool | True for any DLP match — block, redact, or alert |
| `incident_id` | str(36) | FK to `dlp_incidents` when DLP fired |
| `response_status` | int | HTTP status returned to the client |
| `latency_ms` | int | End-to-end |
| `auth_ms` / `dlp_ms` / `inject_ms` / `vllm_ms` | int | Per-stage timing |
| `tokens_used` | int | From the LLM's `usage.total_tokens` |
| `client_ip` | str(45) | Stored full; masked (`xxx` last octet) when read via the admin API |
| `timestamp` | datetime | UTC, indexed |

Append-only by design. Never `UPDATE`, never `DELETE`. Retention is a downstream concern (your `pg_partman` or equivalent, see deployment guide).

---

## Deployment guide

The Quick Start gets you running on a laptop. Production needs a few more steps.

### Production checklist

- [ ] **Secrets.** Replace every default in `.env`. At minimum: `JWT_SECRET` (64-char hex), `ADMIN_PASSWORD` (strong, you'll change it on first login anyway), `POSTGRES_PASSWORD`. Use a secrets manager (Vault, AWS Secrets Manager, Doppler) or your platform's native mechanism, not committed `.env`.
- [ ] **TLS.** Terminate at a reverse proxy. The container speaks plain HTTP on `:8080`; never expose that directly.
- [ ] **Postgres.** Use a managed instance or a dedicated postgres VM with WAL archiving. The compose-bundled postgres is for development only.
- [ ] **Backups.** See below. Audit data is the gateway's reason to exist; losing it defeats the point.
- [ ] **Monitoring.** Track the `audit_logs` table (write rate, status distribution) and the `/` health endpoint. The gateway logs to stdout/stderr — collect with whatever you already use.
- [ ] **CORS.** Set `CORS_ORIGIN` to the admin console's real URL (not `localhost:5173`).
- [ ] **DLP review.** The shipped patterns are a starting set, not a compliance package. Add patterns specific to the data your tenants handle.
- [ ] **Rate limits.** Set sane per-team `requests` and `tokens_per_day` before opening to real workloads.
- [ ] **Log retention.** Audit grows. Plan a partitioning/archival strategy.

### Database backup

Plain `pg_dump` is sufficient for most installs. Run from a host with `psql` and the connection details:

```bash
# Full SQL dump (good for restore portability)
pg_dump \
  --host=<your-postgres-host> \
  --username=<your-postgres-user> \
  --dbname=synapse_ai_gateway \
  --format=custom \
  --file=synapse-$(date -u +%Y%m%dT%H%M%SZ).pgdump

# Restore (drops + recreates database content)
pg_restore --clean --if-exists \
  --host=<host> --username=<user> --dbname=synapse_ai_gateway \
  synapse-20260101T120000Z.pgdump
```

Schedule with cron / systemd timer / your platform's scheduler. Hourly for the `audit_logs` change rate of a busy install; daily is fine for most. Off-host the dumps.

For a hot-standby production setup, run streaming replication (`pg_basebackup` + WAL) rather than scripted dumps.

### TLS setup

Easiest pattern: a sidecar [Caddy](https://caddyserver.com) container. Drop this into `docker-compose.override.yml`:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
      - frontend

volumes:
  caddy_data:
  caddy_config:
```

And the matching `Caddyfile`:

```caddyfile
gateway.example.com {
    reverse_proxy backend:8080
}

admin.example.com {
    reverse_proxy frontend:8080
}
```

Caddy will request and renew Let's Encrypt certificates automatically on first request. Point the two DNS records at the host and you're done.

For nginx / Traefik / a managed load balancer (ALB / GLB), the same pattern applies — terminate TLS in front, forward plain HTTP to the backend container.

### Health checks

The container ships a `HEALTHCHECK` already. For Kubernetes / Nomad:

```yaml
livenessProbe:
  httpGet: { path: /, port: 8080 }
  initialDelaySeconds: 20
  periodSeconds: 30
readinessProbe:
  httpGet: { path: /, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 10
```

`GET /` returns `{"status":"ok","service":"Synapse AI Gateway"}` once the app has booted and Postgres is reachable.

---

## How does it compare?

| | **Synapse** | **LiteLLM** | **Commercial gateways** (Portkey, Helicone, Vercel AI Gateway, Cloudflare AI Gateway, …) |
|---|---|---|---|
| License | Apache-2.0 | MIT | Proprietary (mostly; some have open proxies) |
| Primary deployment | self-hosted only | self-hosted or SaaS | SaaS-first |
| Data sovereignty | full (your DB, your network) | full when self-hosted | depends on the plan / region |
| LLM providers | any OpenAI-compatible endpoint | 100+ via per-provider adapters | broad, varies |
| Governance posture | core — in the request path, unbypassable | optional via callbacks / budgets | core on enterprise tiers |
| Per-key system prompt enforcement | shipped, unbypassable | available via config | shipped |
| DLP / prompt redaction | shipped (block / redact / alert per pattern) | not built-in | shipped on enterprise tiers |
| Immutable audit (prompt hash, not plaintext) | shipped | basic request logging | shipped |
| Hybrid local + cloud routing on a per-key classification | shipped | available via routing config | varies |
| Admin UI | shipped (React, included) | shipped (admin proxy UI) | shipped, typically richer |
| Production maturity | early — works, small surface area | mature, large adoption | mature |
| When it fits | regulated work that must not leave your network and where governance is the audit trail you'll defend in a review | broad model support, want one OpenAI-compatible facade for many providers | rich dashboards, fast monitoring iteration, willing to send data to a SaaS |

There's overlap. The question to ask is "which one's defaults are governance, and which one's defaults are speed-to-ship?" For regulated workloads on networks that can't talk to a SaaS, Synapse's defaults match what you'd build anyway. For everything else, an existing project is probably faster.

---

## Contributing

Pull requests welcome. Before opening one:

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow, branch policy, and what makes a good PR for this project.
2. Run the test suite locally:
   ```bash
   cd backend
   pip install -r requirements-dev.txt
   COVERAGE_CORE=sysmon pytest --cov=. --cov-report=term-missing -rs
   ```
   The CI gate is ~88% line coverage. New features should ship with tests.
3. Lint and security-scan:
   ```bash
   ruff check .
   bandit -r . -c .bandit -lll
   ```
4. For changes that touch the request path (auth, DLP, routing, audit), include a test that exercises the new branch end-to-end through `httpx ASGITransport` — the existing `tests/conftest.py` has fixtures that make this straightforward.

Security issues: please report them privately rather than opening a public issue. See [SECURITY.md](SECURITY.md) for the disclosure process.

---

## License

[Apache License 2.0](LICENSE). See the file for the full text. In short: you can use, modify, and redistribute this freely, including commercially, as long as you preserve the copyright notice and license terms.

---

## Maintainer

Built and maintained by **Zaka Ul Haque** — [LinkedIn](https://www.linkedin.com/in/zakaulhaque/) · [GitHub](https://github.com/zaddy88).

Synapse AI Gateway started as a response to a real governance gap in regulated environments: teams either adopting AI with no controls or waiting years for enterprise tooling that never quite arrives. It is published openly under Apache 2.0 so any team facing that same gap can deploy a governed AI environment in an afternoon.

Contributions, bug reports, and use-case feedback are welcome — open an [issue](https://github.com/synapse-ai-gateway/synapse-ai-gateway/issues) or a [discussion](https://github.com/synapse-ai-gateway/synapse-ai-gateway/discussions).
