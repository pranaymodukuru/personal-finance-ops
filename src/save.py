"""
Save extracted transactions to CSV and JSON, and record the run in pipeline.json.

Claude Code calls this after extracting transactions from a bank statement.

Usage:
    python src/save.py <pdf_path> '<transactions_json>'

Where <transactions_json> is a JSON array of transaction objects:
    [{"date": "2024-01-15", "receiver": "...", "reference": "...", "description": "...",
      "amount": -42.50, "type": "debit", "category": "food", "bank": "N26"}, ...]
"""

import csv
import json
import sys
from pathlib import Path

from src.pipeline import record

INDIVIDUAL_DIR = Path("output/individual")
CUMULATIVE_CSV = Path("output/cumulative.csv")

FIELDNAMES = [
    "date",
    "transaction_date",
    "receiver",
    "reference",
    "description",
    "amount",
    "currency_original",
    "amount_original",
    "exchange_rate",
    "type",
    "category",
    "payment_method",
    "account_type",
    "space",
    "city",
    "bank",
]


def save(pdf_path: Path, transactions: list[dict]) -> tuple[Path, Path]:
    """Write transactions to output/individual/<stem>.csv + .json, append to cumulative.csv."""
    INDIVIDUAL_DIR.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem
    json_path = INDIVIDUAL_DIR / f"{stem}.json"
    csv_path = INDIVIDUAL_DIR / f"{stem}.csv"

    json_path.write_text(json.dumps(transactions, indent=2))

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(transactions)

    _append_cumulative(transactions)

    record(pdf_path, len(transactions), csv_path, json_path)

    return csv_path, json_path


def _append_cumulative(transactions: list[dict]) -> None:
    """Append transactions to cumulative.csv, writing header only if file is new."""
    write_header = not CUMULATIVE_CSV.exists()
    with CUMULATIVE_CSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(transactions)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/save.py <pdf_path> '<transactions_json>'")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    transactions = json.loads(sys.argv[2])
    csv_path, json_path = save(pdf_path, transactions)
    print(f"Saved {len(transactions)} transactions.")
    print(f"  CSV  -> {csv_path}")
    print(f"  JSON -> {json_path}")
    print(f"  Cumulative -> {CUMULATIVE_CSV}")
    print(f"  Pipeline updated.")
