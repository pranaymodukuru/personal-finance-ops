---
name: pipeline-status
description: Show which bank statement PDFs have been processed, transaction counts, and what is still pending
---

Show the current state of the processing pipeline and sync pipeline.json with the filesystem.

Steps:
1. Run `python -m src.pipeline sync` — this scans all PDFs under `statements/`, adds any newly discovered files as "pending", removes stale pending entries, and saves the full state to `pipeline.json`.
2. Run `python -m src.pipeline` (without `sync`) to display the current pipeline table.
3. Present a clean summary with two sections:

**Processed**
- Count of processed statements
- Total transactions extracted across all statements
- Per-file table: filename, bank (infer from path/subfolder), transaction count, processed date, output CSV path

**Pending**
- Count of pending statements
- List of pending file paths
- If any pending files exist, prompt the user to run `/process-statements` to extract them

pipeline.json is always the source of truth — after running this command it reflects the complete, current state of every PDF in the `statements/` folder.
