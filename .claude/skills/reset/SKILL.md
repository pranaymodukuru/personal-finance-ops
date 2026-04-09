---
name: reset
description: Reset all app data — removes all uploaded statements, extracted output, and pipeline state
---

Reset the personal finance pipeline by deleting all data files.

**This is destructive and irreversible.** Always confirm with the user before proceeding.

Steps:
1. Warn the user clearly:
   > "This will permanently delete all uploaded PDFs in `statements/`, all extracted data in `output/`, and the `pipeline.json` state file. This cannot be undone. Are you sure?"
2. Wait for explicit confirmation ("yes", "confirm", "go ahead", etc.). If the user does not confirm, abort and do nothing.
3. Once confirmed, run the following commands:
   ```bash
   rm -f statements/*.pdf
   rm -f output/cumulative.csv
   rm -rf output/individual/*
   touch output/individual/.gitkeep
   rm -f pipeline.json
   ```
4. Confirm what was deleted:
   - How many PDFs were removed from `statements/`
   - Whether `output/cumulative.csv` existed and was removed
   - Whether `output/individual/` was cleared
   - Whether `pipeline.json` was removed
5. Tell the user the app is now in a clean state and they can drop new PDFs into `statements/` and run `/process-statements` to start fresh.
