---
name: run-quote-tests
description: Run the quote generation test suite. Use when the user asks to run quote tests, check the pipeline, test templates, run /run-quote-tests, or mentions testing with specific template numbers (e.g. "04 06") or "existing" for real Supabase templates.
version: 1.1.0
---

# Quote Generation Test Suite

Tests the full pipeline for each template: blank DOCX creation → brand DNA extraction → Jinja2 template mapping → quote rendering → 5-dimension scoring.

## Template Field Styles

Templates are generated in three field-style modes to stress-test the AI's field detection ability. Not every template uses `[bracket]` markers — the AI must detect and map fields from context, labels, or sample text alone.

| Style | Templates | How fillable fields appear in the blank |
|---|---|---|
| `brackets` | 01, 04, 08 | `[FieldName]` explicit placeholders — easiest for AI |
| `labels` | 02, 05, 07, 10 | Label column present, value cell **blank** — AI infers from adjacent label |
| `sample` | 03, 06, 09 | Realistic sample text (e.g. "QT-1001", "ABC Company Ltd") — AI must detect from document structure |

## Scoring (50 points total)

| Dimension | Points | What is checked |
|---|---|---|
| Placeholder Accuracy | 10 | No leftover `{{ }}` Jinja2 or `[bracket]` markers in final output |
| Line Items Integrity | 10 | All expected line item descriptions appear in the rendered quote |
| Calculation Accuracy | 10 | Subtotal, tax, and grand total values are mathematically correct |
| Template Fidelity | 10 | Business name, address, and customer name are all present |
| Client Readiness | 10 | Gemini qualitative review — would this embarrass a client? |

**Status thresholds:** ≥35 → ✅ PASS · 20–34 → ⚠️ WARN · <20 → ❌ FAIL

## Running the Tests

### Parse arguments from `$ARGUMENTS`

- **Empty** → run all 10 synthetic templates
- **`existing`** → fetch up to 10 real user templates from Supabase Storage
- **Space-separated numbers** (e.g. `04 06 09`) → run only those synthetic templates

### Build and execute the command

**All 10 templates (no arguments):**
```
python test_runner.py
```

**Real Supabase templates:**
```
python test_runner.py --mode existing
```

**Filtered subset (e.g. `04 06 09`):**
```python
python -c "
import test_runner
ids = '04 06 09'
test_runner.TEMPLATES = [t for t in test_runner.TEMPLATES if any(t['id'].startswith(p) for p in ids.split())]
test_runner.main()
"
```

### Execution notes

- Run with `run_in_background: true` — the full suite takes 2–10 minutes depending on Gemini quota
- Working directory: `d:\Antigravity\Quote App`

### Reading results

When the background task completes:
1. Read the last ~40 lines of task output for the console summary table
2. Read `test_results/quote_test_analysis.md` for the full per-template breakdown

### Reporting

Present results as a markdown table: **Template | Field Style | Plac. | Line. | Calc. | Fid. | Client | Total | Status**

Call out separately:
- Any template scoring <35 (WARN or FAIL) — explain which dimension failed
- Pipeline errors (brand DNA failure, `build_quote_template returned None`) — usually Gemini quota exhaustion, not a code bug
- **Regressions** — if a previously-passing template now WARN/FAILs, highlight prominently
- Client Readiness scores (qualitative via Gemini) — expected to be low (2–4/10) for ghost fields and validity inconsistencies; only flag if a new issue appears

## File Locations

| Path | Contents |
|---|---|
| `test_templates/` | `*_blank.docx` and `*_processed.docx` per template |
| `test_generated/` | `*_generated.docx` — final rendered quotes |
| `test_results/quote_test_analysis.md` | Full scoring report (overwritten each run) |

## Known Baseline Issues (not regressions)

These are structural limitations documented in the strategic analysis — do not flag as new failures:

- **Ghost fields** (`[Status]`, `[Project Code]`, `[Department]`) — blank in all outputs; no user input populates them
- **Validity mismatch** — `valid_until` hardcoded to +30 days in `document_factory.py` vs "Valid for 14 days" footer text
- **Extra columns empty** (`Weight`, `Seats`, `Part No`) — `line_items` schema only has `description/qty/unit_price`
- **`labels`/`sample` style templates** will naturally score lower on Client Readiness if the AI fails to detect unmarked fields — this is expected and indicates a genuine detection gap
