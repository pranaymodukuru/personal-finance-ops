---
name: reprocess
description: Force re-extract transactions from a specific bank statement PDF, even if already processed
argument-hint: [pdf-filename]
---

Force reprocess a specific bank statement PDF, even if it was already processed before.

Steps:
1. If no filename was provided in the command arguments, ask the user which file to reprocess and list available PDFs with `ls statements/*.pdf`.
2. Read the specified PDF using the Read tool.
3. Extract ALL transactions from the statement — every debit, credit, fee, and transfer visible in the document.
4. Normalize each transaction to this schema:
   - date: YYYY-MM-DD
   - description: merchant or transaction description (clean, no extra whitespace)
   - amount: decimal number, negative for debits/charges, positive for credits/deposits
   - type: "debit" or "credit"
   - category: one of food, transport, utilities, entertainment, healthcare, shopping, income, other
5. Run `python src/save.py <pdf_path> '<transactions_json>'` to overwrite existing output and update pipeline.json.
6. Report how many transactions were found and confirm the output files were updated.
