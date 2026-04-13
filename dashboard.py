"""
Personal Finance Dashboard
Run with: streamlit run dashboard.py
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from src.pipeline import status as pipeline_status

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Finance",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.7; }
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
.section-header {
    font-size: 1.1rem; font-weight: 600;
    color: rgba(255,255,255,0.85);
    margin: 1.5rem 0 0.5rem;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
CUMULATIVE_CSV = Path("output/cumulative.csv")

CATEGORY_COLORS = {
    "food": "#FF6B6B",
    "transport": "#4ECDC4",
    "shopping": "#45B7D1",
    "utilities": "#96CEB4",
    "entertainment": "#FFEAA7",
    "healthcare": "#DDA0DD",
    "income": "#98FB98",
    "savings": "#87CEEB",
    "transfer": "#B0B0B0",
    "fees": "#FFA07A",
    "other": "#C0C0C0",
}

BANK_COLORS = {
    "N26": "#00E5B4",
    "Amex": "#2E77BC",
    "Advanzia": "#FF6B35",
}

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_pipeline_status_data() -> list[dict]:
    return pipeline_status()


@st.cache_data
def load_data() -> pd.DataFrame:
    if not CUMULATIVE_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(CUMULATIVE_CSV)
    df["date"] = pd.to_datetime(df["date"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["month_dt"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["day_of_month"] = df["date"].dt.day
    df["year"] = df["date"].dt.year
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["amount_original"] = pd.to_numeric(df["amount_original"], errors="coerce")
    df["exchange_rate"] = pd.to_numeric(df["exchange_rate"], errors="coerce")
    return df


def real_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Debits only, excluding internal transfers and Space credits."""
    return df[
        (df["type"] == "debit")
        & (df["category"] != "transfer")
        & (df["account_type"] != "savings")
    ].copy()


def real_income(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["type"] == "credit") & (df["category"] == "income")].copy()


def fmt_eur(amount: float) -> str:
    return f"€{amount:,.2f}"


def chart_defaults() -> dict:
    return dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=16, r=16, t=32, b=16),
        font=dict(family="Inter, sans-serif", size=12),
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
def sidebar(df: pd.DataFrame):
    st.sidebar.title("💰 Finance")
    page = st.sidebar.radio(
        "Navigation",
        [
            "Overview",
            "Category Breakdown",
            "Spending Trends",
            "Savings & Spaces",
            "Travel & FX",
            "Merchant Intelligence",
            "Investment Potential",
            "Pipeline Status",
        ],
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Filters**")

    banks = sorted(df["bank"].dropna().unique().tolist())
    selected_banks = st.sidebar.multiselect("Bank", banks, default=banks)

    date_min = df["date"].min().date()
    date_max = df["date"].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )

    # Apply filters
    filtered = df[df["bank"].isin(selected_banks)].copy()
    if len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["date"].dt.date >= start) & (filtered["date"].dt.date <= end)
        ]

    st.sidebar.divider()
    st.sidebar.caption(f"{len(filtered)} transactions loaded")
    st.sidebar.caption("Add PDFs → `statements/` and run `/process-statements`")

    # ── Pipeline status ───────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.markdown("**Pipeline**")
    entries = load_pipeline_status_data()
    processed_entries = [e for e in entries if e.get("status") == "processed"]
    pending_entries = [e for e in entries if e.get("status") == "pending"]
    total_tx = sum(e.get("transaction_count") or 0 for e in processed_entries)

    p1, p2 = st.sidebar.columns(2)
    p1.metric("Processed", len(processed_entries))
    p2.metric("Pending", len(pending_entries))
    st.sidebar.caption(f"{total_tx:,} transactions extracted")

    if entries:
        with st.sidebar.expander("Statement details", expanded=False):
            for e in processed_entries:
                tx = e.get("transaction_count") or 0
                processed_at = (e.get("processed_at") or "")[:10]
                st.markdown(
                    f"✅ **{e['filename']}**  \n"
                    f"<span style='font-size:0.75rem;opacity:0.65'>{tx} txns · {processed_at}</span>",
                    unsafe_allow_html=True,
                )
            for e in pending_entries:
                st.markdown(
                    f"⏳ **{e['filename']}**  \n"
                    "<span style='font-size:0.75rem;opacity:0.65'>pending</span>",
                    unsafe_allow_html=True,
                )

    return page, filtered


# ── Page 1: Overview ──────────────────────────────────────────────────────────
def page_overview(df: pd.DataFrame):
    st.title("Overview")

    spend = real_spend(df)
    income = real_income(df)

    total_spend = spend["amount"].abs().sum()
    total_income = income["amount"].sum()
    net_flow = total_income - total_spend
    tx_count = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Income", fmt_eur(total_income), help="Sum of all income credits")
    c2.metric("Total Spend", fmt_eur(total_spend), help="All debits excluding transfers")
    c3.metric(
        "Net Cash Flow",
        fmt_eur(net_flow),
        delta=f"{(net_flow/total_income*100):.1f}% of income" if total_income else None,
        delta_color="normal",
    )
    c4.metric("Transactions", str(tx_count))

    st.markdown('<p class="section-header">Spend by Category</p>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        cat_spend = (
            spend.groupby("category")["amount"].apply(lambda x: x.abs().sum()).reset_index()
        )
        cat_spend.columns = ["category", "amount"]
        cat_spend = cat_spend.sort_values("amount", ascending=False)
        colors = [CATEGORY_COLORS.get(c, "#888") for c in cat_spend["category"]]
        fig = go.Figure(
            go.Pie(
                labels=cat_spend["category"],
                values=cat_spend["amount"],
                hole=0.55,
                marker_colors=colors,
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>€%{value:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(title="Category split", **chart_defaults(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        bank_spend = (
            spend.groupby("bank")["amount"].apply(lambda x: x.abs().sum()).reset_index()
        )
        bank_spend.columns = ["bank", "amount"]
        colors = [BANK_COLORS.get(b, "#888") for b in bank_spend["bank"]]
        fig = go.Figure(
            go.Pie(
                labels=bank_spend["bank"],
                values=bank_spend["amount"],
                hole=0.55,
                marker_colors=colors,
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>€%{value:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(title="Spend by bank / card", **chart_defaults(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-header">All Transactions</p>', unsafe_allow_html=True)
    display = df[["date", "receiver", "description", "amount", "category", "payment_method", "bank", "city"]].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    display["amount"] = display["amount"].apply(lambda x: f"€{x:+.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)


# ── Page 2: Category Breakdown ────────────────────────────────────────────────
def page_categories(df: pd.DataFrame):
    st.title("Category Breakdown")

    spend = real_spend(df)

    if spend.empty:
        st.info("No spending data in the selected range.")
        return

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown('<p class="section-header">By Category</p>', unsafe_allow_html=True)
        cat = (
            spend.groupby("category")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
            .sort_values("total", ascending=False)
        )
        cat["pct"] = (cat["total"] / cat["total"].sum() * 100).round(1)
        cat["total_fmt"] = cat["total"].apply(fmt_eur)
        st.dataframe(
            cat[["category", "total_fmt", "pct"]].rename(
                columns={"category": "Category", "total_fmt": "Total", "pct": "%"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    with col_right:
        st.markdown('<p class="section-header">Monthly Category Stack</p>', unsafe_allow_html=True)
        monthly_cat = (
            spend.groupby(["month_dt", "category"])["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
        )
        if not monthly_cat.empty:
            fig = px.bar(
                monthly_cat,
                x="month_dt",
                y="amount",
                color="category",
                color_discrete_map=CATEGORY_COLORS,
                labels={"month_dt": "Month", "amount": "EUR", "category": "Category"},
                barmode="stack",
            )
            fig.update_layout(
                xaxis_tickformat="%b %Y",
                **chart_defaults(),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-header">Top 15 Merchants</p>', unsafe_allow_html=True)
    top_merchants = (
        spend.groupby(["receiver", "category"])["amount"]
        .agg(total=lambda x: x.abs().sum(), count="count")
        .reset_index()
        .sort_values("total", ascending=False)
        .head(15)
    )
    top_merchants["total"] = top_merchants["total"].apply(fmt_eur)
    st.dataframe(
        top_merchants.rename(
            columns={"receiver": "Merchant", "category": "Category", "total": "Total", "count": "# Transactions"}
        ),
        hide_index=True,
        use_container_width=True,
    )


# ── Page 3: Spending Trends ───────────────────────────────────────────────────
def page_trends(df: pd.DataFrame):
    st.title("Spending Trends")

    spend = real_spend(df)

    if spend.empty:
        st.info("No spending data in the selected range.")
        return

    # Monthly total
    st.markdown('<p class="section-header">Monthly Total Spend</p>', unsafe_allow_html=True)
    monthly = (
        spend.groupby("month_dt")["amount"]
        .apply(lambda x: x.abs().sum())
        .reset_index()
        .rename(columns={"amount": "total"})
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["month_dt"],
            y=monthly["total"],
            marker_color="#45B7D1",
            name="Spend",
            hovertemplate="<b>%{x|%b %Y}</b><br>€%{y:,.2f}<extra></extra>",
        )
    )
    if len(monthly) > 1:
        fig.add_trace(
            go.Scatter(
                x=monthly["month_dt"],
                y=monthly["total"],
                mode="lines+markers",
                line=dict(color="#FFD700", width=2),
                marker=dict(size=6),
                name="Trend",
            )
        )
    fig.update_layout(xaxis_tickformat="%b %Y", **chart_defaults())
    st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">Spend by Day of Month</p>', unsafe_allow_html=True)
        day_spend = (
            spend.groupby("day_of_month")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
        )
        fig2 = px.bar(
            day_spend,
            x="day_of_month",
            y="total",
            labels={"day_of_month": "Day of Month", "total": "EUR"},
            color="total",
            color_continuous_scale="Blues",
        )
        fig2.update_layout(**chart_defaults(), coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        st.markdown('<p class="section-header">Spend by Payment Method</p>', unsafe_allow_html=True)
        pm_spend = (
            spend.groupby("payment_method")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
        )
        pm_spend["payment_method"] = pm_spend["payment_method"].fillna("unknown")
        fig3 = px.pie(
            pm_spend,
            names="payment_method",
            values="total",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.update_layout(**chart_defaults())
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<p class="section-header">Cumulative Spend Over Time</p>', unsafe_allow_html=True)
    spend_sorted = spend.sort_values("date")
    spend_sorted["cumulative"] = spend_sorted["amount"].abs().cumsum()
    fig4 = go.Figure(
        go.Scatter(
            x=spend_sorted["date"],
            y=spend_sorted["cumulative"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#FF6B6B", width=2),
            fillcolor="rgba(255,107,107,0.15)",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Cumulative: €%{y:,.2f}<extra></extra>",
        )
    )
    fig4.update_layout(
        yaxis_title="Cumulative EUR",
        **chart_defaults(),
    )
    st.plotly_chart(fig4, use_container_width=True)


# ── Page 4: Savings & Spaces ──────────────────────────────────────────────────
def page_savings(df: pd.DataFrame):
    st.title("Savings & N26 Spaces")

    spaces_df = df[df["account_type"] == "savings"].copy()
    checking = df[(df["bank"] == "N26") & (df["account_type"] == "checking")].copy()

    income = real_income(df)
    total_income = income["amount"].sum()

    transfers_out = checking[
        (checking["category"] == "transfer") & (checking["type"] == "debit")
    ]["amount"].abs().sum()

    savings_rate = (transfers_out / total_income * 100) if total_income > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", fmt_eur(total_income))
    c2.metric("Moved to Spaces", fmt_eur(transfers_out))
    c3.metric("Savings Rate", f"{savings_rate:.1f}%", help="% of income moved to N26 Spaces")

    if spaces_df.empty:
        st.info("No N26 Space transactions in the selected range.")
    else:
        st.markdown('<p class="section-header">Space Transactions</p>', unsafe_allow_html=True)
        space_summary = (
            spaces_df.groupby("space")["amount"]
            .agg(total="sum", count="count")
            .reset_index()
        )
        space_summary["total_fmt"] = space_summary["total"].apply(fmt_eur)

        col_left, col_right = st.columns(2)
        with col_left:
            fig = px.bar(
                space_summary,
                x="space",
                y="total",
                color="space",
                labels={"space": "Space", "total": "EUR"},
                title="Total moved per Space",
                color_discrete_sequence=["#00E5B4", "#87CEEB", "#96CEB4", "#FFEAA7"],
            )
            fig.update_layout(**chart_defaults(), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.dataframe(
                space_summary[["space", "total_fmt", "count"]].rename(
                    columns={"space": "Space", "total_fmt": "Total Saved", "count": "Transactions"}
                ),
                hide_index=True,
                use_container_width=True,
            )

        st.markdown('<p class="section-header">Space Transactions Detail</p>', unsafe_allow_html=True)
        detail = spaces_df[["date", "space", "description", "amount"]].copy()
        detail["date"] = detail["date"].dt.strftime("%Y-%m-%d")
        detail["amount"] = detail["amount"].apply(fmt_eur)
        st.dataframe(detail, hide_index=True, use_container_width=True)


# ── Page 5: Travel & FX ──────────────────────────────────────────────────────
def page_travel(df: pd.DataFrame):
    st.title("Travel & Foreign Currency")

    fx = df[df["currency_original"].notna()].copy()

    if fx.empty:
        st.info("No foreign currency transactions in the selected range.")
        return

    total_fx_eur = fx["amount"].abs().sum()
    currencies = fx["currency_original"].nunique()
    countries = fx["city"].dropna().nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total FX Spend (EUR)", fmt_eur(total_fx_eur))
    c2.metric("Currencies", str(currencies))
    c3.metric("Cities", str(countries))

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">By Currency</p>', unsafe_allow_html=True)
        by_ccy = (
            fx.groupby("currency_original")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "EUR equivalent"})
        )
        fig = px.bar(
            by_ccy,
            x="currency_original",
            y="EUR equivalent",
            color="currency_original",
            labels={"currency_original": "Currency"},
            color_discrete_sequence=["#FF6B35", "#45B7D1", "#FFEAA7"],
        )
        fig.update_layout(**chart_defaults(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown('<p class="section-header">By City</p>', unsafe_allow_html=True)
        by_city = (
            fx.groupby("city")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "EUR equivalent"})
            .sort_values("EUR equivalent", ascending=True)
        )
        fig2 = px.bar(
            by_city,
            x="EUR equivalent",
            y="city",
            orientation="h",
            labels={"city": "City"},
            color_discrete_sequence=["#4ECDC4"],
        )
        fig2.update_layout(**chart_defaults())
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<p class="section-header">FX Transaction Detail</p>', unsafe_allow_html=True)
    detail = fx[["date", "receiver", "city", "currency_original", "amount_original", "exchange_rate", "amount", "bank"]].copy()
    detail["date"] = detail["date"].dt.strftime("%Y-%m-%d")
    detail["amount"] = detail["amount"].apply(lambda x: fmt_eur(abs(x)))
    detail["amount_original"] = detail.apply(
        lambda r: f"{r['amount_original']:,.2f} {r['currency_original']}" if pd.notna(r["amount_original"]) else "", axis=1
    )
    detail["exchange_rate"] = detail["exchange_rate"].apply(
        lambda x: f"{x:.4f}" if pd.notna(x) else ""
    )
    st.dataframe(
        detail.rename(columns={
            "date": "Date", "receiver": "Merchant", "city": "City",
            "currency_original": "Currency", "amount_original": "Original Amount",
            "exchange_rate": "Rate (per EUR)", "amount": "EUR Amount", "bank": "Bank"
        }),
        hide_index=True,
        use_container_width=True,
    )

    # FX fee estimate (Amex charges 2%)
    amex_fx = fx[fx["bank"] == "Amex"]["amount"].abs().sum()
    if amex_fx > 0:
        estimated_fee = amex_fx * 0.02
        st.info(f"**Estimated Amex FX fees (2%):** {fmt_eur(estimated_fee)} on {fmt_eur(amex_fx)} of foreign spend")


# ── Page 6: Merchant Intelligence ────────────────────────────────────────────
def page_merchants(df: pd.DataFrame):
    st.title("Merchant Intelligence")

    spend = real_spend(df)

    if spend.empty:
        st.info("No spending data in the selected range.")
        return

    st.markdown('<p class="section-header">Top Merchants by Spend</p>', unsafe_allow_html=True)
    top = (
        spend.groupby("receiver")
        .agg(total=("amount", lambda x: x.abs().sum()), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
        .head(20)
    )
    fig = px.bar(
        top,
        x="total",
        y="receiver",
        orientation="h",
        color="total",
        color_continuous_scale="Blues",
        labels={"total": "Total Spend (EUR)", "receiver": "Merchant"},
        hover_data={"count": True},
    )
    fig.update_layout(**chart_defaults(), coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">PayPal Breakdown</p>', unsafe_allow_html=True)
        paypal = spend[spend["payment_method"] == "paypal"].copy()
        if paypal.empty:
            st.write("No PayPal transactions.")
        else:
            pp = (
                paypal.groupby("receiver")
                .agg(total=("amount", lambda x: x.abs().sum()), count=("amount", "count"))
                .reset_index()
                .sort_values("total", ascending=False)
            )
            pp["total_fmt"] = pp["total"].apply(fmt_eur)
            st.dataframe(
                pp[["receiver", "total_fmt", "count"]].rename(
                    columns={"receiver": "Real Merchant (via PayPal)", "total_fmt": "Total", "count": "Txns"}
                ),
                hide_index=True,
                use_container_width=True,
            )

    with col_right:
        st.markdown('<p class="section-header">Recurring Merchant Detection</p>', unsafe_allow_html=True)
        recurring = (
            spend.groupby("receiver")
            .agg(count=("amount", "count"), total=("amount", lambda x: x.abs().sum()))
            .reset_index()
        )
        recurring = recurring[recurring["count"] > 1].sort_values("count", ascending=False)
        if recurring.empty:
            st.write("No recurring merchants detected (need more data).")
        else:
            recurring["avg"] = (recurring["total"] / recurring["count"]).apply(fmt_eur)
            recurring["total"] = recurring["total"].apply(fmt_eur)
            st.dataframe(
                recurring.rename(columns={
                    "receiver": "Merchant", "count": "# Times",
                    "total": "Total Spend", "avg": "Avg per Txn"
                }),
                hide_index=True,
                use_container_width=True,
            )

    st.markdown('<p class="section-header">Spend Concentration</p>', unsafe_allow_html=True)
    total_spend = spend["amount"].abs().sum()
    top5 = top.head(5)["total"].sum()
    top5_pct = top5 / total_spend * 100 if total_spend else 0
    st.metric(
        "Top 5 merchants",
        fmt_eur(top5),
        delta=f"{top5_pct:.1f}% of total spend",
        delta_color="off",
    )


# ── Page 7: Investment Potential ─────────────────────────────────────────────
def page_investment(df: pd.DataFrame):
    st.title("Investment Potential")

    spend = real_spend(df)
    income = real_income(df)

    total_income = income["amount"].sum()
    total_spend = spend["amount"].abs().sum()
    net = total_income - total_spend

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", fmt_eur(total_income))
    c2.metric("Total Spend", fmt_eur(total_spend))
    c3.metric(
        "Net Surplus",
        fmt_eur(net),
        delta=f"{(net/total_income*100):.1f}% saved" if total_income else None,
    )

    st.divider()
    st.markdown('<p class="section-header">Compound Growth Simulator</p>', unsafe_allow_html=True)
    st.caption("Adjust the sliders to see what investing your surplus monthly could grow to.")

    col_s, col_r, col_y = st.columns(3)
    with col_s:
        monthly_invest = st.slider(
            "Monthly investment (EUR)", min_value=50, max_value=5000, value=max(50, int(net / 6)), step=50
        )
    with col_r:
        annual_return = st.slider("Expected annual return (%)", min_value=1.0, max_value=15.0, value=7.0, step=0.5)
    with col_y:
        years = st.slider("Years", min_value=1, max_value=40, value=20)

    monthly_rate = annual_return / 100 / 12
    months = years * 12
    month_range = np.arange(1, months + 1)

    # Future value of monthly contributions
    if monthly_rate > 0:
        fv = monthly_invest * ((1 + monthly_rate) ** month_range - 1) / monthly_rate
    else:
        fv = monthly_invest * month_range

    invested = monthly_invest * month_range
    growth = fv - invested

    final_value = fv[-1]
    total_invested = invested[-1]
    total_growth = growth[-1]

    r1, r2, r3 = st.columns(3)
    r1.metric("Portfolio value", fmt_eur(final_value))
    r2.metric("Total invested", fmt_eur(total_invested))
    r3.metric("Total returns", fmt_eur(total_growth), delta=f"{(total_growth/total_invested*100):.0f}% gain")

    dates = pd.date_range(start=pd.Timestamp.today(), periods=months, freq="MS")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates, y=fv,
            name="Portfolio Value",
            fill="tozeroy",
            line=dict(color="#98FB98", width=2),
            fillcolor="rgba(152,251,152,0.12)",
            hovertemplate="<b>%{x|%b %Y}</b><br>Portfolio: €%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates, y=invested,
            name="Amount Invested",
            line=dict(color="#4ECDC4", width=2, dash="dash"),
            hovertemplate="<b>%{x|%b %Y}</b><br>Invested: €%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates, y=growth,
            name="Returns",
            line=dict(color="#FFD700", width=1.5),
            hovertemplate="<b>%{x|%b %Y}</b><br>Returns: €%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        yaxis_title="EUR",
        legend=dict(orientation="h", y=-0.12),
        **chart_defaults(),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-header">Subscription / Recurring Audit</p>', unsafe_allow_html=True)
    st.caption("Recurring small charges add up. Here's what you're paying repeatedly.")

    all_spend = df[(df["type"] == "debit") & (df["category"] != "transfer")].copy()
    recurring = (
        all_spend.groupby("receiver")
        .agg(count=("amount", "count"), total=("amount", lambda x: x.abs().sum()))
        .reset_index()
    )
    recurring = recurring[recurring["count"] > 1].sort_values("total", ascending=False)
    if not recurring.empty:
        recurring["avg_per_month_est"] = (recurring["total"] / recurring["count"]).apply(fmt_eur)
        recurring["total"] = recurring["total"].apply(fmt_eur)
        st.dataframe(
            recurring.rename(columns={
                "receiver": "Merchant", "count": "Occurrences",
                "total": "Total Paid", "avg_per_month_est": "Avg per Occurrence"
            }),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown('<p class="section-header">Category Reduction Scenarios</p>', unsafe_allow_html=True)
    st.caption("How much could you save per year by cutting each category by 20%?")
    spend_by_cat = (
        spend.groupby("category")["amount"]
        .apply(lambda x: x.abs().sum())
        .reset_index()
        .rename(columns={"amount": "total"})
        .sort_values("total", ascending=False)
    )
    spend_by_cat["annual_est"] = spend_by_cat["total"] * 12
    spend_by_cat["saving_20pct"] = spend_by_cat["annual_est"] * 0.20
    spend_by_cat["invested_10yr"] = spend_by_cat["saving_20pct"] / 12 * (
        ((1 + 0.07 / 12) ** 120 - 1) / (0.07 / 12)
    )
    spend_by_cat["total"] = spend_by_cat["total"].apply(fmt_eur)
    spend_by_cat["annual_est"] = spend_by_cat["annual_est"].apply(fmt_eur)
    spend_by_cat["saving_20pct"] = spend_by_cat["saving_20pct"].apply(fmt_eur)
    spend_by_cat["invested_10yr"] = spend_by_cat["invested_10yr"].apply(fmt_eur)
    st.dataframe(
        spend_by_cat.rename(columns={
            "category": "Category",
            "total": "Seen in Data",
            "annual_est": "Annual Estimate",
            "saving_20pct": "Save 20% → Annual",
            "invested_10yr": "Invested @ 7% over 10yr",
        }),
        hide_index=True,
        use_container_width=True,
    )


# ── Page 8: Pipeline Status ──────────────────────────────────────────────────
def page_pipeline_status(df: pd.DataFrame):
    st.title("Pipeline Status")

    entries = load_pipeline_status_data()

    if not entries:
        st.info("No statements discovered yet. Add PDFs to `statements/` and run `/process-statements`.")
        return

    processed_entries = [e for e in entries if e.get("status") == "processed"]
    pending_entries = [e for e in entries if e.get("status") == "pending"]
    total = len(entries)
    n_processed = len(processed_entries)
    n_pending = len(pending_entries)
    total_tx = sum(e.get("transaction_count") or 0 for e in processed_entries)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Statements", total)
    c2.metric("Processed", n_processed)
    c3.metric("Pending", n_pending)
    c4.metric("Transactions Extracted", f"{total_tx:,}")

    progress = n_processed / total if total else 0
    st.progress(progress, text=f"{progress*100:.0f}% of statements processed")

    # ── Processed statements ─────────────────────────────────────────────────
    if processed_entries:
        st.markdown('<p class="section-header">Processed Statements</p>', unsafe_allow_html=True)

        processed_df = pd.DataFrame([
            {
                "File": e["filename"],
                "Transactions": e.get("transaction_count") or 0,
                "Processed At": (e.get("processed_at") or "")[:19].replace("T", " "),
                "Discovered At": (e.get("discovered_at") or "")[:19].replace("T", " "),
                "Output CSV": (e.get("output") or {}).get("csv", ""),
            }
            for e in processed_entries
        ])

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.dataframe(processed_df, hide_index=True, use_container_width=True)

        with col_right:
            fig = go.Figure(
                go.Bar(
                    x=processed_df["Transactions"],
                    y=processed_df["File"],
                    orientation="h",
                    marker_color="#00E5B4",
                    hovertemplate="<b>%{y}</b><br>%{x} transactions<extra></extra>",
                )
            )
            fig.update_layout(
                title="Transactions per statement",
                yaxis=dict(autorange="reversed"),
                **chart_defaults(),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Pending statements ───────────────────────────────────────────────────
    if pending_entries:
        st.markdown('<p class="section-header">Pending Statements</p>', unsafe_allow_html=True)
        pending_df = pd.DataFrame([
            {
                "File": e["filename"],
                "Path": e.get("path") or "",
                "Discovered At": (e.get("discovered_at") or "")[:19].replace("T", " "),
            }
            for e in pending_entries
        ])
        st.dataframe(pending_df, hide_index=True, use_container_width=True)
        st.info(f"{n_pending} statement(s) waiting — run `/process-statements` to extract transactions.")
    else:
        st.success("All discovered statements have been processed.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    df = load_data()

    if df.empty:
        st.warning("No data found. Run `/process-statements` to process your PDFs first.")
        return

    page, filtered = sidebar(df)

    pages = {
        "Overview": page_overview,
        "Category Breakdown": page_categories,
        "Spending Trends": page_trends,
        "Savings & Spaces": page_savings,
        "Travel & FX": page_travel,
        "Merchant Intelligence": page_merchants,
        "Investment Potential": page_investment,
        "Pipeline Status": page_pipeline_status,
    }

    pages[page](filtered)


if __name__ == "__main__":
    main()
