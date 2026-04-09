# personal-finance-ops

A local-first personal finance pipeline powered by **Claude Code**. Drop a bank statement PDF into `statements/` and get structured transaction data, a full interactive dashboard, and spending insights — no cloud service, no API keys, no data leaving your machine.

---

## How it works

```
statements/
  └── your-statement.pdf
        │
        ▼  Claude Code reads the PDF directly
        │  and extracts every transaction
        │
        ▼  python -m src.save
        │  writes CSV + JSON, updates pipeline.json
        │
        ▼  streamlit run dashboard.py
           7-page interactive dashboard
```

Claude Code acts as the AI brain: it reads the raw PDF, understands the bank's layout, extracts all transactions, normalises them to a consistent schema, and saves the output. No OCR library, no custom parser per bank — just Claude reading and reasoning.

---

## Features

- **Multi-bank support** — N26 (checking + Spaces), American Express PAYBACK, Advanzia Gebührenfrei Mastercard
- **Rich schema** — 16 fields per transaction including foreign currency, exchange rate, city, payment method, N26 Space sub-account
- **Idempotent pipeline** — files tracked by SHA256 hash; re-running never double-counts
- **Interactive dashboard** — 7 pages built with Streamlit + Plotly
- **Claude Code slash commands** — `/process-statements`, `/pipeline-status`, `/reprocess`, `/start-dashboard`
- **Privacy first** — all data stays local; `.gitignore` ensures statements and extracted data are never committed

---

## Setup

**Prerequisites:** Python 3.11+, [Claude Code](https://claude.ai/code)

```bash
git clone https://github.com/pranaymodukuru/personal-finance-ops
cd personal-finance-ops

pip install pdfplumber streamlit plotly pandas numpy
```

That's it. No API keys required — Claude Code is the runtime.

---

## Usage

### 1. Add your statements

Drop any supported bank statement PDF into `statements/`:

```
statements/
  ├── n26-october-2024.pdf
  ├── amex-november-2024.pdf
  └── advanzia-december-2024.pdf
```

### 2. Process them

Inside Claude Code, run:

```
/process-statements
```

Claude reads each unprocessed PDF, extracts all transactions, and saves structured output to `output/`.

### 3. Launch the dashboard

```
/start-dashboard
```

Or directly in your terminal:

```bash
streamlit run dashboard.py
```

Opens at **http://localhost:8501**

---

## Slash Commands

| Command | Description |
|---|---|
| `/process-statements` | Find all unprocessed PDFs in `statements/` and extract transactions |
| `/pipeline-status` | Show processed files, transaction counts, and what's pending |
| `/reprocess [file]` | Force re-extract a specific statement even if already processed |
| `/start-dashboard` | Start the Streamlit dashboard |

---

## Dashboard Pages

| Page | What you see |
|---|---|
| **Overview** | Income vs spend KPIs, net cash flow, category and bank pie charts, full transaction table |
| **Category Breakdown** | Donut chart, monthly stacked bar, top 15 merchants |
| **Spending Trends** | Monthly totals, cumulative spend curve, day-of-month heatmap, payment method split |
| **Savings & Spaces** | N26 Space balances, savings rate, Space transaction detail |
| **Travel & FX** | Foreign currency transactions, spend by city, estimated FX fees |
| **Merchant Intelligence** | Top merchants ranked, PayPal pass-through breakdown, recurring charge detection |
| **Investment Potential** | Compound growth simulator (adjustable sliders), category reduction scenarios |

---

## Transaction Schema

Every transaction is normalised to 16 fields:

| Field | Type | Description |
|---|---|---|
| `date` | YYYY-MM-DD | Booking/settlement date |
| `transaction_date` | YYYY-MM-DD \| null | Date the purchase actually occurred (differs on Amex) |
| `receiver` | string | Counterparty name — merchant, person, or institution |
| `reference` | string | Payment reference or note; empty string if none |
| `description` | string | Short clean English description of the transaction |
| `amount` | decimal | Negative = debit/charge, positive = credit/deposit. Always EUR. |
| `currency_original` | string \| null | ISO 4217 code if original currency was not EUR (e.g. `"INR"`) |
| `amount_original` | decimal \| null | Amount in original currency |
| `exchange_rate` | decimal \| null | FX rate used |
| `type` | `debit` \| `credit` | Direction of the transaction |
| `category` | string | `food`, `transport`, `utilities`, `entertainment`, `healthcare`, `shopping`, `income`, `savings`, `transfer`, `fees`, `other` |
| `payment_method` | string \| null | `paypal`, `sepa_transfer`, `direct_card`, `direct_debit`, `atm` |
| `account_type` | string | `checking`, `savings` (N26 Spaces), `credit_card` |
| `space` | string \| null | N26 Space name (e.g. `"House Rent"`); null for other banks |
| `city` | string \| null | City/location of transaction if stated in document |
| `bank` | string | `"N26"`, `"Amex"`, `"Advanzia"` |

---

## Project Structure

```
personal-finance-ops/
├── statements/              # Drop PDF bank statements here (git-ignored)
├── output/
│   ├── individual/          # Per-statement CSV + JSON (git-ignored)
│   └── cumulative.csv       # All transactions combined (git-ignored)
├── src/
│   ├── extractor.py         # PDF → raw text via pdfplumber (fallback)
│   ├── pipeline.py          # Tracks processed files by SHA256 hash
│   └── save.py              # Writes CSV/JSON and updates pipeline.json
├── .claude/
│   └── skills/
│       ├── process-statements/SKILL.md
│       ├── pipeline-status/SKILL.md
│       ├── reprocess/SKILL.md
│       └── start-dashboard/SKILL.md
├── dashboard.py             # Streamlit dashboard (7 pages)
├── pipeline.json            # Auto-generated; tracks processed files (git-ignored)
├── CLAUDE.md                # Instructions for Claude Code
└── pyproject.toml
```

---

## Supported Banks

| Bank | Type | Notes |
|---|---|---|
| **N26** | Checking account | Supports Spaces (sub-accounts), value date vs booking date, sender IBAN |
| **American Express PAYBACK** | Credit card | Two dates per transaction, PayPal merchant detection, PAYBACK points (skipped) |
| **Advanzia Gebührenfrei Mastercard** | Credit card | City field, inline FX with exchange rate, single date column |

### Adding a new bank

1. Drop a statement PDF into `statements/`
2. Run `/process-statements` — Claude will identify the bank format and extract accordingly
3. If the layout is complex, run `python -m src.extractor statements/yourfile.pdf` first to inspect the raw text
4. The extraction notes in `.claude/skills/process-statements/SKILL.md` can be extended with bank-specific rules

---

## Pipeline Tracking

Processed files are tracked in `pipeline.json` by **SHA256 hash** of the file content:

- Renaming a file does **not** cause it to be reprocessed
- Replacing a file with new content **will** trigger reprocessing
- Running `/process-statements` twice is safe — it skips already-processed files

```json
{
  "processed": {
    "a3f2c1...": {
      "filename": "n26-october-2024.pdf",
      "processed_at": "2024-10-09T10:30:00+00:00",
      "transaction_count": 42,
      "output": {
        "csv": "output/individual/n26-october-2024.csv",
        "json": "output/individual/n26-october-2024.json"
      }
    }
  }
}
```

---

## Privacy

All processing is local. The `.gitignore` ensures the following are **never committed**:

- `statements/*.pdf` — your bank statement PDFs
- `output/individual/*` — extracted transaction CSV/JSON files
- `output/cumulative.csv` — combined transaction history
- `pipeline.json` — file hashes and processing metadata

The repo contains only code, configuration, and empty directory placeholders.
