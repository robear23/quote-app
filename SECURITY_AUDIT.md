# Security & Code Quality Audit — `quote-app`

**Repository:** github.com/robear23/quote-app
**Scope:** Read-only audit
**Date:** 10 June 2026
**Stack:** FastAPI + python-telegram-bot (webhook mode), Supabase, Google Gemini, Stripe, Resend, LibreOffice
**Size:** ~8,400 lines across 12 Python modules

---

## Executive summary

This is a competently built, coherent codebase. Authentication uses signed cookies and single-use magic-link tokens correctly, Stripe webhooks verify signatures, quota reservation uses an atomic Postgres RPC with advisory locking, and there is real care in the error handling and fallback paths.

The issues below are mostly about **trust boundaries** — what happens when a user (or someone guessing a URL) feeds the system hostile input. The most serious finding is a server-side template injection path through user-uploaded documents, followed by an unauthenticated data-exposure (IDOR) on the public share endpoints.

Findings are ordered by priority. Severity reflects likelihood × impact.

### Scope caveats

This review covered the Python application code and configuration. It did **not** cover the Supabase database schema / Row Level Security policies or the static frontend JavaScript in depth. Two findings (C2 and C3) hinge on details that live outside this repository — specifically whether `documents.id` is a UUID vs. a serial, and whether `SUPABASE_KEY` is the service-role or anon key. Those findings are written conditionally as a result.

---

## Findings at a glance

| ID | Severity | Title |
|----|----------|-------|
| C1 | Critical | Server-Side Template Injection → likely RCE via uploaded `.docx` |
| C2 | Critical | IDOR — any customer's quote + PII readable by guessing a document ID |
| C3 | Critical | Supabase key trust model / RLS unverified |
| H1 | High | Unauthenticated email enumeration + cost-amplification on `/handshake` |
| H2 | High | No file-content validation on uploads beyond extension + size |
| H3 | High | Dependencies are unpinned (`>=` lower bounds only) |
| H4 | High | Container runs as root; no non-root user |
| M1 | Medium | Stripe webhook does idempotency-free writes |
| M2 | Medium | `billing_cycle_anchor` period math can drift |
| M3 | Medium | PII written to logs and forwarded to Telegram/Sentry |
| M4 | Medium | `secure` cookie flag depends on `APP_URL` string prefix |
| M5 | Medium | Admin CLI has no audit trail and full data access |
| M6 | Medium | Broad `except Exception: pass` swallows real errors |
| L1–L6 | Low | Code quality / maintainability items |

---

## CRITICAL

### C1. Server-Side Template Injection → likely RCE via uploaded `.docx`

**Location:** `document_factory.py:857-858`, `ai_service.py:build_quote_template`

The onboarding flow takes a user-uploaded `.docx`, injects Jinja2 placeholders into it, stores it, and later renders it with:

```python
tpl = DocxTemplate(io.BytesIO(template_bytes))
tpl.render(context)
```

The uploaded document *becomes the Jinja2 template source*, and docxtpl uses a **plain (non-sandboxed) Jinja2 environment** by default — this was confirmed against the installed library. A user who embeds Jinja2 expressions in their template text (e.g. payloads of the `{{ ''.__class__.__mro__[1].__subclasses__() }}` family) gets arbitrary expression evaluation inside the container — which also runs LibreOffice and holds the Supabase key, Stripe key, Gemini key, and so on.

The barrier to entry is low: any registered user can upload a template, and registration is self-service. **This is the single most important item.**

**Fix:** Render with a sandboxed environment:

```python
from jinja2.sandbox import SandboxedEnvironment

tpl = DocxTemplate(io.BytesIO(template_bytes))
jenv = SandboxedEnvironment()
tpl.render(context, jinja_env=jenv)
```

The sandbox blocks attribute access to dunders and dangerous callables. Additionally, consider validating/escaping the AI-injected placeholders and rejecting templates whose raw text contains `{{` / `{%` outside the placeholders the application itself inserted.

---

### C2. IDOR — anyone can read any customer's quote + PII by guessing a document ID

**Location:** `main.py:399` (`/api/share/{doc_id}`), `main.py:454` (`/api/download/{doc_id}`)

Both endpoints look up the document purely by `doc_id`, with **no session check and no ownership check**:

```python
res = await ... .table("documents").select("*, users(email)").eq("id", doc_id).execute()
```

`/api/share` returns `customer_name`, `customer_email`, `customer_phone`, `cover_message`, totals, and the **business owner's email** (via the `users(email)` join). `/api/download` issues a signed Storage URL to the actual quote file. There is no authentication on either.

This is partly by design — share links are meant to be public. The problems are:

1. The join leaks the *business owner's* email to anyone with the link.
2. If `documents.id` is sequential or otherwise guessable, the entire table is enumerable.
3. Even with UUIDs, a forwarded share link exposes that customer's contact details indefinitely — `/api/share` itself has no expiry (only the downstream signed URL does, at 1 hour).

**Fix:**

- Drop `users(email)` from the share query, or select only non-sensitive columns explicitly rather than `select("*")`.
- Confirm `documents.id` is a UUIDv4 (not a serial). If it is, enumeration risk drops sharply, but the link is still a bearer token — prefer a separate unguessable `share_token` column over exposing the primary key.
- Consider an expiry on shares and an owner-controlled revoke flag.

---

### C3. Supabase key trust model / RLS is unverified

**Location:** `config.py:9`, used throughout via `database.supabase`

Every DB call goes through one server-side key. If that key is the **service-role key** (which bypasses Row Level Security), then RLS provides no defense — every query's correctness depends entirely on the `.eq("user_id", ...)` filters being present and correct in application code. Most are, but C2 shows what happens when one is missing. No RLS documentation was found in the repository to confirm which key is in use.

The line itself is also a smell:

```python
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().encode('ascii', 'ignore').decode('ascii')
```

The `encode('ascii', 'ignore')` silently strips non-ASCII bytes. A JWT is base64url (always ASCII), so this never helps with a valid key — but it would *silently corrupt* a mistyped or whitespace-laden key into a different string and produce confusing auth failures rather than a clear error.

**Fix:** Document which key this is. If it is the service-role key, treat every table query as security-sensitive and enable RLS as defense-in-depth regardless. Drop the ascii-stripping; use a plain `.strip()` and fail loudly on a malformed key.

---

## HIGH

### H1. Unauthenticated email enumeration + cost-amplification on `/handshake`

**Location:** `main.py:341`

`/handshake` takes an email, creates a user if absent, and sends mail. The rate limiter is a per-process in-memory dict (`_handshake_last_sent`) — it does **not** survive restarts and is **not shared across workers/replicas**. On Railway with more than one replica, or after any redeploy, the 60-second cooldown is trivially bypassed.

An attacker can drive Resend send volume (cost) and create unbounded junk user rows (each triggering `auto_apply_signup_bonus`). The endpoint returns the same `{"status": "check_email"}` regardless of whether the user exists, which is good for enumeration resistance — but user *creation* as a side effect of an unauthenticated POST is the deeper issue.

**Fix:** Move rate limiting to Supabase (a `login_attempts` table keyed by email with a timestamp, mirroring the existing `login_tokens` pattern) or another shared store. Consider a CAPTCHA or proof-of-work for account creation, and defer creating the user row until the magic link is actually clicked.

---

### H2. No file-content validation on uploads beyond extension + size

**Location:** `bot_manager.py` ~line 1015 (`handle_document`)

Uploads are gated only on a `.docx` / `.xlsx` filename suffix and a 20 MB cap. The bytes then flow into python-docx, openpyxl, docxtpl, **and LibreOffice** (`soffice --convert-to pdf`). This is a wide attack surface — LibreOffice has a long history of file-parsing CVEs, and Office Open XML supports external-entity and embedded-object tricks. Combined with C1, a malicious "docx" is the primary threat vector in the app.

**Fix:** Validate the actual zip/OOXML structure (not just the extension) before processing. Run LibreOffice conversion in a locked-down subprocess (no network, restricted filesystem, dedicated unprivileged user, ideally a separate sandbox), and set resource limits. Strip macros and external references.

---

### H3. Dependencies are unpinned (`>=` lower bounds only)

**Location:** `requirements.txt` — all 19 dependencies use `>=`

For example `stripe>=8.0.0`, `fastapi>=0.100.0`. Builds are non-reproducible and a future transitive release can silently change behavior or introduce a regression/compromise. The code already shows scar tissue from this — the Stripe SDK v8 `current_period_end` removal, handled by `_billing_period_from_anchor`, is exactly the kind of breakage pinning prevents.

**Fix:** Pin exact versions and commit a lockfile (`pip-tools`, `uv`, or `poetry`). Add Dependabot or `pip-audit` to CI.

---

### H4. Container runs as root; no non-root user

**Location:** `Dockerfile`

Nothing creates or switches to a non-root user, so the app — including the LibreOffice subprocess that parses untrusted files — runs as root. This magnifies the impact of C1 and H2 considerably.

**Fix:** Add a `useradd` step and `USER app`. Combined with H2 sandboxing, this meaningfully reduces blast radius.

---

## MEDIUM

### M1. Stripe webhook does idempotency-free writes

**Location:** `main.py:561` and the `_handle_*` handlers

Signature verification is correct, but Stripe re-delivers events and can send them out of order. Handlers upsert state unconditionally; a delayed `subscription.updated` could clobber a newer `subscription.deleted`. Record processed event IDs and/or compare event timestamps before applying.

### M2. `billing_cycle_anchor` period math can drift

**Location:** `main.py:_billing_period_from_anchor`

Rebuilding the period by adding calendar months from the anchor is a workaround for the SDK change and will diverge from Stripe's real period on proration, plan changes, or pauses. Prefer reading the period from the subscription *item* (`sub.items.data[0].current_period_end` in newer SDKs) rather than recomputing.

### M3. PII written to logs and forwarded to Telegram/Sentry

Multiple `logger.info` / `logger.error` calls include email addresses, Telegram IDs, and full tracebacks (e.g. `api_account` logs email + telegram_id; `_notify_admin_of_failure` sends customer name + tracebacks to a Telegram chat). Under GDPR this is personal data in logs and a third-party chat. Reduce to IDs, and scrub before sending to Sentry (confirm `send_default_pii=False`, which is the default).

### M4. `secure` cookie flag depends on `APP_URL` string prefix

**Location:** `main.py:_set_session_cookie`

`secure=settings.APP_URL.startswith("https")` is correct in production but means a misconfigured `APP_URL` silently ships session cookies over HTTP. Add an explicit assertion that production `APP_URL` is https.

### M5. Admin CLI has no audit trail and full data access

**Location:** `admin.py`

Reasonable as an internal tool, but it reads all users, quotes, and downloads templates with the service key and no logging of who ran what. If it ever runs anywhere shared, add audit logging and keep it off production hosts.

### M6. Broad `except Exception: pass` swallows real errors

Many spots (storage `.remove()`, cookie deletes, file cleanup) silently swallow everything. Mostly intentional for non-fatal cleanup, but a few — e.g. the subscription-period lookup in `api_account` (`except Exception: pass`) — hide real DB errors behind a "free tier" fallback. Narrow these to expected exception types.

---

## LOW / Code quality

- **L1.** Duplicate comment line in `generate_and_send_quote` (`# Send document directly...` appears twice, `bot_manager.py` ~line 583). Cosmetic.
- **L2.** `bot_manager.py` is 1,868 lines mixing the onboarding state machine, handlers, storage, and notifications. The state machine (`HANDSHAKE → ONBOARDING → ... → ACTIVE`) is implicit across functions; extracting it into a documented module/enum would cut bugs in the "state lost on restart" paths already being handled defensively.
- **L3.** No automated test suite for the web/bot layers — the `tests/` and `*_test_runner.py` files are template-evaluation scripts, not unit/integration tests. The Stripe period math (M2) and quota logic especially warrant tests.
- **L4.** The `_handshake_last_sent` "prune stale entries" loop is O(n) on every request — fine at low volume, but it is a homegrown cache that should be a real store (see H1).
- **L5.** Repeated inline `from subscription_service import ...` inside functions (circular-import avoidance). Works, but restructuring imports would be cleaner.
- **L6.** Mixed concerns: `main.py` holds large HTML email templates as f-strings. Move these to template files.

---

## Recommended remediation order

1. **C1** — sandbox the Jinja2 render. Small change, removes an RCE path. Do this first.
2. **C2** — strip `users(email)` from the share query and confirm `documents.id` is a UUID. Quick, stops the PII leak.
3. **C3** — confirm the Supabase key type and enable RLS as defense-in-depth.
4. **H2 + H4** — run LibreOffice/uploads as a non-root, sandboxed process.
5. **H1** — move handshake rate-limiting to a shared store; defer user creation until link click.
6. **H3** — pin dependencies and add `pip-audit`.
7. Then the Medium items, starting with **M1 / M2** (they affect billing correctness).

---

## Next steps to firm up conditional findings

To convert C2 and C3 from conditional to confirmed, the following would help:

- Whether `SUPABASE_KEY` is the **service-role** or **anon** key.
- The `documents` table definition (specifically the type of the `id` column).
- The current RLS policies on `documents`, `users`, `user_configs`, and `subscriptions`.
