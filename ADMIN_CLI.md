# Admin CLI

A command-line tool for diagnosing and fixing user issues in production.

## Setup

Run commands from the Quote App directory with the virtual environment active:

```bash
# Windows
.venv\Scripts\activate

# Then run any command
python admin.py <command>
```

Your `.env` file must be present with valid `SUPABASE_URL` and `SUPABASE_KEY` — the CLI connects to Supabase directly.

---

## Commands

### `list` — Overview of all users

```bash
python admin.py list
```

Shows every registered user with their email, bot state, subscription tier, Telegram ID, and join date. Good starting point when a user reports an issue — check their `bot_state` column first.

**Bot states:**

| State | Meaning |
|---|---|
| `HANDSHAKE` | Signed up but hasn't opened Telegram yet |
| `ONBOARDING` | In Telegram but hasn't uploaded a template |
| `ONBOARDING_CURRENCY` | Waiting to select their currency |
| `ONBOARDING_TAX` | Waiting to enter their VAT/tax rate |
| `AWAITING_FORMAT` | Template processed, choosing DOCX or XLSX |
| `ACTIVE` | Fully set up, can generate quotes |
| `AWAITING_CONFIRMATION` | Mid-quote, waiting for user to confirm or edit |

---

### `user` — Full profile for one user

```bash
python admin.py user rob@example.com
```

Shows everything about that user in one place:

- **ID & Telegram ID** — useful for cross-referencing logs
- **Bot state** — where they are in the flow
- **Pending quote** — if they're stuck in `AWAITING_CONFIRMATION`, shows the customer name and line items that are waiting
- **Config** — business name, currency, VAT rate, preferred format (DOCX/XLSX), template file path, brand colours
- **Recent quotes** — last 5 generated quotes with dates and totals
- **Subscription** — tier, status, and period end date

---

### `quotes` — Full quote history

```bash
python admin.py quotes rob@example.com
```

Shows the last 10 generated quotes with every line item, quantity, unit price, and totals. Useful when a user says a quote had the wrong price or missing items.

---

### `template` — Download a user's template files

```bash
python admin.py template rob@example.com
```

Downloads two files into `admin_downloads/`:

- `quote_template.docx` — the Jinja2 template the app fills in when generating quotes
- `blank_template.docx` — the original file the user uploaded during onboarding

Open these in Word to inspect the placeholders, check if a table row is broken, or verify the layout looks correct.

---

### `reset` — Unstick a user

```bash
python admin.py reset rob@example.com
```

Resets the user's `bot_state` to `ACTIVE` and clears any pending quote. Use this when:

- A user is stuck in `AWAITING_CONFIRMATION` and can't get out
- A user reports the bot stopped responding mid-flow
- You've manually fixed something and need to return them to a working state

The command shows their current state and asks for confirmation before making any changes.

---

## Common Scenarios

**User says the bot isn't responding:**
1. `python admin.py user their@email.com` — check `bot_state`
2. If stuck in `AWAITING_CONFIRMATION`: `python admin.py reset their@email.com`

**User says their generated quote looks wrong (wrong prices, missing items):**
1. `python admin.py quotes their@email.com` — see what was actually generated
2. `python admin.py template their@email.com` — download and inspect their template

**User completed onboarding but quotes aren't generating:**
1. `python admin.py user their@email.com` — check that `template_docx_path` is set in their config
2. If missing, they need to go through `/restart` in Telegram to re-upload their template

**User hasn't linked Telegram after signing up:**
1. `python admin.py user their@email.com` — `Telegram ID` will show `—`
2. Their state will be `HANDSHAKE` — they need to click the Telegram link from their welcome email
