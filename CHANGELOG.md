# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet — track upcoming changes here.

---

## [0.1.0] - 2026-06-08

Initial public release.

### Added

#### Request pipeline
- OpenAI-compatible `POST /v1/chat/completions` endpoint.
- Five-layer request pipeline: authentication, request-side DLP, hybrid routing,
  LLM forwarding, response-side DLP, audit write.
- Both streaming (SSE) and non-streaming completions.

#### Per-team API keys as the governance primitive
- Each team key is bound at issuance to a team name, an assigned model, a rate
  limit (requests per window), an optional system prompt, an optional
  `expires_at`, an optional `tokens_per_day` budget, and a `data_classification`.
- System prompts are server-side enforced; any client-supplied `system` message
  is stripped before forwarding.
- Model assignment is enforced server-side; mismatched model in the request
  returns `403 Forbidden`.
- Keys are returned **once** in the create response and masked everywhere else
  (admin list, audit log read endpoint, incident export).

#### Rate limiting and quotas
- Sliding-window request count per team key (`requests` per `window_sec`).
- Daily token budget per team key (`tokens_per_day`, NULL = unlimited).
- Both 429 responses include standard `Retry-After` and `X-RateLimit-*`
  headers, plus token-specific `X-RateLimit-Tokens-*` headers for budget 429s.

#### DLP
- Regex-based DLP engine, patterns stored in `dlp_patterns` (Postgres) with
  per-pattern `severity` and `action`.
- Three actions: `block` (HTTP 400), `redact` (substitute and forward),
  `alert` (log and forward). Strongest action wins when multiple match.
- DLP runs on both the request (user message) and the response (assistant
  content). Response-side block returns 502 with an incident_id.
- Initial pattern set seeded from `backend/dlp_patterns.json`; admin UI and
  REST endpoints allow patterns to be added, edited, enabled/disabled.

#### Hybrid routing
- Per-team `data_classification` (`sensitive` / `non_sensitive`) decides routing.
- `sensitive` always routes to the on-prem `vllm_url`.
- `non_sensitive` routes to `cloud_vllm_url` when configured; falls back to
  on-prem if no cloud URL is set.
- The decision is on the API key, not the request — applications cannot opt
  themselves into cloud routing.

#### Audit logging
- Every request — successful, blocked, or errored — writes an `audit_logs` row.
- Prompts and responses are stored as SHA-256 hashes (`prompt_hash`,
  `response_hash`); plaintext is never persisted.
- Per-stage timing captured (`auth_ms`, `dlp_ms`, `inject_ms`, `vllm_ms`,
  `latency_ms`).
- DLP incidents persisted to `dlp_incidents` with `action`, `severity`,
  matched patterns, source (`user_input` / `model_response`), and an
  `incident_id` cross-linked to the audit row.

#### Admin console (React + Vite)
- Dashboard with today's request volume, DLP blocks, rate-limit hits, active
  teams, requests-per-team last 60 minutes, recent DLP incidents.
- Pages for Teams, DLP Incidents, Audit Log, Settings, Users, Activity Log,
  API Docs.
- CSV export for both audit log and DLP incidents.
- API key shown once on team creation, masked everywhere else.

#### Admin authentication (JWT)
- `bcrypt` password hashing.
- Configurable password policy: minimum length, age, history, complexity.
- Account lockout on repeated failed logins.
- Single-session enforcement (new login invalidates previous token).
- Forced password change on first login.
- Inactivity-based auto-disable for admin accounts.

#### Configuration
- All configuration via environment variables; centralised in `backend/config.py`.
- Comprehensive `backend/.env.example` documenting every variable.
- Separate `.env.example` at the repo root for `docker compose` variable
  substitution.

#### Deployment
- Multi-stage backend `Dockerfile` (Python 3.12-slim, non-root user,
  healthcheck, OCI image labels) — final image ~195 MB.
- Multi-stage frontend `Dockerfile` (Node build → `nginx-unprivileged`) with
  SPA-aware nginx config.
- `docker-compose.yml` orchestrating postgres + backend + frontend with
  `${VAR:-default}` env substitution and a fixed project `name`.
- Quickstart scripts (`scripts/quickstart.sh`, `scripts/quickstart.bat`) with
  `--reset` and `--reconfigure` flags, idempotent on repeated runs.

#### CI / CD
- GitHub Actions `ci.yml`: ruff lint, pytest with coverage (Python 3.11 and
  3.12 matrix), Bandit security scan, Trivy filesystem scan, Docker build
  with Trivy image scan + SARIF upload to GitHub Security.
- GitHub Actions `release.yml`: builds and pushes images to GHCR on `v*.*.*`
  tags, generates a GitHub Release with auto-generated changelog notes.
- Codecov gate at 70% project + patch coverage.

#### Testing
- 69 pytest tests covering auth, rate limiting, DLP modes, audit, admin CRUD,
  routing, error branches, streaming, login flows.
- File-backed SQLite test database, ASGI client via `httpx.ASGITransport`,
  mocked LLM client, deterministic draining of detached audit writes.
- ~88% line coverage with the `sysmon` coverage tracer on Python 3.12.

#### Documentation
- `README.md` with quick start, configuration reference, comparison vs LiteLLM
  and commercial gateways.
- `docs/governance-model.md`, `docs/dlp-configuration.md`,
  `docs/hybrid-routing.md`, `docs/audit-logging.md`.
- Contributing guide, code of conduct, security policy, Apache-2.0 LICENSE
  and NOTICE.

### Security
- API keys returned in plaintext only once at creation; masked thereafter in
  all admin read endpoints and CSV exports.
- Default JWT secret is a clearly-marked placeholder; production deployments
  must override.
- Default admin password is forced to change on first login.
- Detached audit/DLP database writes wrap their work in `try/except` so a
  Postgres outage produces a logged error rather than a silently lost
  governance record.

### Known limitations (in scope for future releases)
- Single-model assignment per team. Multi-model allowlists require multiple
  keys today; the data model is ready to extend.
- No native Anthropic / Google adapter — cloud routing is OpenAI-compatible
  only. Use a translation layer (e.g. LiteLLM) in front of `cloud_vllm_url`.
- No built-in audit retention. Operator-managed via scheduled `DELETE` or
  Postgres native partitioning; documented in `docs/audit-logging.md`.
- No webhook streaming of audit events. Use a polling sidecar against
  `audit_logs.id` for now.
- No automatic backend failover between cloud and on-prem on upstream errors.

---

[Unreleased]: https://github.com/synapse-ai-gateway/synapse-ai-gateway/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/synapse-ai-gateway/synapse-ai-gateway/releases/tag/v0.1.0
