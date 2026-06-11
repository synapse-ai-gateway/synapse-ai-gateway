# Audit logging

The gateway writes an `audit_logs` row for every request — successful, blocked, or errored. Prompts and responses are stored as SHA-256 hashes; the plaintext never lands in the database. This document covers the schema, the rationale, common compliance queries, and the operator side of retention and export.

---

## Complete schema

```sql
CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    api_key         VARCHAR(36) NOT NULL,
    team_name       VARCHAR(100) NOT NULL,
    model           VARCHAR(200) NOT NULL DEFAULT '',
    status          VARCHAR(30)  NOT NULL DEFAULT 'success',
    prompt_hash     VARCHAR(64)  NOT NULL DEFAULT '',
    response_hash   VARCHAR(64),
    response_status INTEGER,
    latency_ms      INTEGER,
    auth_ms         INTEGER,
    dlp_ms          INTEGER,
    inject_ms       INTEGER,
    vllm_ms         INTEGER,
    dlp_flagged     BOOLEAN NOT NULL DEFAULT FALSE,
    incident_id     VARCHAR(36),
    tokens_used     INTEGER,
    client_ip       VARCHAR(45),
    timestamp       TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX ix_audit_logs_api_key   ON audit_logs (api_key);
CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);
```

Field by field:

| Field | Type | Always populated? | Meaning |
|---|---|---|---|
| `id` | int | yes | Surrogate primary key. |
| `api_key` | str(36) | yes | Team key in full. The admin API masks it on read; the database stores the raw value so you can join to the `teams` table for forensics. |
| `team_name` | str(100) | yes | Denormalised from `teams.team_name` at write time, so dashboards don't need to join. For auth failures with no recognised key, the value is `"unknown"`. |
| `model` | str(200) | yes | The model actually forwarded to. `""` for auth failures that never reached the routing step. |
| `status` | str(30) | yes | One of: `success`, `blocked_auth`, `blocked_dlp`, `blocked_rate_limit`, `error`. |
| `prompt_hash` | str(64) | when there was a prompt | SHA-256 hex of the request's last user message. `""` for auth failures where no prompt was scanned. |
| `response_hash` | str(64) | non-streaming success only | SHA-256 hex of the assistant content. `NULL` for streaming responses (content was forwarded chunk-by-chunk, never reassembled server-side), errors, and blocked requests. |
| `response_status` | int | usually | HTTP status returned to the client: `200`, `400`, `401`, `403`, `429`, `502`, `504`, etc. |
| `latency_ms` | int | when measured | End-to-end gateway processing time. |
| `auth_ms` | int | when measured | Time spent on the auth + rate-limit step. |
| `dlp_ms` | int | when measured | Time spent on DLP scans (request + response combined for `success` rows; request-only for blocks). |
| `inject_ms` | int | when measured | Time spent on system-prompt injection. Always tiny; the field exists for symmetry. |
| `vllm_ms` | int | when measured | Time spent in the LLM call itself — the dominant component on almost every row. |
| `dlp_flagged` | bool | yes | `TRUE` if any DLP pattern matched on either side. Includes block, redact, and alert actions. |
| `incident_id` | str(36) | when DLP fired | UUID of the corresponding `dlp_incidents` row. |
| `tokens_used` | int | LLM success only | From the model's `usage.total_tokens`. |
| `client_ip` | str(45) | when the request had a client | Stored unmasked. The admin API masks the last octet on read (`192.168.1.xxx`). IPv6 fits in 45 chars. |
| `timestamp` | datetime | yes | UTC, indexed. Naive `TIMESTAMP WITHOUT TIME ZONE` to keep the schema dialect-portable. |

---

## Why hashes, not plaintext

Storing the prompt and response in plaintext is the obvious thing to do, and the wrong thing.

The audit log exists for accountability — "what happened, when, who did it" — not for verbatim recall. Storing plaintext creates four problems:

1. **It puts secrets in the database.** Anything a user typed (including the very PII the DLP layer is trying to keep out) is now sitting in your audit table, replicated to your standby, included in your `pg_dump` backups, and shipped to your log aggregator if you collect SQL audit. The DLP layer just got bypassed by the audit layer.
2. **It's a compliance liability.** Some regulations (HIPAA, GDPR, India's DPDP) treat the audit log itself as PII once it contains the prompt. You then owe the same controls — encryption at rest, access logging, retention limits, right-to-erasure — on your audit infrastructure as on production data.
3. **It bloats the table.** A few hundred MB of plaintext per million rows is tractable; a few TB of prompt history is not. Query performance and backup windows degrade fast.
4. **It tempts misuse.** A plaintext audit log is one SQL query away from being a content moderation training set, a search engine, a leaderboard of "most embarrassing prompts" — anything but accountability.

A hash gives you what audit actually needs:

- **Existence:** "this team sent a request at 14:03 UTC" — known from the row.
- **Linking:** "is this the same prompt the same team sent five minutes earlier?" — yes if `prompt_hash` matches.
- **Forensic match:** "we found this prompt in an incident report; was it ever sent through the gateway?" — recompute SHA-256 of the suspect prompt, search the column.
- **No recall:** you cannot reconstruct the prompt from the hash. Whoever has the audit log doesn't gain access to the content.

That trade — losing recall to gain accountability without liability — is the design.

---

## Querying for compliance reporting

Common questions, with working SQL. Adjust schema-qualifications (`public.audit_logs` etc.) for your environment.

### Volume by team this month

```sql
SELECT
    team_name,
    COUNT(*) FILTER (WHERE status = 'success')               AS successful,
    COUNT(*) FILTER (WHERE status = 'blocked_dlp')           AS dlp_blocked,
    COUNT(*) FILTER (WHERE status = 'blocked_rate_limit')    AS rate_limited,
    COUNT(*) FILTER (WHERE status = 'blocked_auth')          AS auth_blocked,
    COUNT(*) FILTER (WHERE status = 'error')                 AS upstream_errors,
    SUM(tokens_used) FILTER (WHERE status = 'success')       AS tokens
FROM audit_logs
WHERE timestamp >= date_trunc('month', NOW())
GROUP BY team_name
ORDER BY successful DESC;
```

### Every DLP-blocked request in the last 24 hours with incident detail

```sql
SELECT
    a.timestamp,
    a.team_name,
    a.api_key,
    a.prompt_hash,
    i.patterns,
    i.severities,
    i.max_severity,
    i.action
FROM audit_logs a
JOIN dlp_incidents i ON a.incident_id = i.incident_id
WHERE a.status = 'blocked_dlp'
  AND a.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY a.timestamp DESC;
```

### "Did team X ever send this exact prompt?"

For a known plaintext suspect prompt, compute its hash and search:

```bash
PROMPT_HASH=$(printf '%s' 'the suspect prompt text' | sha256sum | awk '{print $1}')
psql -c "SELECT timestamp, team_name, status
         FROM audit_logs
         WHERE prompt_hash = '$PROMPT_HASH'
         ORDER BY timestamp DESC;"
```

### p95 latency by hour, last 7 days

```sql
SELECT
    date_trunc('hour', timestamp) AS hour,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms,
    COUNT(*)
FROM audit_logs
WHERE status = 'success'
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
```

### Auth failures — possible abuse or misconfiguration

```sql
SELECT
    api_key,
    client_ip,
    COUNT(*) AS attempts,
    MAX(timestamp) AS most_recent
FROM audit_logs
WHERE status = 'blocked_auth'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY api_key, client_ip
HAVING COUNT(*) > 10
ORDER BY attempts DESC;
```

### Same prompt sent across multiple teams (potential prompt sharing)

```sql
SELECT prompt_hash, ARRAY_AGG(DISTINCT team_name) AS teams, COUNT(*) AS hits
FROM audit_logs
WHERE timestamp > NOW() - INTERVAL '30 days'
  AND prompt_hash != ''
GROUP BY prompt_hash
HAVING COUNT(DISTINCT team_name) > 1
ORDER BY hits DESC
LIMIT 50;
```

---

## Retention

There's no in-app retention setting. The gateway writes; nothing in the codebase deletes. This is intentional — the right retention strategy depends on your regulatory regime and your storage budget, and getting it wrong by quietly truncating audit data would be worse than not handling it at all.

Three operator-side approaches, in increasing order of sophistication.

### 1. Scheduled `DELETE` (simplest)

A daily cron that drops rows older than N days. Works well up to ~10 GB of audit data.

```sql
-- Delete audit rows older than 365 days.
DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '365 days';

-- And the matching DLP incidents (FK isn't enforced; clean up by date too).
DELETE FROM dlp_incidents WHERE timestamp < NOW() - INTERVAL '365 days';
```

Run nightly via `pg_cron` or systemd timer. Vacuum afterwards if you don't have autovacuum tuned for write-heavy tables.

### 2. Native partitioning (recommended for production)

Convert `audit_logs` to a partitioned table by month. Drop entire partitions instead of `DELETE` — orders of magnitude faster, no vacuum debt, no bloat.

The pattern (one-time migration):

```sql
-- Rename existing
ALTER TABLE audit_logs RENAME TO audit_logs_old;

-- New parent, partitioned by month
CREATE TABLE audit_logs (
    LIKE audit_logs_old INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- One partition per month
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
-- ... create future months in advance with pg_partman

-- Backfill
INSERT INTO audit_logs SELECT * FROM audit_logs_old;
DROP TABLE audit_logs_old;
```

Then retention is:

```sql
DROP TABLE audit_logs_2025_01;
```

[`pg_partman`](https://github.com/pgpartman/pg_partman) automates partition creation and dropping with a retention policy.

### 3. Archive then delete (for regulations requiring multi-year retention)

If you must retain audit for 7+ years but don't want to keep it hot:

1. Daily: `COPY` rows older than 90 days to compressed Parquet on S3 / GCS / your object store.
2. Verify the export landed (row counts match).
3. `DELETE` (or drop partition) for the same date range.

You retain queryable hot audit for 90 days and cheap cold archives indefinitely. When a request for old data comes in, you read from the cold store.

### Pick one and document it

The worst outcome is an inconsistent retention policy: random rows getting deleted, no one knowing when, no record of what was removed. Whichever you pick, write it down — your regulator (or your future self) will want to see the policy alongside the data.

---

## Exporting audit data

Two paths, depending on whether the consumer is a human or a system.

### CSV export via the admin API

`GET /admin/audit/export` streams a CSV of the audit log, applying any of the same filters as the regular `GET /admin/audit` list endpoint:

```bash
curl -G 'http://localhost:8080/admin/audit/export' \
  -H 'Authorization: Bearer <ANALYST_JWT>' \
  --data-urlencode 'start_date=2026-01-01T00:00:00' \
  --data-urlencode 'end_date=2026-01-31T23:59:59' \
  --data-urlencode 'team_name=Customer Support' \
  --data-urlencode 'statuses=success' \
  --data-urlencode 'statuses=blocked_dlp' \
  > audit-jan-2026.csv
```

`api_key` is masked in the export. `client_ip` is masked. Everything else is verbatim. Requires `analyst` role or higher.

Same endpoint exists for DLP incidents: `GET /admin/incidents/export`.

### SQL access for analytics

For analysts who already have BI tools, give them a read-only Postgres role:

```sql
CREATE ROLE audit_reader LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE synapse_ai_gateway TO audit_reader;
GRANT USAGE ON SCHEMA public TO audit_reader;
GRANT SELECT ON audit_logs, dlp_incidents, teams TO audit_reader;
-- Explicitly NO grant on users, user_password_history, gateway_settings
```

They can wire that into Metabase / Superset / Tableau / DBT and build dashboards directly. The hashed columns mean even broad SELECT access doesn't expose prompt content.

### Webhook streaming

There is no built-in webhook output. If you need real-time forwarding to SIEM (Splunk, Sentinel, Datadog), the simplest pattern is a sidecar that polls `audit_logs` on a watermark (`WHERE id > last_seen_id`) and POSTs to the destination. A 50-line Python script handles it; build it as a dedicated component rather than hooking into the gateway.

---

## Related documents

- [docs/governance-model.md](governance-model.md) — what populates `team_name` and `api_key`
- [docs/dlp-configuration.md](dlp-configuration.md) — what populates `dlp_flagged` and `incident_id`
- [docs/hybrid-routing.md](hybrid-routing.md) — what `error` rows usually mean (upstream backend failure)
