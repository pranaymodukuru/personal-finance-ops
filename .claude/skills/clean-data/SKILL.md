---
name: clean-data
description: Clean raw transaction data — dedup, normalize, validate, flag internal transfers, assign subcategories — and produce output/processed/cleaned_cumulative.csv for the dashboard
---

Clean `output/raw/cumulative.csv` and produce `output/processed/cleaned_cumulative.csv`, ready for the dashboard.

> **CRITICAL: `output/raw/cumulative.csv` is the raw source of truth and MUST NEVER be modified.**
> All fixes, patches, and corrections go into `output/processed/cleaned_cumulative.csv` only.
> If any step instructs you to write to `cumulative.csv`, do NOT do it — skip that write or apply the fix only in memory before writing the cleaned output.

The cleaning script (`src/cleaner.py`) handles deduplication, text normalization, type coercion, validation, internal transfer flagging, and subcategory assignment. It always prints a JSON report as its last stdout line. The skill parses that JSON to drive the interactive workflow below.

## Steps

### 1. Pre-flight check
Run:
```bash
python3 -c "from pathlib import Path; p=Path('output/raw/cumulative.csv'); print('exists' if p.exists() else 'missing')"
```
If the output is `missing`, tell the user to run `/process-statements` first and stop.

### 2. Overwrite guard
Check if `output/processed/cleaned_cumulative.csv` exists:
```bash
python3 -c "from pathlib import Path; print('exists' if Path('output/processed/cleaned_cumulative.csv').exists() else 'missing')"
```
If `exists`, automatically back it up — no confirmation needed:
```bash
cp output/processed/cleaned_cumulative.csv output/cleaned_cumulative.backup.csv
```
Inform the user: "Backed up existing `cleaned_cumulative.csv` → `cleaned_cumulative.backup.csv`"

### 3. Dry-run — preview the changes
Run the cleaner in report-only mode (does NOT write any file):
```bash
python -m src.cleaner --report-only 2>&1
```
The **last line** of stdout is the JSON report. Parse it with:
```bash
python -m src.cleaner --report-only 2>&1 | python3 -c "import sys,json; lines=sys.stdin.read().strip().splitlines(); r=json.loads(lines[-1]); print(json.dumps(r, indent=2))"
```

Show the user a human-readable preview table:

| Metric | Value |
|---|---|
| Raw rows | `rows.raw` |
| Duplicates removed | `rows.duplicates_removed` |
| Rows after dedup | `rows.after_dedup` |
| Auto-reclassified | `reclassified.count` |
| Internal transfers to flag | `is_internal_transfer.total` |
| Subcategory unique count | `subcategory.unique` |
| Unclassified | `subcategory.unclassified` |
| Anomalies found | `anomalies.total_anomalies` |

If `reclassified.count > 0`, show the auto-fixes in a collapsed table:

| Receiver | From | To |
|---|---|---|
| `change.receiver` | `change.from` | `change.to` |

Inform the user: "These categories were auto-corrected based on known patterns. To add or adjust rules, edit `_RECLASSIFY_RULES` in `src/cleaner.py`."

### 4. Anomaly review (only if anomalies exist)
If `anomalies.total_anomalies > 0`, handle each type interactively before writing:

**`sign_mismatch_debit` / `sign_mismatch_credit`**: Show the affected rows in a table (date, receiver, amount, type). Ask the user:
- (a) Auto-fix: swap the `type` field to match the sign — the fix is applied only when writing `cleaned_cumulative.csv`; `cumulative.csv` is NOT touched
- (b) Leave as-is (may be legitimate)
- (c) Abort

**`zero_amount`**: Show the rows. Ask whether to drop them or keep them. The decision is applied only in `cleaned_cumulative.csv`; `cumulative.csv` is NOT touched.

**`unknown_category`**: Show the rows. Suggest the closest valid category from: `food, transport, utilities, entertainment, healthcare, shopping, income, savings, transfer, fees, other`. Ask the user to confirm or override. Corrections are applied only in `cleaned_cumulative.csv`.

**`category_suspect`**: Show the flagged rows in a table (date, receiver, description, current_category, suggested_category). Ask the user for each group of same-pattern suspects:
- (a) Apply suggestion — correction goes into `cleaned_cumulative.csv` only; `cumulative.csv` is NOT touched
- (b) Keep as-is (current category is intentional)
- (c) Set a different category manually

If the user chooses (a) for a pattern that recurs often, suggest they add a rule to `_RECLASSIFY_RULES` in `src/cleaner.py` so future runs auto-correct it without manual intervention.

**`future_date`**: Show the rows. Inform the user these are dated beyond today. Ask whether to keep them or flag them by appending `[future-dated]` to their description — the flag is written only in `cleaned_cumulative.csv`; `cumulative.csv` is NOT touched.

Wait for user responses before proceeding to step 5. If the user says "proceed as-is" or there are no anomalies, move straight to step 5.

### 5. Write the cleaned file
```bash
python -m src.cleaner 2>&1
```
Parse the JSON from the last line. Verify:
- `written` is `true`
- `rows.final` matches `rows.after_dedup` from the dry-run

### 6. Final summary
Display the results:

| Metric | Value |
|---|---|
| Raw rows | `rows.raw` |
| Duplicates removed | `rows.duplicates_removed` |
| Final rows | `rows.final` |
| Internal transfers flagged | `is_internal_transfer.total` |
| External transactions | `is_internal_transfer.external` |
| Subcategories assigned | `subcategory.unique` unique labels |
| Unclassified | `subcategory.unclassified` |
| Anomalies | `anomalies.total_anomalies` |
| Output | `output/processed/cleaned_cumulative.csv` |

Then tell the user:
> "The dashboard reads `output/processed/cleaned_cumulative.csv` automatically. Run `/start-dashboard` to view results with full subcategory breakdowns."

If `subcategory.unclassified > 0`, add:
> "`{unclassified}` transactions have subcategory `unclassified`. Inspect them in the Transaction Editor, or add regex patterns to `src/subcategory.py` and re-run `/clean-data`."
