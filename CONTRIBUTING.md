# Contributing to Synapse AI Gateway

Thanks for your interest in contributing. This project is governance infrastructure
for regulated organisations, so the bar for changes — especially in the request
path — is deliberately high. This document explains how to contribute effectively.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Before you start

- **Bug reports and small fixes** — open a PR directly, or file an issue first if
  you want to confirm the approach.
- **New features or behaviour changes** — open an issue first to discuss. Changes
  to the five governance layers (auth, DLP, routing, audit, output filtering) need
  agreement on the design before code, because they are security controls.
- **Security vulnerabilities** — do **not** open a public issue. See
  [SECURITY.md](SECURITY.md) for private disclosure.

---

## Contributor License Agreement (CLA)

Before your first contribution can be merged, you must sign the
[Contributor License Agreement](CLA.md). A bot will prompt you on your first PR;
signing is a one-time, one-click action recorded against your GitHub account.

The CLA lets the project (a) redistribute your contribution under the project
licence, and (b) keep the option to relicense future versions without tracking
down every past contributor. It does **not** transfer copyright — you keep
ownership of your work. See [CLA.md](CLA.md) for the full text.

---

## Development setup

### Prerequisites

- Python 3.11 or 3.12
- Node.js 20+ (only if you're touching the frontend)
- Docker + Docker Compose (for end-to-end testing)

### Backend

```bash
cd backend
python -m venv backend_ve
source backend_ve/bin/activate          # Windows: backend_ve\Scripts\activate
pip install -r requirements-dev.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Full stack

```bash
cp .env.example .env
docker compose up --build
```

---

## Project conventions

These are enforced in review. Most are also enforced in CI.

### Python

- **snake_case** throughout. No exceptions.
- **Type hints on every function signature.** No exceptions.
- **Never log prompt or response content.** Only SHA-256 hashes. This is a hard
  rule — the whole privacy model depends on it.
- **All configuration via environment variables.** Nothing hardcoded. New config
  goes through `config.py` and gets documented in `backend/.env.example`.
- **DLP category definitions live in external config** (`dlp_patterns.json`),
  never in source code.
- Tests mirror the source layout under `backend/tests/`.

### Sensitive areas — extra review

Changes here get scrutinised harder and must include tests:

- **DLP regex patterns** — a false negative means sensitive data reaches a model.
- **Audit log schema** — append-only by design; schema changes need a migration.
- **System prompt injection** — the key-bound prompt must never be bypassable.
- **Rate limiting** — both the per-window request count and the per-day token
  budget are enforced; don't simplify to one.
- **Routing policy** — the `data_classification` check that keeps sensitive data
  on-premises is a security control.

---

## Testing

Run from the `backend/` directory. On Python 3.12+ set `COVERAGE_CORE=sysmon` so
coverage measures `async` handlers accurately.

```bash
cd backend

# Linux / macOS
COVERAGE_CORE=sysmon pytest --cov=. --cov-report=term-missing -rs

# Windows PowerShell
$env:COVERAGE_CORE = 'sysmon'; pytest --cov=. --cov-report=term-missing -rs
```

- The CI gate is **70% minimum** coverage (project sits around 88%).
- New features should ship with tests.
- For changes that touch the request path, add a test that exercises the new
  branch end-to-end via `httpx` `ASGITransport`. The fixtures in
  `backend/tests/conftest.py` (`client`, `gateway`, `mock_llm`, `flush_background`)
  make this straightforward.

---

## Linting and security

Both run in CI; run them locally before pushing:

```bash
cd backend
ruff check .                      # lint (also: ruff check --fix)
bandit -r . -c .bandit -lll       # security scan, fails on HIGH findings
```

---

## Pull request process

1. **Branch** off `main`. Use a descriptive name: `fix/dlp-redact-streaming`,
   `feat/per-key-ip-allowlist`.
2. **Keep PRs focused.** One logical change per PR. Unrelated cleanup belongs in
   its own PR.
3. **Write a clear description.** What changed, why, and how you tested it. If it
   changes behaviour in the request path, say so explicitly.
4. **Update docs.** If you change config, update `backend/.env.example`. If you
   change behaviour, update the relevant file under `docs/`.
5. **Update the CHANGELOG.** Add a line under `## [Unreleased]` in
   [CHANGELOG.md](CHANGELOG.md).
6. **Green CI.** Lint, tests, coverage, and security scans must pass.
7. **Sign the CLA** (first PR only).

A maintainer will review. Expect questions on anything touching a sensitive area —
that's the process working, not an obstacle.

---

## Commit messages

Conventional Commits are encouraged but not required:

```
feat: add per-key IP allowlist enforcement
fix: prevent DLP redact from leaking original prompt in audit
docs: clarify hybrid routing fallback behaviour
test: cover daily token budget reset at UTC midnight
```

---

## Questions

Open a [GitHub Discussion](https://github.com/synapse-ai-gateway/synapse-ai-gateway/discussions)
or a draft issue. We'd rather answer a question early than review a large PR built
on a misunderstanding.
