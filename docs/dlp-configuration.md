# DLP configuration

The gateway runs a regex-based DLP scan on both sides of every request: against the user's prompt before forwarding to the LLM, and against the LLM's response before returning to the client.

This document covers how the engine works, how to add patterns specific to your jurisdiction, and how to tune false positives.

---

## How the regex engine works

A single dictionary of **patterns** drives the engine. Each pattern is a row in the `dlp_patterns` table with four fields:

| Field | Meaning |
|---|---|
| `name` | Unique short identifier (e.g. `us_ssn`, `credit_card`). Used in audit logs and incident reports. |
| `pattern` | A Python regex string. Compiled with `re.IGNORECASE`. |
| `severity` | `Critical` / `High` / `Medium` / `Low`. Affects incident reporting only — not the routing decision. |
| `action` | What to do on a match: `block` (HTTP 400), `redact` (substitute and forward), or `alert` (log and forward). |

### Per-request flow

1. The gateway calls `re.findall(pattern, text)` for every **enabled** pattern.
2. Every match produces a finding: `{pattern, severity, action}`.
3. The strongest action across all matches wins: **`block > redact > alert`**.
4. If `block`: reject the request with `400`, write an audit row (`status=blocked_dlp`), persist a `DLPIncident` row with `action=block`.
5. If `redact`: for every redact-action pattern that matched, replace the matched text with `[REDACTED:<pattern_name>]` in the user message. Forward the modified message. Log incident with `action=redact`.
6. If `alert`: forward unchanged. Log incident with `action=alert`.

The same engine runs on the LLM response — but **response-side only supports `block`** (action `redact` and `alert` on a response are not meaningful: by the time the model has produced the tokens, the leak has happened).

### Where patterns live

- **Seed** (first-run only): `backend/dlp_patterns.json`, loaded by `seed.py` when the database is empty.
- **Runtime**: the `dlp_patterns` table in Postgres. Manage via the admin UI (**DLP Patterns** page) or the `/admin/dlp-patterns/*` REST endpoints.
- **State**: compiled patterns are cached in process memory by `state.dlp_patterns` and refreshed on every admin mutation.

### The default pattern pack

The default `dlp_patterns.json` ships a **jurisdiction-diverse starter set** —
not a production-ready pack for any single country. It is designed to be useful
on first boot and to demonstrate the engine, but you should expect to customise
it for your own regulatory context before going live.

| Name | Severity | Action | Purpose |
|---|---|---|---|
| `credit_card` | Critical | `block` | Visa / Mastercard / Amex PANs |
| `us_ssn` | Critical | `block` | US Social Security Number |
| `uk_nino` | Critical | `block` | UK National Insurance Number |
| `iban` | High | `block` | Generic IBAN (any country) |
| `aws_access_key` | High | `block` | Leaked AWS access key IDs |
| `phone_e164` | Medium | `block` | International E.164 phone numbers |
| `email` | Low | `alert` | Personal email addresses (alert-only by default to avoid false-positive blocks) |

For locale-specific identifiers — Pakistani CNIC, Indian Aadhaar, Canadian SIN,
French INSEE, etc. — copy the relevant row from [Example patterns by sector](#example-patterns-by-sector)
below into your own `dlp_patterns.json`, or add them via the admin UI after first
boot. Point `DLP_PATTERNS_FILE` at a custom JSON file to override the default
pack entirely for a fleet deployment.

---

## Adding a custom PII category

Three equivalent ways. Pick whichever fits your workflow.

### Via the admin UI

Sidebar → **DLP Patterns** → **Add pattern**. Fill in name / regex / severity / action. The dialog has a small **test** field where you can paste sample text and see what the regex matches before saving — a client-side check that uses the browser's JavaScript regex engine. Note that JavaScript regex is *not identical* to Python regex (lookbehind support differs, character classes have edge cases); for production patterns, validate end-to-end with a real chat completion (see [Testing your patterns](#testing-your-patterns) below).

### Via the REST API

```bash
curl -X POST http://localhost:8080/admin/dlp-patterns \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ssn_us",
    "pattern": "\\b\\d{3}-\\d{2}-\\d{4}\\b",
    "severity": "Critical",
    "action": "block"
  }'
```

Backslashes must be JSON-escaped (so `\b` in regex becomes `\\b` in JSON).

### Via `dlp_patterns.json` (first-run seed only)

If you're standing up a fresh deployment, edit `backend/dlp_patterns.json` *before* the first start. The shape:

```json
[
  {
    "name": "ssn_us",
    "pattern": "\\b\\d{3}-\\d{2}-\\d{4}\\b",
    "severity": "Critical",
    "action": "block"
  }
]
```

This only seeds an *empty* database. If `dlp_patterns` already has rows, the file is ignored. After the first start, manage patterns via the API/UI.

---

## Example patterns by sector

These are starting points. Validate against your own jurisdiction's exact format rules — local variation matters and the regex below assumes common formats only.

### Financial services

| Name | Pattern | Severity | Default action | Notes |
|---|---|---|---|---|
| `credit_card` | `\b(?:4[0-9]{12}(?:[0-9]{3})?\|5[1-5][0-9]{14}\|3[47][0-9]{13})\b` | Critical | `block` | Visa / Mastercard / Amex PAN. Already shipped in the default pack. |
| `cvv` | `\b(?:cvv\|cvc\|cv2)[:\s]*\d{3,4}\b` | Critical | `block` | Card security code. Case-insensitive by default. |
| `iban` | `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b` | High | `block` | Generic IBAN (any country). |
| `account_no` | `(?:account\|a\/c\|acct)[^\d]{0,10}(\d{10,16})` | High | `block` | Context-anchored — requires the word "account" nearby to limit false positives. |
| `routing_number_us` | `\b\d{9}\b` | Medium | `alert` | US bank routing numbers are 9 digits — extremely ambiguous, hence `alert` rather than `block`. |

### Healthcare

| Name | Pattern | Severity | Default action | Notes |
|---|---|---|---|---|
| `us_ssn` | `\b(?!000\|666\|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b` | Critical | `block` | US Social Security Number, with the well-known invalid-prefix exclusions. Already shipped in the default pack. |
| `mrn` | `\b(?:mrn\|medical record)[:\s#]*[\w-]{6,12}\b` | High | `redact` | Context-anchored MRN. Format varies by EHR; tune per your records. |
| `npi` | `\b\d{10}\b` | Low | `alert` | National Provider Identifier — 10 digits, collides with phone numbers; alert mode lets you observe rather than break workflows. |
| `dob_iso` | `\b(19\|20)\d{2}-\d{2}-\d{2}\b` | Medium | `alert` | ISO-format date of birth — also matches non-birthday dates, so monitor before tightening. |
| `email` | `\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b` | Low | `alert` | Patient email. Already shipped. |

### Government / public sector

| Name | Pattern | Severity | Default action | Notes |
|---|---|---|---|---|
| `passport_us` | `\b[A-Z]\d{8}\b` | High | `block` | US passport book number (post-2007 format). |
| `driver_license_state` | varies — write one per state | Medium-High | `block` | US driver's licence formats differ by state; ship per-state patterns rather than one generic. |
| `ein` | `\b\d{2}-\d{7}\b` | Medium | `block` | US Employer Identification Number. |
| `uk_nino` | `\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b` | Critical | `block` | UK National Insurance Number. Already shipped in the default pack. |
| `aadhaar_in` | `\b\d{4}\s?\d{4}\s?\d{4}\b` | Critical | `block` | Indian Aadhaar — 12 digits in groups of 4. Verify with Verhoeff checksum at the application layer for confirmed hits. |
| `cnic_pk` | `\b\d{5}-\d{7}-\d{1}\b` | Critical | `block` | Pakistani national ID. |
| `sin_ca` | `\b\d{3}-\d{3}-\d{3}\b` | Critical | `block` | Canadian Social Insurance Number. Validate with Luhn at the application layer for confirmed hits. |
| `insee_fr` | `\b[12]\d{2}(?:0[1-9]\|1[0-2])(?:2[AB]\|\d{2})\d{3}\d{3}\d{2}\b` | Critical | `block` | French INSEE / national identification number. |

---

## Testing your patterns

There are three levels of validation.

### 1. Syntax test (in the admin UI)

The pattern-create dialog has a regex tester:

> Pattern: `\b\d{3}-\d{2}-\d{4}\b`
> Test input: `my ssn is 123-45-6789`
> Result: `1 match(es): 123-45-6789`

This is a JavaScript regex run in the browser. It catches syntax errors and obvious matching mistakes. It does **not** guarantee parity with Python's regex engine — they differ on a handful of edge cases (lookbehind assertions, some character class escapes). For production patterns, follow up with the end-to-end check below.

### 2. End-to-end test (via the chat API)

There's no separate test endpoint. Use a normal chat completion against a non-production team key with the text you want to test:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer <TEST_TEAM_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:latest",
    "messages": [{
      "role": "user",
      "content": "Please update my record. SSN: 123-45-6789. Thanks."
    }]
  }'
```

If the pattern is `action=block` and matches: response is `400` with `incident_id` and `findings`:

```json
{
  "detail": {
    "error": "Request blocked by DLP policy",
    "incident_id": "f0a4...c923",
    "findings": [
      {"pattern": "ssn_us", "severity": "Critical", "action": "block"}
    ]
  }
}
```

If `action=redact`: the request completes with `200` and the model's reply is based on the redacted text. Look at the `dlp_incidents` table for proof — there'll be a row with `source=user_input`, `action=redact`, and the matched pattern recorded.

If `action=alert`: completes normally. The incident row is the only sign that anything fired.

### 3. Audit-log review

After a few real requests, query:

```sql
SELECT pattern_name, COUNT(*) AS hits
FROM (
    SELECT jsonb_array_elements_text(patterns::jsonb) AS pattern_name
    FROM dlp_incidents
    WHERE timestamp > NOW() - INTERVAL '24 hours'
) p
GROUP BY pattern_name
ORDER BY hits DESC;
```

This tells you which patterns are firing and how often — your raw input for tuning.

---

## Tuning false-positive rates

Three knobs to turn, in order of cheapest to most disruptive.

### 1. Change the action, not the regex

If a pattern fires often and most hits are false positives, switch it from `block` to `alert` first. You'll still see the incidents in `dlp_incidents` and on the **DLP Incidents** page, but no traffic is rejected. After a week of observation, you have data on what the pattern actually catches.

If most incidents look like the *kind* of leak you care about: switch back to `block`.
If most look benign: tighten the regex.

### 2. Context-anchor the pattern

A bare 10-digit number is too broad — it matches phone numbers, routing numbers, NPIs, account numbers, lottery codes. Adding a context word in front cuts most of the noise:

| Loose | Tighter |
|---|---|
| `\b\d{10}\b` | `(?:account\|acct\|a\/c)[^\d]{0,10}(\d{10})` |
| `\b\d{4}-\d{4}-\d{4}-\d{4}\b` | `(?:card\|cc\|payment)[^\d]{0,20}(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})` |

This is the approach the shipped `account_no` pattern takes (`(?:account|a\/c|acct)[^\d]{0,10}(\d{10,16})`).

### 3. Use checksum validation at a higher layer

Some PII formats have a checksum (Luhn for card numbers, Verhoeff for Aadhaar, MOD-11 for SSN). Regex can't verify those, so a regex-only match has a non-trivial false-positive rate even at perfect syntax.

If you need higher precision than regex gives you, the architecture supports it: write a small validator in `routers/chat.py`'s `_run_dlp` (or fork the function), have it call into `luhn`/`verhoeff` libraries on candidate matches, and downgrade non-validating matches to `alert` or drop them. This is the right place to add semantic validation — but it's beyond what ships in the default engine.

### What "good" looks like

A healthy install fires hundreds of `alert`-action incidents a week and only a handful of `block`-action ones. If your block rate is creating support tickets, you've tuned too tight. If the alert rate is zero, your patterns aren't matching what you think they are.

---

## Related documents

- [docs/governance-model.md](governance-model.md) — keys, prompts, rate limits
- [docs/audit-logging.md](audit-logging.md) — what's in `dlp_incidents` and how to query
- `backend/dlp_patterns.json` — the seed file
