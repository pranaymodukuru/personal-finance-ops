"""
Pipeline state tracker.

Maintains pipeline.json with the full list of all discovered bank statement PDFs,
each with a status of "processed" or "pending".

Schema of pipeline.json:
{
  "documents": {
    "<sha256>": {
      "filename": "N26_2024-01.pdf",
      "path": "statements/N26/N26_2024-01.pdf",
      "status": "processed",          # or "pending"
      "discovered_at": "2024-04-09T10:00:00+00:00",
      "processed_at": "2024-04-09T10:30:00+00:00",  # null if pending
      "transaction_count": 42,                        # null if pending
      "output": {                                     # null if pending
        "csv": "output/raw/individual/N26_2024-01.csv",
        "json": "output/raw/individual/N26_2024-01.json",
        "cumulative": "output/raw/cumulative.csv"
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
    if not PIPELINE_FILE.exists():
        return {"documents": {}}
    raw = json.loads(PIPELINE_FILE.read_text())
    # Migrate old schema: {"processed": {...}} → {"documents": {...}}
    if "processed" in raw and "documents" not in raw:
        raw = _migrate(raw)
    return raw


def _migrate(old: dict) -> dict:
    """Migrate from the old {"processed": {}} schema to {"documents": {}}."""
    documents = {}
    for file_hash, entry in old.get("processed", {}).items():
        documents[file_hash] = {
            "filename": entry.get("filename"),
            "path": None,  # path was not stored in old schema
            "status": "processed",
            "discovered_at": entry.get("processed_at"),
            "processed_at": entry.get("processed_at"),
            "transaction_count": entry.get("transaction_count"),
            "output": entry.get("output"),
        }
    return {"documents": documents}


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
    doc = state["documents"].get(file_hash)
    return doc is not None and doc.get("status") == "processed"


def record(pdf_path: Path, transaction_count: int, csv_path: Path, json_path: Path) -> None:
    """Mark a PDF as processed in pipeline.json."""
    file_hash = sha256(pdf_path)
    state = _load()
    now = datetime.now(timezone.utc).isoformat()
    existing = state["documents"].get(file_hash, {})
    state["documents"][file_hash] = {
        "filename": pdf_path.name,
        "path": str(pdf_path),
        "status": "processed",
        "discovered_at": existing.get("discovered_at", now),
        "processed_at": now,
        "transaction_count": transaction_count,
        "output": {
            "csv": str(csv_path),
            "json": str(json_path),
            "cumulative": "output/raw/cumulative.csv",
        },
    }
    _save(state)


def sync(statements_dir: Path = Path("statements")) -> None:
    """Scan statements_dir for all PDFs and upsert them into pipeline.json.

    - Already-processed entries are left untouched.
    - Newly discovered PDFs are added with status "pending".
    - PDFs previously marked "pending" that are no longer on disk are removed.
    """
    state = _load()
    documents = state["documents"]

    # Build a map of hash → path for every PDF currently on disk
    all_pdfs = sorted(statements_dir.rglob("*.pdf"))
    on_disk: dict[str, Path] = {}
    for pdf in all_pdfs:
        h = sha256(pdf)
        on_disk[h] = pdf

    now = datetime.now(timezone.utc).isoformat()

    # Upsert: add new PDFs as "pending"; update paths for existing entries
    for file_hash, pdf_path in on_disk.items():
        if file_hash in documents:
            # Keep existing entry but refresh the path in case the file moved
            documents[file_hash]["path"] = str(pdf_path)
            documents[file_hash]["filename"] = pdf_path.name
        else:
            documents[file_hash] = {
                "filename": pdf_path.name,
                "path": str(pdf_path),
                "status": "pending",
                "discovered_at": now,
                "processed_at": None,
                "transaction_count": None,
                "output": None,
            }

    # Remove stale "pending" entries for PDFs no longer on disk
    # (processed entries are kept as historical record even if file is deleted)
    stale = [h for h, doc in documents.items()
             if doc.get("status") == "pending" and h not in on_disk]
    for h in stale:
        del documents[h]

    state["documents"] = documents
    _save(state)


def status() -> list[dict]:
    """Return all pipeline entries as a list, sorted by status then discovered_at."""
    state = _load()
    entries = [{"sha256": k, **v} for k, v in state["documents"].items()]
    # processed first, then pending; within each group newest first
    entries.sort(key=lambda e: (e.get("status") != "processed", e.get("discovered_at", "")), reverse=False)
    return entries


def pending(statements_dir: Path = Path("statements")) -> list[Path]:
    """Return PDFs in statements_dir (any depth) that have not yet been processed."""
    pdfs = sorted(statements_dir.rglob("*.pdf"))
    return [p for p in pdfs if not is_processed(p)]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        sync()
        print("pipeline.json synced.")

    entries = status()
    if not entries:
        print("No statements found.")
    else:
        processed = [e for e in entries if e.get("status") == "processed"]
        pending_entries = [e for e in entries if e.get("status") == "pending"]

        print(f"\nProcessed ({len(processed)}):")
        print(f"  {'File':<40} {'Transactions':>12}  {'Processed At'}")
        print("  " + "-" * 72)
        for e in processed:
            print(
                f"  {e['filename']:<40} {e['transaction_count']:>12}  {(e.get('processed_at') or '')[:19]}"
            )

        if pending_entries:
            print(f"\nPending ({len(pending_entries)}):")
            for e in pending_entries:
                print(f"  - {e['path'] or e['filename']}")
        else:
            print("\nPending: none")
