---
name: pipeline-status
description: Show which bank statement PDFs have been processed, transaction counts, and what is still pending
---

Show the current state of the processing pipeline.

Steps:
1. Run `python -m src.pipeline` to display all processed statements.
2. Run `python -c "from src.pipeline import pending; files = list(pending()); print(f'{len(files)} pending'); [print(' -', p) for p in files]"` to list any unprocessed PDFs waiting in statements/.
3. Present a clean summary:
   - How many statements have been processed total
   - Total transactions extracted across all statements
   - Which files are pending (if any), prompting the user to run /process-statements if there are pending files
   - For each processed file: filename, transaction count, date processed, and output file paths
