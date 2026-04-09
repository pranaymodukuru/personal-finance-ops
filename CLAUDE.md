# Personal Finance Assistant

Claude Code is the AI brain of this project. Drop a bank statement PDF into `statements/` and ask Claude Code to process it — no API keys needed.

## Project Structure

```
pf-ops/
├── statements/              # Drop PDF bank statements here (organised by bank subfolder)
│   ├── N26/
│   ├── Amex/
│   └── Advanzia/
├── output/
│   ├── individual/          # Per-statement CSV + JSON files
│   └── cumulative.csv       # All transactions combined across all statements
├── src/
│   ├── extractor.py         # PDF → raw text (pdfplumber); fallback for complex layouts
│   ├── pipeline.py          # Pipeline state tracker (reads/writes pipeline.json)
│   └── save.py              # Writes transactions to CSV + JSON and updates pipeline.json
├── .claude/
│   └── skills/
│       ├── process-statements/SKILL.md  # /process-statements slash command
│       ├── pipeline-status/SKILL.md     # /pipeline-status slash command
│       └── reprocess/SKILL.md           # /reprocess slash command
├── pipeline.json            # Auto-generated; tracks processed files by SHA256 hash
├── CLAUDE.md
└── pyproject.toml
```

## Setup

```bash
pip install -e .
```

No API key required. Claude Code reads PDFs directly and extracts transactions itself.

## Slash Commands

| Command | Description |
|---|---|
| `/process-statements` | Find all unprocessed PDFs in `statements/` and extract their transactions |
| `/pipeline-status` | Show which files have been processed, transaction counts, and what's pending |
| `/reprocess [file]` | Force re-extract a specific statement even if already processed |

## Pipeline Tracking

Processed files are tracked in `pipeline.json` by **SHA256 hash** of the file content. This means:
- Renaming a file does **not** cause it to be reprocessed
- Replacing a file with new content **will** trigger reprocessing (different hash)
- Running `/process-statements` twice is safe — it skips already-processed files

Example `pipeline.json`:
```json
{
  "processed": {
    "a3f2c1...": {
      "filename": "chase_april_2024.pdf",
      "processed_at": "2024-04-09T10:30:00+00:00",
      "transaction_count": 42,
      "output": {
        "csv": "output/chase_april_2024.csv",
        "json": "output/chase_april_2024.json"
      }
    }
  }
}
```

## Transaction Schema

Each transaction has:
- `date` — ISO format (YYYY-MM-DD); booking/settlement date
- `transaction_date` — ISO format or null; date purchase actually occurred (differs from `date` on Amex)
- `receiver` — counterparty name (merchant, person, or institution)
- `reference` — payment reference or note; empty string if none
- `description` — short clean English description of what the transaction is for
- `amount` — decimal (negative = debit/charge, positive = credit/deposit); always EUR
- `currency_original` — ISO 4217 code if original currency was not EUR (e.g. "INR"), else null
- `amount_original` — amount in original currency (positive), else null
- `exchange_rate` — FX rate used, else null
- `type` — "debit" or "credit"
- `category` — one of: food, transport, utilities, entertainment, healthcare, shopping, income, savings, transfer, fees, other
- `payment_method` — inferred: "paypal", "sepa_transfer", "direct_card", "direct_debit", "atm", or null
- `account_type` — "checking" (N26 main), "savings" (N26 Spaces), or "credit_card" (Amex/Advanzia)
- `space` — N26 Space sub-account name (e.g. "House Rent"), null for other banks
- `city` — city/location of transaction if stated in document, else null
- `bank` — name of the bank: "N26", "Amex", or "Advanzia"

## What Claude Code does

1. Reads the PDF using its native Read tool (supports multi-page PDFs)
2. Extracts all transactions from the statement text
3. Runs `python -m src.save <pdf_path> '<json>'` to write CSV + JSON and update `pipeline.json`

If the PDF has complex table layouts that the Read tool struggles with, fall back to:
```bash
python -m src.extractor statements/foo.pdf
```
