# Security Remediation Plan — `quote-app`

**Based on:** SECURITY_AUDIT.md (10 June 2026)  
**Created:** 22 June 2026  
**Author:** Robbie

---

## Overview

This plan converts the audit findings into actionable phases, ordered by risk elimination per unit of effort. Each phase is independently shippable. Complete verification steps before closing a phase.

---

## Phase 1 — Stop Bleeding: Critical RCE & PII Leaks

**Target:** Complete within 1–2 days.  
**Goal:** Eliminate the two confirmed exploit paths (C1, C2) and establish the key trust baseline (C3).

---

### 1A. Sandbox the Jinja2 render (C1) — **~30 min**

**File:** `document_factory.py:857-858`

**Risk:** Any registered user can achieve RCE by embedding `{{ ''.__class__.__mro__[1].__subclasses__() }}` (or similar) inside an uploaded `.docx` template.

**Change:**

```python
# Before
from docxtpl import DocxTemplate

tpl = DocxTemplate(io.BytesIO(template_bytes))
tpl.render(context)

# After
from docxtpl import DocxTemplate
from jinja2.sandbox import SandboxedEnvironment

tpl = DocxTemplate(io.BytesIO(template_bytes))
jenv = SandboxedEnvironment()
tpl.render(context, jinja_env=jenv)
```

**Additional hardening:** After switching to `SandboxedEnvironment`, add a pre-render check that rejects any template whose raw extracted text contains `{{` or `{%` outside of placeholders the application itself injected. This prevents the class of payload that relies on literal Jinja2 syntax in the document body.

**Verification:** Upload a `.docx` containing `{{ ''.__class__ }}` as body text. The render should raise a `SecurityError` (or produce the literal string, not evaluate it) and not return subclass information.

---

### 1B. Fix IDOR on share/download endpoints (C2) — **~1 hour**

**File:** `main.py:399` (`/api/share/{doc_id}`) and `main.py:454` (`/api/download/{doc_id}`)

**Risk:** Any unauthenticated person with a doc ID can retrieve another business's customer PII (name, email, phone) plus the owner's email.

**Changes (in order of priority):**

1. **Drop the owner email from the share query.** Replace `select("*, users(email)")` with an explicit column list that excludes `users(email)`. Only return what the share page actually needs to render.

   ```python
   # Before
   .table("documents").select("*, users(email)").eq("id", doc_id)
   
   # After
   .table("documents").select(
       "id, customer_name, customer_email, customer_phone, cover_message, total_amount, currency, created_at"
   ).eq("id", doc_id)
   ```

2. **Confirm `documents.id` is UUIDv4** (not a serial integer). Run this against Supabase:
   ```sql
   SELECT column_name, data_type FROM information_schema.columns
   WHERE table_name = 'documents' AND column_name = 'id';
   ```
   If it is a serial, migrate to UUID immediately — a sequential ID makes the entire table enumerable.

3. **Add a `share_token` column (recommended follow-up).** Replace the primary key in share URLs with a separate `uuid_generate_v4()` share token. This keeps the primary key internal and allows individual share links to be revoked without touching the document record. This can ship in Phase 2 to avoid blocking Phase 1.

**Verification:** Authenticated as User A, create a document. Unauthenticated (or as User B), hit `/api/share/{doc_id}` and confirm the owner's email field is absent from the response.

---

### 1C. Confirm Supabase key type and fix key parsing (C3) — **~45 min**

**File:** `config.py:9`

**Tasks:**

1. **Identify whether `SUPABASE_KEY` is the service-role or anon key.** Check the Railway environment variable or Supabase dashboard. Document the result in a comment in `config.py`.

2. **Enable RLS as defense-in-depth regardless of key type.** Even if the service-role key is used, RLS provides a second layer that catches missing `.eq("user_id", ...)` filters (as demonstrated by C2). Enable RLS on `documents`, `users`, `user_configs`, and `subscriptions` at minimum.

3. **Fix the key parsing — remove the silent ASCII stripping:**

   ```python
   # Before
   SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().encode('ascii', 'ignore').decode('ascii')
   
   # After
   SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()
   ```

   Add a startup assertion:
   ```python
   assert settings.SUPABASE_KEY, "SUPABASE_KEY is required"
   ```

**Verification:** Confirm RLS is active on the four tables by running:
```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```
All four should show `rowsecurity = true`.

---

### Phase 1 Exit Criteria

- [ ] `SandboxedEnvironment` is used in all `DocxTemplate.render()` calls
- [ ] `/api/share` response no longer contains owner email
- [ ] `documents.id` type confirmed as UUID
- [ ] `SUPABASE_KEY` type documented, ascii-strip removed
- [ ] RLS enabled on core tables

---

## Phase 2 — Reduce Attack Surface: Upload Security & Container Hardening

**Target:** Complete within 3–5 days.  
**Goal:** Harden the file upload path (the primary threat vector alongside C1) and reduce container blast radius.

---

### 2A. Run container as non-root (H4) — **~30 min**

**File:** `Dockerfile`

This is the fastest win for the broadest blast-radius reduction, and it must be done before H2 has meaningful effect.

```dockerfile
# Add after the final apt/pip install step, before COPY
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app
```

Verify that LibreOffice conversion and Supabase storage calls still work under the non-root user after this change.

**Verification:** `docker run --rm quote-app whoami` must print `app`, not `root`.

---

### 2B. Validate file content, not just extension (H2) — **~3–4 hours**

**File:** `bot_manager.py` (~line 1015, `handle_document`)

Extension-only checks are trivially bypassed. Add structural validation before the bytes touch any parser.

**Changes:**

1. **OOXML structure check:** Validate the file is a real ZIP with Office content types before opening with python-docx or openpyxl.

   ```python
   import zipfile
   from io import BytesIO
   
   def _validate_ooxml(data: bytes, expected_content_type: str) -> bool:
       try:
           with zipfile.ZipFile(BytesIO(data)) as zf:
               names = zf.namelist()
               return "[Content_Types].xml" in names
       except zipfile.BadZipFile:
           return False
   ```

2. **Reject macros and external references:** Before passing to docxtpl, inspect the OOXML for `vbaProject.bin` (macros) and external relationship targets (`http://`, `file://`). Reject files that contain either.

   ```python
   def _has_dangerous_content(data: bytes) -> bool:
       try:
           with zipfile.ZipFile(BytesIO(data)) as zf:
               if "word/vbaProject.bin" in zf.namelist():
                   return True
               rels = zf.read("word/_rels/document.xml.rels").decode()
               if "http://" in rels or "file://" in rels:
                   return True
       except Exception:
           pass
       return False
   ```

3. **Restrict LibreOffice subprocess:** Add resource limits and disable network access for the `soffice` conversion call.

   ```python
   subprocess.run(
       ["soffice", "--headless", "--convert-to", "pdf", ...],
       timeout=60,
       env={**os.environ, "HOME": "/tmp/lo_home"},  # isolated home
       # Consider: preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, -1))
   )
   ```

**Verification:** Upload a file renamed `.docx` that is actually a PNG. It must be rejected before reaching python-docx. Upload a `.docx` with a `vbaProject.bin` entry — it must be rejected.

---

### Phase 2 Exit Criteria

- [ ] Container user confirmed non-root in production
- [ ] File content validated as valid OOXML before processing
- [ ] Macro and external-reference detection blocks malicious files
- [ ] LibreOffice runs with a restricted subprocess environment

---

## Phase 3 — Harden Infrastructure: Rate Limits & Dependencies

**Target:** Complete within 1 week.  
**Goal:** Close the unauthenticated cost-amplification vector and make builds reproducible.

---

### 3A. Move handshake rate limiting to a shared store (H1) — **~3–4 hours**

**File:** `main.py:341`

**Problem:** The in-memory `_handshake_last_sent` dict does not survive restarts or scale across replicas. Any redeploy resets the 60-second cooldown.

**Approach:** Use the existing `login_tokens` Supabase table as the pattern. Add a `handshake_attempts` table (or reuse `login_tokens` with a `type` column) to track per-email cooldowns server-side.

```sql
CREATE TABLE handshake_attempts (
    email TEXT PRIMARY KEY,
    last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```python
# In /handshake handler
async def _check_and_record_handshake(email: str) -> bool:
    """Returns True if allowed, False if rate-limited."""
    result = await asyncio.to_thread(
        lambda: supabase.table("handshake_attempts")
            .upsert({"email": email, "last_sent_at": "now()"}, on_conflict="email")
            .execute()
        # Add a WHERE last_sent_at < now() - interval '60 seconds' condition
    )
    # implement using RPC or conditional upsert
```

**Defer user creation:** Only create the `users` row when the magic link is clicked, not when `/handshake` is first called. This prevents junk row creation from unauthenticated POST spam.

**Verification:** Restart the server between two `/handshake` calls within 60 seconds to the same email. The second call must still be rate-limited.

---

### 3B. Pin dependencies and add pip-audit (H3) — **~1–2 hours**

**File:** `requirements.txt`

**Steps:**

1. Generate a pinned lockfile using `pip-tools`:
   ```bash
   pip install pip-tools
   pip-compile requirements.in --generate-hashes -o requirements.txt
   ```
   Rename the current `requirements.txt` to `requirements.in` (the unpinned source of truth).

2. Add `pip-audit` to the CI pipeline (GitHub Actions or Railway build hook):
   ```bash
   pip install pip-audit
   pip-audit -r requirements.txt
   ```

3. Configure Dependabot (`.github/dependabot.yml`):
   ```yaml
   version: 2
   updates:
     - package-ecosystem: pip
       directory: "/"
       schedule:
         interval: weekly
   ```

**Verification:** Run `pip install -r requirements.txt` in a fresh venv. All versions must be pinned to exact hashes. Run `pip-audit` — resolve any CVEs before proceeding.

---

### Phase 3 Exit Criteria

- [ ] Handshake rate limit survives a server restart
- [ ] User row not created until magic link click is confirmed
- [ ] All 19 dependencies pinned with hashes
- [ ] `pip-audit` passes in CI

---

## Phase 4 — Billing & Operational Hardening

**Target:** Complete within 2 weeks.  
**Goal:** Fix billing correctness issues and reduce operational risk from silently swallowed errors and PII in logs.

---

### 4A. Stripe webhook idempotency (M1) — **~2–3 hours**

**File:** `main.py:561`

Track processed Stripe event IDs to prevent duplicate application of subscription state changes.

```sql
CREATE TABLE stripe_events (
    event_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```python
async def _is_event_processed(event_id: str) -> bool:
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("stripe_events")
                .insert({"event_id": event_id})
                .execute()
        )
        return False  # inserted successfully — not a duplicate
    except Exception:  # unique constraint violation = duplicate
        return True

# In webhook handler:
if await _is_event_processed(event["id"]):
    return {"status": "already_processed"}
```

Also add timestamp comparison before applying `subscription.updated` events — a delayed delivery must not overwrite a newer state.

---

### 4B. Fix billing period math (M2) — **~1 hour**

**File:** `main.py:_billing_period_from_anchor`

Replace the calendar-month arithmetic with a direct read from the Stripe subscription item:

```python
# Replace _billing_period_from_anchor with a direct SDK read
sub = stripe.Subscription.retrieve(subscription_id, expand=["items"])
current_period_end = sub.items.data[0].current_period_end
```

Verify this is available in the currently pinned Stripe SDK version. If not, pin to a version that exposes it.

---

### 4C. Scrub PII from logs and Telegram notifications (M3) — **~2 hours**

**Files:** `main.py`, `bot_manager.py`, `ai_service.py`

- Replace `email` in log lines with a truncated or hashed identifier: `email[:3]***@***` or `hashlib.sha256(email.encode()).hexdigest()[:8]`.
- Replace `telegram_id` in logs with a consistent internal user UUID where possible.
- In `_notify_admin_of_failure`: strip customer contact details from the Telegram message body. Send only an internal user ID and error type.
- Confirm Sentry is initialised with `send_default_pii=False` (this is the default but should be explicit).

---

### 4D. Harden the `secure` cookie flag (M4) — **~30 min**

**File:** `main.py:_set_session_cookie`

Add a startup assertion rather than relying on the URL prefix check at cookie-set time:

```python
# In config.py or app startup
if os.getenv("ENV") == "production":
    assert settings.APP_URL.startswith("https://"), \
        "APP_URL must be https in production"
```

---

### 4E. Narrow broad `except Exception: pass` blocks (M6) — **~1–2 hours**

**Files:** `main.py`, `bot_manager.py`

- In `api_account` subscription-period lookup: replace `except Exception: pass` with `except stripe.StripeError` and log the specific error before falling back.
- For cleanup paths (storage `.remove()`, file delete): replace `except Exception: pass` with `except (StorageException, OSError) as e: logger.warning(...)`.
- Leave intentional no-op swallows only where the exception type is genuinely expected and handled.

---

### Phase 4 Exit Criteria

- [ ] Stripe event IDs tracked; duplicate events are no-ops
- [ ] `billing_period_from_anchor` replaced with direct Stripe SDK read
- [ ] No raw email addresses in log output (verified against sample log)
- [ ] `send_default_pii=False` explicitly set in Sentry init
- [ ] `APP_URL` https assertion present in production startup
- [ ] All `except Exception: pass` blocks narrowed to specific types

---

## Phase 5 — Code Quality & Architecture

**Target:** Ongoing, ship incrementally.  
**Goal:** Reduce future bug surface and make the codebase maintainable at scale.

---

### 5A. Extract the bot state machine (L2) — Medium effort

`bot_manager.py` at 1,868 lines mixes state transitions, handlers, storage, and notifications. The state machine (`HANDSHAKE → ONBOARDING → ONBOARDING_CURRENCY → ONBOARDING_TAX → ACTIVE → AWAITING_CONFIRMATION`) is implicit across many functions.

**Approach:** Extract a `BotStateMachine` class or module that owns the state enum, valid transitions, and guards. Handlers call `state_machine.transition(user, new_state)` rather than writing `bot_state` directly. This makes the "state lost on restart" defensive paths explicit and testable.

---

### 5B. Add targeted integration tests (L3) — High value

The Stripe period math (M2) and quota reservation logic are the two most consequence-bearing pieces of business logic with no test coverage. Add:

- A test for `_billing_period_from_anchor` with known anchor dates and subscription timestamps.
- A test for the `reserve_quota_slot` RPC under concurrent calls (confirm the advisory lock prevents double-booking).
- A test for the `/handshake` rate-limit path after the Phase 3 fix.

---

### 5C. Move email templates out of `main.py` (L6) — Low effort

The large HTML f-strings in `main.py` should move to `templates/email/welcome.html` etc. Use Jinja2 (already a dependency) to render them. This improves readability and allows designers to edit templates without touching application logic.

---

### 5D. Admin audit logging (M5) — Low effort

Add a simple `admin_actions` log table or append-only log file that records: timestamp, action name, affected user ID, operator identifier. No sensitive data in the log — IDs only.

---

### Phase 5 Exit Criteria

- [ ] State machine in dedicated module; all `bot_state` writes go through it
- [ ] Tests for billing period math, quota slot, and handshake rate limit
- [ ] Email templates in files, not f-strings
- [ ] Admin CLI logs every action to audit table

---

## Summary Table

| Phase | Findings | Effort | Priority |
|-------|----------|--------|----------|
| 1 — Critical fixes | C1, C2, C3 | 2–3 hours | Ship immediately |
| 2 — Upload & container | H2, H4 | 1 day | Ship this week |
| 3 — Rate limits & deps | H1, H3 | 1 day | Ship this week |
| 4 — Billing & ops | M1–M6 | 2–3 days | Ship next sprint |
| 5 — Code quality | L1–L6 | Ongoing | Incremental |

---

## Pre-Phase 1 Checklist (confirm before writing any code)

- [ ] Confirm `documents.id` column type (UUID or serial?) — affects C2 urgency
- [ ] Confirm `SUPABASE_KEY` is service-role or anon key — affects C3 scope
- [ ] Confirm current RLS status on core tables
- [ ] Identify all callers of `DocxTemplate.render()` in `document_factory.py` — there may be more than one call site
