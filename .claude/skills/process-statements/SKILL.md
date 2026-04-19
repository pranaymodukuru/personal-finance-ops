---
name: process-statements
description: Find all unprocessed bank statement PDFs in statements/ and extract their transactions
---

Check for unprocessed bank statement PDFs and extract their transactions — one agent per document.

Steps:
1. Run `python -m src.pipeline` to see what has already been processed.
2. Run `python -c "from src.pipeline import pending; [print(p) for p in pending()]"` to list unprocessed PDFs in statements/.
3. If there are no pending PDFs, tell the user everything is already up to date and stop.
4. Take only the **first 3** pending PDFs from the list. If there are more than 3 pending, note how many are remaining after this batch.
5. For each of the (up to 3) selected PDFs, spawn a **separate Agent** (using the Agent tool) to process it. Do NOT process documents yourself — delegate every document to its own agent to keep context isolated. Pass the full extraction prompt below as the agent's `prompt`, with the specific PDF path substituted in.
6. Wait for all agents to complete, then print a summary table: filename, bank, transaction count, and output path for each.
7. If there are remaining unprocessed PDFs beyond this batch, tell the user how many are left and **ask if they want to process the next batch** before proceeding. Do NOT continue automatically.

## Per-document agent prompt template

Use this as the `prompt` for each spawned agent (substitute `{PDF_PATH}` with the actual path):

```
Process the bank statement PDF at: {PDF_PATH}

Steps:
1. Read the PDF using the Read tool (or fall back to `python -m src.extractor {PDF_PATH}` for complex layouts).
2. Identify the bank from the document header/branding (N26, Amex, or Advanzia).
3. Extract ALL transactions — every debit, credit, fee, and transfer visible in the document.
4. Normalize each transaction to the schema below.
5. Run `python -m src.save {PDF_PATH} '<transactions_json>'` to save and update pipeline.json.
6. Report how many transactions were found and where the output CSV/JSON was saved.

## Transaction Schema

All fields are required. Use `null` for fields not available in the source document.

| Field | Type | Description |
|---|---|---|
| `date` | YYYY-MM-DD | Booking/settlement date (the date the bank posted it) |
| `transaction_date` | YYYY-MM-DD or null | Date the purchase/transfer actually occurred, if different from booking date |
| `receiver` | string | Counterparty name (merchant, person, or institution) |
| `reference` | string | Payment reference or note; empty string if none |
| `description` | string | Short clean English description of what the transaction is for |
| `amount` | decimal | Negative = debit/charge, positive = credit/deposit. Always in EUR. |
| `currency_original` | string or null | ISO 4217 code of original currency if not EUR (e.g. "INR", "USD") |
| `amount_original` | decimal or null | Amount in original currency (positive number) |
| `exchange_rate` | decimal or null | FX rate used (EUR per 1 unit of foreign currency, or as stated in document) |
| `type` | "debit" or "credit" | Direction of the transaction |
| `category` | string | One of: food, transport, utilities, entertainment, healthcare, shopping, income, savings, transfer, fees, other |
| `payment_method` | string or null | Inferred method: "paypal", "sepa_transfer", "direct_card", "direct_debit", "atm" |
| `account_type` | string | "checking" for N26 main account, "savings" for N26 Spaces, "credit_card" for Amex/Advanzia |
| `space` | string or null | N26 Space name (e.g. "House Rent", "Emergency Fund"); null for other banks |
| `city` | string or null | City or location of transaction if stated in document |
| `bank` | string | "N26", "Amex", or "Advanzia" |

## Bank-Specific Extraction Notes

### N26 (checking account)
- The statement has a **Main Account** section followed by **Space** sub-account sections.
- Main account: `account_type = "checking"`, `space = null`
- Space transactions (e.g. "Von Main Account"): `account_type = "savings"`, `space = <space name>`
- Internal transfers between Main Account and Spaces: `category = "transfer"`, `type = "debit"` (out of main) or `"credit"` (into space)
- Incoming transfers often show sender IBAN/BIC — put the sender name in `receiver`, IBAN in `reference`
- `transaction_date` = Wertstellung date; `date` = Verbuchungsdatum

### American Express PAYBACK (credit card)
- `account_type = "credit_card"`, `bank = "Amex"`
- Two dates per row: "Umsatz vom" (transaction date) and "Buchungsdatum" (booking date)
  - `date` = Buchungsdatum, `transaction_date` = Umsatz vom
- Many charges come via PayPal: set `payment_method = "paypal"`; receiver = the real merchant after "PAYPAL *"
- Foreign currency amounts appear in a separate column — extract `currency_original` and `amount_original`
- PAYBACK points rows are metadata, not transactions — skip them

### Advanzia Gebührenfrei Mastercard (credit card)
- `account_type = "credit_card"`, `bank = "Advanzia"`
- Single date column → use for both `date` and `transaction_date`
- City is in the "Ort" column → set `city`
- Foreign currency is embedded in the description: e.g. "AMAZON PAY INDIA PRIVA - INR 16876,00 (KURS 89,9094)"
  - Extract: `currency_original = "INR"`, `amount_original = 16876.00`, `exchange_rate = 89.9094`
  - Clean the merchant name (remove the FX suffix) for `receiver`
- ALTER SALDO / NEUER SALDO / EINZAHLUNG / Mindestbetrag rows are balance/payment metadata — skip them (or treat EINZAHLUNG as a credit payment if desired)
- `payment_method = "direct_card"` unless description says PayPal
```
