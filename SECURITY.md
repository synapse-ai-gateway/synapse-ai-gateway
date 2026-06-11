# Security Policy

Synapse AI Gateway is security infrastructure. We take vulnerabilities seriously
and appreciate responsible disclosure.

## Supported versions

The project is pre-1.0. Security fixes are applied to the latest released minor
version and `main`. There is no backport guarantee for older tags yet; this table
will be filled in once a stable release line exists.

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ |
| older tags | ❌ (upgrade to latest) |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately through either:

1. **GitHub Security Advisories** (preferred) — go to the repository's
   **Security → Advisories → Report a vulnerability**. This opens a private
   channel visible only to maintainers.
2. **Email** — `security@synapse-gateway.com` (set up the monitored alias on
   the synapse-gateway.com domain before publishing). Encrypt with our PGP key
   if the details are sensitive.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce, or a proof-of-concept.
- Affected version / commit.
- Any suggested remediation, if you have one.

## What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement of your report | within 3 business days |
| Initial assessment + severity rating | within 7 business days |
| Fix or mitigation plan communicated | within 14 business days |
| Public disclosure | coordinated with you, after a fix is available |

We follow coordinated disclosure: we'll agree a timeline with you and credit you in
the advisory (unless you prefer to remain anonymous).

## Scope

Particularly interested in reports affecting the governance controls:

- **Authentication / authorisation bypass** — anything that lets a request reach a
  model backend without a valid, enabled, non-expired API key, or that lets a key
  use a model it isn't assigned.
- **System prompt bypass** — any way for a consuming application to override or
  strip the key-bound system prompt.
- **DLP bypass** — input that should match a `block` pattern but reaches the model,
  or a way to disable scanning.
- **Audit integrity** — anything that lets a request avoid producing an audit
  record, or that writes prompt/response plaintext into the database.
- **Routing bypass** — a `sensitive`-classified key's traffic reaching a cloud
  backend.
- **Secret exposure** — API keys, JWT secrets, or credentials leaking via logs,
  responses, or the admin API.
- Standard web vulns: injection, SSRF, auth flaws, privilege escalation.

## Out of scope

- Vulnerabilities in third-party dependencies that have no exploit path through
  Synapse (report those upstream; we'll bump the dependency).
- Findings that require an already-compromised host or database.
- Denial of service from misconfiguration (e.g. rate limits set too high).
- The intentional defaults documented as dev-only (e.g. the placeholder
  `JWT_SECRET` in `.env.example`) — these are not vulnerabilities, they are
  configuration you are expected to change. See the production checklist in the
  README.

## Hardening guidance

If you're deploying Synapse, the README's **Deployment guide** and
`docs/audit-logging.md` cover the production checklist: rotate all default secrets,
terminate TLS at a reverse proxy, use a managed Postgres, restrict `CORS_ORIGIN`,
and review DLP patterns for your jurisdiction.
