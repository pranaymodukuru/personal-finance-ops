---
name: start-dashboard
description: Start the personal finance Streamlit dashboard
---

Start the Streamlit dashboard for personal finance analysis.

Steps:
1. Check that `output/processed/cleaned_cumulative.csv` exists. If it does not, tell the user to run `/process-statements` then `/clean-data` first and stop.
2. Tell the user to run the following command in their terminal (suggest using `!` prefix to run it in-session):
   ```
   streamlit run dashboard.py
   ```
3. Let them know the dashboard will open at http://localhost:8501 and includes these pages:
   - **Overview** — income, spend, and net cash flow summary
   - **Category Breakdown** — where the money goes, top merchants
   - **Spending Trends** — monthly patterns, cumulative spend
   - **Savings & Spaces** — N26 Space balances and savings rate
   - **Travel & FX** — foreign currency transactions and FX fees
   - **Merchant Intelligence** — recurring charges, PayPal breakdown
   - **Investment Potential** — compound growth simulator and saving scenarios
4. Remind them that the dashboard auto-refreshes from `output/processed/cleaned_cumulative.csv` — adding new statements and running `/process-statements` then `/clean-data` is all that's needed to update it.
