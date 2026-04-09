"""
Pipeline state tracker.

Maintains pipeline.json to record which statements have been processed,
keyed by SHA256 hash so re-naming or replacing a file is handled correctly.

Schema of pipeline.json:
{
  "processed": {
    "<sha256>": {
      "filename": "chase_april_2024.pdf",
      "processed_at": "2024-04-09T10:30:00",
      "transaction_count": 42,
      "output": {
        "csv": "output/chase_april_2024.csv",
        "json": "output/chase_april_2024.json"
      }
    }
  }
}
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_FILE = Path("pipeline.json")


def _load() -> dict:
    if PIPELINE_FILE.exists():
        return json.loads(PIPELINE_FILE.read_text())
    return {"processed": {}}


def _save(state: dict) -> None:
    PIPELINE_FILE.write_text(json.dumps(state, indent=2))


def sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_processed(pdf_path: Path) -> bool:
    """Return True if this exact file (by content hash) has already been processed."""
    file_hash = sha256(pdf_path)
    state = _load()
    return file_hash in state["processed"]


def record(pdf_path: Path, transaction_count: int, csv_path: Path, json_path: Path) -> None:
    """Mark a PDF as processed in pipeline.json."""
    file_hash = sha256(pdf_path)
    state = _load()
    state["processed"][file_hash] = {
        "filename": pdf_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "transaction_count": transaction_count,
        "output": {
            "csv": str(csv_path),
            "json": str(json_path),
            "cumulative": "output/cumulative.csv",
        },
    }
    _save(state)


def status() -> list[dict]:
    """Return all pipeline entries as a list, sorted by processed_at descending."""
    state = _load()
    entries = [{"sha256": k, **v} for k, v in state["processed"].items()]
    entries.sort(key=lambda e: e.get("processed_at", ""), reverse=True)
    return entries


def pending(statements_dir: Path = Path("statements")) -> list[Path]:
    """Return PDFs in statements_dir that have not yet been processed."""
    pdfs = sorted(statements_dir.glob("*.pdf"))
    return [p for p in pdfs if not is_processed(p)]


if __name__ == "__main__":
    # Quick status dump
    entries = status()
    if not entries:
        print("No statements processed yet.")
    else:
        print(f"{'File':<35} {'Transactions':>12}  {'Processed At'}")
        print("-" * 70)
        for e in entries:
            print(
                f"{e['filename']:<35} {e['transaction_count']:>12}  {e['processed_at'][:19]}"
            )
