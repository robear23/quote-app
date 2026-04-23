Run the quote generation test suite against the templates in `test_templates/`.

## Usage

- `/run-quote-tests` — creates 10 new synthetic templates and runs the full pipeline
- `/run-quote-tests existing` — fetches up to 10 random real user templates from Supabase and tests those
- `/run-quote-tests 06 08 10` — runs only the specified synthetic templates (match by number prefix)

## Arguments

`$ARGUMENTS` is optional. It can be:
- Empty → run all 10 synthetic templates (`--mode new`)
- The word `existing` → run against real user templates from Supabase (`--mode existing`)
- Space-separated template numbers (e.g. `04 06 08 10`) → run a filtered subset of synthetic templates

## Steps

1. **Build the run command** based on `$ARGUMENTS`:

   If `$ARGUMENTS` is `existing`:
   ```
   python test_runner.py --mode existing
   ```

   If `$ARGUMENTS` contains template numbers (digits), filter synthetic templates:
   ```
   python -c "
   import test_runner
   ids = '$ARGUMENTS'
   test_runner.TEMPLATES = [t for t in test_runner.TEMPLATES if any(t['id'].startswith(p) for p in ids.split())]
   test_runner.main()
   "
   ```

   If `$ARGUMENTS` is empty, run all synthetic templates:
   ```
   python test_runner.py
   ```

2. **Run in the background** using `run_in_background: true`. The test suite takes 2–10 minutes depending on Gemini rate limits.

3. **When the background task completes**, read the last ~40 lines of its output file to get the summary table, then read `test_results/quote_test_analysis.md` for the full per-template breakdown.

4. **Report results** as a markdown table showing each template's score, status, and any Client Readiness issues flagged. Note any pipeline errors (quota exhaustion, brand DNA failures) separately from scoring failures.

5. **Highlight regressions** — if any template that previously passed now shows WARN or ERROR, call it out prominently.

## Context

- Templates are in `test_templates/`, generated quotes in `test_generated/`, report in `test_results/quote_test_analysis.md`
- Scoring is out of 50: Placeholder Accuracy (10) + Line Items Integrity (10) + Calculation Accuracy (10) + Template Fidelity (10) + Client Readiness (10)
- Client Readiness is scored by Gemini qualitative review; if Gemini quota is exhausted it falls back to 5/10
- Pipeline errors (brand DNA failure, `build_quote_template returned None`) score 0/50 and are usually caused by Gemini quota exhaustion on the free tier
- The working directory is `d:\Antigravity\Quote App`
