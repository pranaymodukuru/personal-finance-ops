"""
Personal Finance Dashboard
Run with: streamlit run dashboard.py
"""

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

# ── CSS ───────────────────────────────────────────────────────────────────────
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
CUMULATIVE_CSV = Path("output/processed/cleaned_cumulative.csv")

CATEGORY_COLORS = {
    "food":          "#FF6B6B",
    "transport":     "#4ECDC4",
    "shopping":      "#45B7D1",
    "utilities":     "#96CEB4",
    "entertainment": "#FFEAA7",
    "healthcare":    "#DDA0DD",
    "income":        "#98FB98",
    "savings":       "#87CEEB",
    "transfer":      "#B0B0B0",
    "fees":          "#FFA07A",
    "other":         "#C0C0C0",
    "learning":      "#C3B1E1",
    "travel":        "#FFB347",
    "insurance":     "#AED6F1",
}

BANK_COLORS = {
    "N26":      "#00E5B4",
    "Amex":     "#2E77BC",
    "Advanzia": "#FF6B35",
}

ACCENT_PRIMARY  = "#00E5B4"
ACCENT_WARNING  = "#FFD700"
ACCENT_NEGATIVE = "#FF6B6B"
ACCENT_NEUTRAL  = "#B0B0B0"

PAGE_NAMES = [
    "Dashboard",
    "Spending",
    "Income & Savings",
    "Merchants & Subscriptions",
    "Transactions",
    "Pipeline & Data",
]

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


# ── Data helpers ──────────────────────────────────────────────────────────────
def real_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Debits only, excluding internal transfers and Space credits."""
    return df[
        (df["type"] == "debit")
        & (df["category"] != "transfer")
        & (df["account_type"] != "savings")
    ].copy()


def real_income(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["type"] == "credit") & (df["category"] == "income")].copy()


def real_investments(df: pd.DataFrame) -> pd.DataFrame:
    """ETF and investment-category debits."""
    if "subcategory" not in df.columns:
        return pd.DataFrame()
    return df[
        (df["type"] == "debit")
        & (df["subcategory"].isin(["etf_investments", "investment_transfer"]))
    ].copy()


def monthly_agg(df: pd.DataFrame, value_col: str = "amount", abs_val: bool = False) -> pd.DataFrame:
    d = df.copy()
    if abs_val:
        d[value_col] = d[value_col].abs()
    return (
        d.groupby("month_dt")[value_col]
        .sum()
        .reset_index()
        .sort_values("month_dt")
    )


def savings_rate_series(df: pd.DataFrame) -> pd.DataFrame:
    inc = real_income(df)
    spd = real_spend(df)
    m_inc = monthly_agg(inc).rename(columns={"amount": "income"})
    m_spd = monthly_agg(spd, abs_val=True).rename(columns={"amount": "spend"})
    merged = pd.merge(m_inc, m_spd, on="month_dt", how="outer").fillna(0).sort_values("month_dt")
    merged["rate"] = merged.apply(
        lambda r: (r["income"] - r["spend"]) / r["income"] * 100 if r["income"] > 0 else 0,
        axis=1,
    )
    return merged


def detect_recurring(df: pd.DataFrame, min_occurrences: int = 3) -> pd.DataFrame:
    spend = real_spend(df)
    grouped = (
        spend.groupby("receiver")["amount"]
        .agg(count="count", total=lambda x: x.abs().sum(), avg=lambda x: x.abs().mean(), std=lambda x: x.abs().std())
        .reset_index()
    )
    grouped = grouped[grouped["count"] >= min_occurrences].copy()
    grouped["stability"] = grouped.apply(
        lambda r: max(0.0, 1.0 - (r["std"] / r["avg"])) if r["avg"] > 0 and pd.notna(r["std"]) else 0.0,
        axis=1,
    )
    grouped["annual_est"] = grouped["avg"] * 12
    return grouped.sort_values("total", ascending=False)


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    inc = real_income(df)
    spd = real_spend(df)
    years = sorted(df["year"].dropna().unique().astype(int).tolist())
    rows = []
    for yr in years:
        y_inc = inc[inc["year"] == yr]["amount"].sum()
        y_spd = spd[spd["year"] == yr]["amount"].abs().sum()
        net = y_inc - y_spd
        rate = (net / y_inc * 100) if y_inc > 0 else 0.0
        rows.append({"Year": yr, "Income": y_inc, "Spend": y_spd, "Net": net, "Savings Rate %": round(rate, 1)})
    return pd.DataFrame(rows)


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
    page = st.sidebar.radio("Navigation", PAGE_NAMES, label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.markdown("**Filters**")

    banks = sorted(df["bank"].dropna().unique().tolist())
    selected_banks = st.sidebar.multiselect("Bank", banks, default=banks)

    date_min = df["date"].min().date()
    date_max = df["date"].max().date()

    _preset = st.sidebar.selectbox(
        "Quick filter",
        ["All time", "This month", "Last 3 months", "Last 6 months", "This year"],
        index=0,
    )
    _today = pd.Timestamp.today().date()
    _today_ts = pd.Timestamp.today()
    if _preset == "This month":
        _default_start = _today.replace(day=1)
        _default_end = _today
    elif _preset == "Last 3 months":
        _default_start = (_today_ts - pd.DateOffset(months=3)).date()
        _default_end = _today
    elif _preset == "Last 6 months":
        _default_start = (_today_ts - pd.DateOffset(months=6)).date()
        _default_end = _today
    elif _preset == "This year":
        _default_start = _today.replace(month=1, day=1)
        _default_end = _today
    else:
        _default_start = date_min
        _default_end = date_max
    _default_start = max(_default_start, date_min)
    _default_end = min(_default_end, date_max)

    date_range = st.sidebar.date_input(
        "Date range",
        value=(_default_start, _default_end),
        min_value=date_min,
        max_value=date_max,
    )

    filtered = df[df["bank"].isin(selected_banks)].copy()
    if len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["date"].dt.date >= start) & (filtered["date"].dt.date <= end)
        ]

    st.sidebar.divider()
    st.sidebar.caption(f"{len(filtered):,} transactions loaded")
    st.sidebar.caption("Add PDFs → `statements/` and run `/process-statements`")

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


# ── Page 1: Dashboard ─────────────────────────────────────────────────────────
def page_dashboard(df: pd.DataFrame):
    st.title("Dashboard")
    st.caption("Monthly health at a glance + full history.")

    spend = real_spend(df)
    income = real_income(df)

    if spend.empty and income.empty:
        st.info("No data in the selected range.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    _today = pd.Timestamp.today()
    _cur_month = _today.to_period("M").to_timestamp()
    _prev_month = (_today - pd.DateOffset(months=1)).to_period("M").to_timestamp()

    cur_spend = spend[spend["month_dt"] == _cur_month]["amount"].abs().sum()
    prev_spend = spend[spend["month_dt"] == _prev_month]["amount"].abs().sum()
    spend_delta = ((cur_spend - prev_spend) / prev_spend * 100) if prev_spend else 0

    cur_income = income[income["month_dt"] == _cur_month]["amount"].sum()
    if cur_income == 0:
        # Use trailing 3-month average if current month has no income yet
        last3 = income[income["month_dt"] >= (_today - pd.DateOffset(months=3)).to_period("M").to_timestamp()]
        n_months = max(last3["month_dt"].nunique(), 1)
        cur_income = last3["amount"].sum() / n_months

    cur_net = cur_income - cur_spend

    _ytd_start = _today.replace(month=1, day=1)
    ytd_income = income[income["date"] >= _ytd_start]["amount"].sum()
    ytd_spend = spend[spend["date"] >= _ytd_start]["amount"].abs().sum()
    ytd_rate = ((ytd_income - ytd_spend) / ytd_income * 100) if ytd_income > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "This Month Spend",
        fmt_eur(cur_spend),
        delta=f"{spend_delta:+.1f}% vs last month",
        delta_color="inverse",
        help="Real spend this calendar month vs last month",
    )
    c2.metric("This Month Income", fmt_eur(cur_income), help="Income received this month (or 3-month avg if month is new)")
    c3.metric(
        "Net This Month",
        fmt_eur(cur_net),
        delta=f"{(cur_net/cur_income*100):.1f}% of income" if cur_income else None,
        delta_color="normal",
    )
    c4.metric("YTD Savings Rate", f"{ytd_rate:.1f}%", help="(Income − Spend) / Income, year to date")

    # ── Monthly income vs spend chart ─────────────────────────────────────────
    st.markdown('<p class="section-header">Monthly Income vs Spend</p>', unsafe_allow_html=True)

    m_inc = monthly_agg(income).rename(columns={"amount": "income"})
    m_spd = monthly_agg(spend, abs_val=True).rename(columns={"amount": "spend"})
    monthly_flow = pd.merge(m_inc, m_spd, on="month_dt", how="outer").fillna(0).sort_values("month_dt")
    monthly_flow["net"] = monthly_flow["income"] - monthly_flow["spend"]

    fig_flow = go.Figure()
    fig_flow.add_trace(go.Bar(
        x=monthly_flow["month_dt"], y=monthly_flow["income"],
        name="Income", marker_color="#98FB98",
        hovertemplate="<b>%{x|%b %Y}</b><br>Income: €%{y:,.2f}<extra></extra>",
    ))
    fig_flow.add_trace(go.Bar(
        x=monthly_flow["month_dt"], y=monthly_flow["spend"],
        name="Spend", marker_color=ACCENT_NEGATIVE,
        hovertemplate="<b>%{x|%b %Y}</b><br>Spend: €%{y:,.2f}<extra></extra>",
    ))
    fig_flow.add_trace(go.Scatter(
        x=monthly_flow["month_dt"], y=monthly_flow["net"],
        name="Net Savings", mode="lines+markers",
        line=dict(color=ACCENT_WARNING, width=2), marker=dict(size=5),
        hovertemplate="<b>%{x|%b %Y}</b><br>Net: €%{y:,.2f}<extra></extra>",
    ))
    fig_flow.update_layout(
        barmode="group",
        xaxis_tickformat="%b %Y",
        legend=dict(orientation="h", y=-0.15),
        **chart_defaults(),
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    col_left, col_right = st.columns(2)

    # ── Spend by category horizontal bar ─────────────────────────────────────
    with col_left:
        st.markdown('<p class="section-header">Spend by Category</p>', unsafe_allow_html=True)
        cat_spend = (
            spend.groupby("category")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
            .sort_values("total", ascending=True)
        )
        colors = [CATEGORY_COLORS.get(c, "#888") for c in cat_spend["category"]]
        fig_cat = go.Figure(go.Bar(
            x=cat_spend["total"],
            y=cat_spend["category"],
            orientation="h",
            marker_color=colors,
            hovertemplate="<b>%{y}</b><br>€%{x:,.2f}<extra></extra>",
        ))
        fig_cat.update_layout(
            xaxis_title="EUR",
            yaxis=dict(tickfont=dict(size=11)),
            **chart_defaults(),
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    # ── Year-over-year table ──────────────────────────────────────────────────
    with col_right:
        st.markdown('<p class="section-header">Year-over-Year Summary</p>', unsafe_allow_html=True)
        yoy = yearly_summary(df)
        if not yoy.empty:
            yoy_display = yoy.copy()
            yoy_display["Income"] = yoy_display["Income"].apply(fmt_eur)
            yoy_display["Spend"] = yoy_display["Spend"].apply(fmt_eur)
            yoy_display["Net"] = yoy_display["Net"].apply(fmt_eur)
            yoy_display["Savings Rate %"] = yoy_display["Savings Rate %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(
                yoy_display,
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Insufficient data for year-over-year comparison.")


# ── Page 2: Spending ──────────────────────────────────────────────────────────
def page_spending(df: pd.DataFrame):
    st.title("Spending")
    st.caption("Where your money goes — by category and subcategory.")

    spend = real_spend(df)

    if spend.empty:
        st.info("No spending data in the selected range.")
        return

    total_spend = spend["amount"].abs().sum()
    n_months = max(spend["month_dt"].nunique(), 1)
    avg_monthly = total_spend / n_months
    top_cat = spend.groupby("category")["amount"].apply(lambda x: x.abs().sum()).idxmax()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Spend", fmt_eur(total_spend))
    c2.metric("Avg Monthly Spend", fmt_eur(avg_monthly))
    c3.metric("Biggest Category", top_cat.title())

    tab1, tab2 = st.tabs(["By Category", "By Subcategory"])

    # ── Tab 1: By Category ────────────────────────────────────────────────────
    with tab1:
        col_left, col_right = st.columns([1, 2])

        with col_left:
            st.markdown('<p class="section-header">Category Breakdown</p>', unsafe_allow_html=True)
            cat = (
                spend.groupby("category")["amount"]
                .apply(lambda x: x.abs().sum())
                .reset_index()
                .rename(columns={"amount": "total"})
                .sort_values("total", ascending=False)
            )
            cat["pct"] = (cat["total"] / cat["total"].sum() * 100).round(1)
            cat["avg/mo"] = (cat["total"] / n_months).apply(fmt_eur)
            cat["total_fmt"] = cat["total"].apply(fmt_eur)
            st.dataframe(
                cat[["category", "total_fmt", "pct", "avg/mo"]].rename(
                    columns={"category": "Category", "total_fmt": "Total", "pct": "%", "avg/mo": "Avg/Month"}
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
                    x="month_dt", y="amount", color="category",
                    color_discrete_map=CATEGORY_COLORS,
                    labels={"month_dt": "Month", "amount": "EUR", "category": "Category"},
                    barmode="stack",
                )
                fig.update_layout(xaxis_tickformat="%b %Y", **chart_defaults())
                st.plotly_chart(fig, use_container_width=True)

    # ── Tab 2: By Subcategory ─────────────────────────────────────────────────
    with tab2:
        if "subcategory" not in df.columns:
            st.warning("`subcategory` column not found. Re-run `/clean-data` to generate it.")
            return

        spend["subcategory"] = spend["subcategory"].fillna("unclassified")
        spendable_cats = sorted(spend["category"].dropna().unique().tolist())
        selected_cat = st.selectbox("Select category", spendable_cats, key="subcat_selector")
        cat_spend = spend[spend["category"] == selected_cat]

        sub_total = cat_spend["amount"].abs().sum()
        n_tx = len(cat_spend)
        n_sub = cat_spend["subcategory"].nunique()
        m1, m2, m3 = st.columns(3)
        m1.metric("Category Spend", fmt_eur(sub_total))
        m2.metric("Transactions", n_tx)
        m3.metric("Subcategories", n_sub)

        sub_agg = (
            cat_spend.groupby("subcategory")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
            .sort_values("total", ascending=False)
        )
        sub_agg["pct"] = (sub_agg["total"] / sub_agg["total"].sum() * 100).round(1)
        tx_counts = cat_spend.groupby("subcategory").size().reset_index(name="n_tx")
        sub_agg = sub_agg.merge(tx_counts, on="subcategory", how="left")
        sub_agg["avg_tx"] = (sub_agg["total"] / sub_agg["n_tx"]).apply(fmt_eur)
        sub_agg["total_fmt"] = sub_agg["total"].apply(fmt_eur)

        colors_sub = px.colors.qualitative.Set3
        color_map = {sub: colors_sub[i % len(colors_sub)] for i, sub in enumerate(sub_agg["subcategory"])}

        col_l, col_r = st.columns([1, 2])
        with col_l:
            fig_donut = px.pie(
                sub_agg, names="subcategory", values="total",
                hole=0.45, color="subcategory", color_discrete_map=color_map,
            )
            fig_donut.update_traces(textposition="inside", textinfo="percent+label")
            fig_donut.update_layout(showlegend=False, **chart_defaults())
            st.plotly_chart(fig_donut, use_container_width=True)

        with col_r:
            monthly_sub = (
                cat_spend.groupby(["month_dt", "subcategory"])["amount"]
                .apply(lambda x: x.abs().sum())
                .reset_index()
            )
            if not monthly_sub.empty:
                fig_bar = px.bar(
                    monthly_sub, x="month_dt", y="amount", color="subcategory",
                    color_discrete_map=color_map,
                    labels={"month_dt": "Month", "amount": "EUR", "subcategory": "Subcategory"},
                    barmode="stack",
                )
                fig_bar.update_layout(xaxis_tickformat="%b %Y", **chart_defaults())
                st.plotly_chart(fig_bar, use_container_width=True)

        st.dataframe(
            sub_agg[["subcategory", "total_fmt", "pct", "n_tx", "avg_tx"]].rename(
                columns={
                    "subcategory": "Subcategory", "total_fmt": "Total",
                    "pct": "% of Category", "n_tx": "# Transactions", "avg_tx": "Avg / Tx",
                }
            ),
            hide_index=True, use_container_width=True,
        )

        st.markdown('<p class="section-header">Top Merchants per Subcategory</p>', unsafe_allow_html=True)
        for subcat in sub_agg["subcategory"].tolist():
            sub_rows = cat_spend[cat_spend["subcategory"] == subcat]
            merchants = (
                sub_rows.groupby("receiver")["amount"]
                .agg(total=lambda x: x.abs().sum(), count="count")
                .reset_index()
                .sort_values("total", ascending=False)
                .head(8)
            )
            merchants["total"] = merchants["total"].apply(fmt_eur)
            with st.expander(f"**{subcat}** — {fmt_eur(sub_rows['amount'].abs().sum())} ({len(sub_rows)} txns)"):
                st.dataframe(
                    merchants.rename(columns={"receiver": "Merchant", "total": "Total", "count": "# Tx"}),
                    hide_index=True, use_container_width=True,
                )


# ── Page 3: Income & Savings ──────────────────────────────────────────────────
def page_income_savings(df: pd.DataFrame):
    st.title("Income & Savings")
    st.caption("Earnings, savings rate trend, investments, and N26 Spaces.")

    income = real_income(df)
    spend = real_spend(df)
    investments = real_investments(df)

    if income.empty:
        st.info("No income data in the selected range.")
        return

    total_income = income["amount"].sum()
    total_invested = investments["amount"].abs().sum() if not investments.empty else 0.0
    total_spend = spend["amount"].abs().sum()
    net = total_income - total_spend
    true_rate = (net / total_income * 100) if total_income > 0 else 0.0

    spaces_df = df[df["account_type"] == "savings"].copy()
    net_spaces = spaces_df["amount"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Income", fmt_eur(total_income))
    c2.metric("Total Invested (ETF)", fmt_eur(total_invested), help="ETF contributions (subcategory: etf_investments)")
    c3.metric(
        "True Savings Rate",
        f"{true_rate:.1f}%",
        help="(Income − Real Spend) / Income",
        delta=f"{true_rate - 20:.1f}pp vs 20% target",
        delta_color="normal",
    )
    c4.metric("Net into N26 Spaces", fmt_eur(net_spaces), help="Total net flow into all N26 Spaces")

    # ── Income by source ──────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">Income by Source</p>', unsafe_allow_html=True)
        if "subcategory" in income.columns:
            inc_by_sub = (
                income.groupby("subcategory")["amount"]
                .sum()
                .reset_index()
                .rename(columns={"amount": "total"})
                .sort_values("total", ascending=True)
            )
            inc_by_sub["subcategory"] = inc_by_sub["subcategory"].fillna("unclassified")
            fig_inc = px.bar(
                inc_by_sub, x="total", y="subcategory", orientation="h",
                labels={"subcategory": "Source", "total": "EUR"},
                color_discrete_sequence=[ACCENT_PRIMARY],
            )
            fig_inc.update_layout(**chart_defaults(), showlegend=False)
            st.plotly_chart(fig_inc, use_container_width=True)
        else:
            inc_by_cat = (
                income.groupby("category")["amount"].sum().reset_index().rename(columns={"amount": "total"})
            )
            st.dataframe(inc_by_cat, hide_index=True, use_container_width=True)

    # ── Monthly savings rate ──────────────────────────────────────────────────
    with col_right:
        st.markdown('<p class="section-header">Monthly Savings Rate</p>', unsafe_allow_html=True)
        sr = savings_rate_series(df)
        if not sr.empty:
            fig_sr = go.Figure()
            fig_sr.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_dash="dot")
            fig_sr.add_hline(y=20, line_color=ACCENT_PRIMARY, line_dash="dash",
                             annotation_text="20% target", annotation_position="top right")
            fig_sr.add_trace(go.Scatter(
                x=sr["month_dt"], y=sr["rate"],
                mode="lines+markers",
                line=dict(color=ACCENT_WARNING, width=2),
                marker=dict(size=5, color=[ACCENT_PRIMARY if r >= 0 else ACCENT_NEGATIVE for r in sr["rate"]]),
                fill="tozeroy",
                fillcolor="rgba(0,229,180,0.07)",
                hovertemplate="<b>%{x|%b %Y}</b><br>Savings rate: %{y:.1f}%<extra></extra>",
            ))
            fig_sr.update_layout(yaxis_title="Savings Rate %", xaxis_tickformat="%b %Y", **chart_defaults())
            st.plotly_chart(fig_sr, use_container_width=True)

    # ── ETF contributions ─────────────────────────────────────────────────────
    if not investments.empty:
        st.markdown('<p class="section-header">Investment Contributions Over Time</p>', unsafe_allow_html=True)
        m_inv = monthly_agg(investments, abs_val=True).rename(columns={"amount": "invested"})
        fig_etf = px.bar(
            m_inv, x="month_dt", y="invested",
            labels={"month_dt": "Month", "invested": "EUR"},
            color_discrete_sequence=[ACCENT_PRIMARY],
        )
        fig_etf.update_layout(xaxis_tickformat="%b %Y", **chart_defaults(), showlegend=False)
        st.plotly_chart(fig_etf, use_container_width=True)

    # ── N26 Spaces ────────────────────────────────────────────────────────────
    if not spaces_df.empty:
        st.markdown('<p class="section-header">N26 Spaces</p>', unsafe_allow_html=True)
        space_summary = (
            spaces_df.groupby("space")["amount"]
            .agg(total="sum", count="count")
            .reset_index()
            .sort_values("total", ascending=False)
        )
        space_summary["total_fmt"] = space_summary["total"].apply(fmt_eur)

        col_l, col_r = st.columns(2)
        with col_l:
            fig_sp = px.bar(
                space_summary, x="space", y="total",
                color="space",
                labels={"space": "Space", "total": "EUR"},
                title="Net flow per Space",
                color_discrete_sequence=[ACCENT_PRIMARY, "#87CEEB", "#96CEB4", "#FFEAA7", "#DDA0DD"],
            )
            fig_sp.update_layout(**chart_defaults(), showlegend=False)
            st.plotly_chart(fig_sp, use_container_width=True)
        with col_r:
            st.dataframe(
                space_summary[["space", "total_fmt", "count"]].rename(
                    columns={"space": "Space", "total_fmt": "Net Flow", "count": "Transactions"}
                ),
                hide_index=True, use_container_width=True,
            )
    else:
        st.info("No N26 Space transactions in the selected range.")

    # ── What-if scenarios ─────────────────────────────────────────────────────
    with st.expander("What if I spent less on X? — Category reduction scenarios"):
        st.caption("How much could you save per year by cutting each category by 20%, invested at 7% for 10 years?")
        spend_by_cat = (
            spend.groupby("category")["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .rename(columns={"amount": "total"})
            .sort_values("total", ascending=False)
        )
        _n_mo = max(spend["month_dt"].nunique(), 1)
        spend_by_cat["Annual Est."] = (spend_by_cat["total"] / _n_mo * 12).apply(fmt_eur)
        spend_by_cat["Save 20%/yr"] = (spend_by_cat["total"] / _n_mo * 12 * 0.20).apply(fmt_eur)
        _fv_factor = ((1 + 0.07 / 12) ** 120 - 1) / (0.07 / 12)
        spend_by_cat["@ 7% 10yr"] = (spend_by_cat["total"] / _n_mo * 12 * 0.20 / 12 * _fv_factor).apply(fmt_eur)
        spend_by_cat["total"] = spend_by_cat["total"].apply(fmt_eur)
        st.dataframe(
            spend_by_cat.rename(columns={"category": "Category", "total": "Seen in Data"}),
            hide_index=True, use_container_width=True,
        )


# ── Page 4: Merchants & Subscriptions ────────────────────────────────────────
def page_merchants(df: pd.DataFrame):
    st.title("Merchants & Subscriptions")
    st.caption("Who you pay the most, recurring charges, and transport breakdown.")

    spend = real_spend(df)

    if spend.empty:
        st.info("No spending data in the selected range.")
        return

    top_merchant_row = (
        spend.groupby("receiver")["amount"]
        .apply(lambda x: x.abs().sum())
        .reset_index()
        .sort_values("amount", ascending=False)
        .iloc[0] if len(spend) > 0 else None
    )

    sub_annual = 0.0
    if "subcategory" in spend.columns:
        subs = spend[spend["subcategory"] == "software_subscriptions"]
        n_mo = max(subs["month_dt"].nunique(), 1)
        sub_annual = subs["amount"].abs().sum() / n_mo * 12

    n_merchants = spend["receiver"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Top Merchant",
        top_merchant_row["receiver"] if top_merchant_row is not None else "—",
        delta=fmt_eur(top_merchant_row["amount"]) if top_merchant_row is not None else None,
        delta_color="off",
    )
    c2.metric("Subscription Spend (ann.)", fmt_eur(sub_annual), help="software_subscriptions subcategory, annualised")
    c3.metric("Distinct Merchants", str(n_merchants))

    # ── Top 20 merchants ──────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Top 20 Merchants by Spend</p>', unsafe_allow_html=True)
    top20 = (
        spend.groupby(["receiver", "category"])
        .agg(total=("amount", lambda x: x.abs().sum()), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
        .head(20)
    )

    top20_sorted = top20.sort_values("total", ascending=True)
    colors_top = [CATEGORY_COLORS.get(c, "#888") for c in top20_sorted["category"]]
    fig_top = go.Figure(go.Bar(
        x=top20_sorted["total"],
        y=top20_sorted["receiver"],
        orientation="h",
        marker_color=colors_top,
        customdata=top20_sorted[["category", "count"]].values,
        hovertemplate="<b>%{y}</b><br>€%{x:,.2f}<br>%{customdata[0]} · %{customdata[1]} txns<extra></extra>",
    ))
    fig_top.update_layout(xaxis_title="Total Spend (EUR)", **chart_defaults())
    st.plotly_chart(fig_top, use_container_width=True)

    total_spend = spend["amount"].abs().sum()
    top5_spend = top20.head(5)["total"].sum()
    top5_pct = top5_spend / total_spend * 100 if total_spend else 0
    st.caption(f"Your top 5 merchants account for **{top5_pct:.1f}%** of total spend ({fmt_eur(top5_spend)}).")

    col_left, col_right = st.columns(2)

    # ── Recurring merchants ───────────────────────────────────────────────────
    with col_left:
        st.markdown('<p class="section-header">Recurring Merchants (≥3 appearances)</p>', unsafe_allow_html=True)
        rec = detect_recurring(df, min_occurrences=3)
        if rec.empty:
            st.write("Not enough data to detect recurring merchants.")
        else:
            rec_display = rec.head(20).copy()
            rec_display["avg"] = rec_display["avg"].apply(fmt_eur)
            rec_display["annual_est"] = rec_display["annual_est"].apply(fmt_eur)
            rec_display["total"] = rec_display["total"].apply(fmt_eur)
            st.dataframe(
                rec_display[["receiver", "count", "avg", "annual_est"]].rename(
                    columns={"receiver": "Merchant", "count": "# Times", "avg": "Avg/Txn", "annual_est": "Annual Est."}
                ),
                hide_index=True, use_container_width=True,
            )

    # ── Software subscriptions ────────────────────────────────────────────────
    with col_right:
        st.markdown('<p class="section-header">Software Subscriptions</p>', unsafe_allow_html=True)
        if "subcategory" in spend.columns:
            subs_df = spend[spend["subcategory"] == "software_subscriptions"].copy()
            if subs_df.empty:
                st.write("No software subscription transactions detected.")
            else:
                subs_agg = (
                    subs_df.groupby("receiver")["amount"]
                    .agg(total=lambda x: x.abs().sum(), count="count")
                    .reset_index()
                    .sort_values("total", ascending=False)
                )
                _n_mo_sub = max(subs_df["month_dt"].nunique(), 1)
                subs_agg["monthly_est"] = (subs_agg["total"] / _n_mo_sub).apply(fmt_eur)
                subs_agg["total"] = subs_agg["total"].apply(fmt_eur)
                st.dataframe(
                    subs_agg.rename(columns={"receiver": "Service", "total": "Total Paid", "count": "# Txns", "monthly_est": "~Monthly"}),
                    hide_index=True, use_container_width=True,
                )
        else:
            st.write("Subcategory data not available. Run `/clean-data` first.")

    # ── PayPal breakdown ──────────────────────────────────────────────────────
    st.markdown('<p class="section-header">PayPal Breakdown</p>', unsafe_allow_html=True)
    paypal = spend[spend["payment_method"] == "paypal"].copy()
    if paypal.empty:
        st.write("No PayPal transactions in this range.")
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
            hide_index=True, use_container_width=True,
        )

    # ── Transport deep dive ───────────────────────────────────────────────────
    st.markdown('<p class="section-header">Transport Deep Dive</p>', unsafe_allow_html=True)
    transport = spend[spend["category"] == "transport"].copy()
    if transport.empty:
        st.write("No transport transactions in this range.")
    else:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            m_transport = monthly_agg(transport, abs_val=True).rename(columns={"amount": "total"})
            fig_tr = px.bar(
                m_transport, x="month_dt", y="total",
                labels={"month_dt": "Month", "total": "EUR"},
                color_discrete_sequence=[CATEGORY_COLORS["transport"]],
                title="Monthly transport spend",
            )
            fig_tr.update_layout(xaxis_tickformat="%b %Y", **chart_defaults(), showlegend=False)
            st.plotly_chart(fig_tr, use_container_width=True)

        with col_t2:
            if "subcategory" in transport.columns:
                tr_sub = (
                    transport.groupby("subcategory")["amount"]
                    .apply(lambda x: x.abs().sum())
                    .reset_index()
                    .rename(columns={"amount": "total"})
                    .sort_values("total", ascending=False)
                )
                tr_sub["subcategory"] = tr_sub["subcategory"].fillna("unclassified")
                tr_sub["total_fmt"] = tr_sub["total"].apply(fmt_eur)
                st.dataframe(
                    tr_sub[["subcategory", "total_fmt"]].rename(
                        columns={"subcategory": "Subcategory", "total_fmt": "Total"}
                    ),
                    hide_index=True, use_container_width=True,
                )
            else:
                top_tr = (
                    transport.groupby("receiver")["amount"]
                    .apply(lambda x: x.abs().sum())
                    .reset_index()
                    .sort_values("amount", ascending=False)
                    .head(10)
                )
                top_tr["amount"] = top_tr["amount"].apply(fmt_eur)
                st.dataframe(top_tr.rename(columns={"receiver": "Merchant", "amount": "Total"}),
                             hide_index=True, use_container_width=True)


# ── Page 5: Transactions ──────────────────────────────────────────────────────
def page_transactions(df: pd.DataFrame):
    st.title("Transactions")
    st.caption("Search, filter, and edit categorizations inline.")

    all_cats = sorted(
        set(list(CATEGORY_COLORS.keys())) | set(df["category"].dropna().unique().tolist())
    )
    all_subcats = sorted(df["subcategory"].dropna().unique().tolist()) if "subcategory" in df.columns else []

    # ── Inline filters ────────────────────────────────────────────────────────
    tx_type = st.radio("Type", ["All", "Debit", "Credit"], horizontal=True, key="tx_type_filter")

    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 1, 2])
    with col_f1:
        sel_cats = st.multiselect("Category", all_cats, key="tx_cat_filter")
    with col_f2:
        subcat_opts = (
            sorted(df[df["category"].isin(sel_cats)]["subcategory"].dropna().unique().tolist())
            if sel_cats else all_subcats
        )
        sel_subcats = st.multiselect("Subcategory", subcat_opts, key="tx_subcat_filter")
    with col_f3:
        banks = sorted(df["bank"].dropna().unique().tolist())
        sel_banks = st.multiselect("Bank", banks, key="tx_bank_filter")
    with col_f4:
        search = st.text_input("Search merchant / description", placeholder="e.g. Rewe, Netflix…", label_visibility="visible")

    # Apply local filters (additive on top of sidebar)
    view = df.copy()
    if sel_cats:
        view = view[view["category"].isin(sel_cats)]
    if sel_subcats:
        view = view[view["subcategory"].isin(sel_subcats)]
    if sel_banks:
        view = view[view["bank"].isin(sel_banks)]
    if tx_type == "Debit":
        view = view[view["type"] == "debit"]
    elif tx_type == "Credit":
        view = view[view["type"] == "credit"]
    if search:
        mask = (
            view["receiver"].str.contains(search, case=False, na=False)
            | view["description"].str.contains(search, case=False, na=False)
        )
        view = view[mask]

    debits = view[view["type"] == "debit"]
    credits = view[view["type"] == "credit"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Transactions", f"{len(view):,}")
    c2.metric("Total Debit", fmt_eur(debits["amount"].abs().sum()))
    c3.metric("Total Credit", fmt_eur(credits["amount"].sum()))

    st.markdown('<p class="section-header">Transactions</p>', unsafe_allow_html=True)

    has_subcategory = "subcategory" in view.columns
    edit_cols = ["date", "receiver", "description", "amount", "category"] + \
                (["subcategory"] if has_subcategory else []) + \
                ["type", "bank", "payment_method", "city"]
    display = view[edit_cols].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")

    edited = st.data_editor(
        display,
        column_config={
            "date": st.column_config.TextColumn("Date", disabled=True),
            "receiver": st.column_config.TextColumn("Receiver"),
            "description": st.column_config.TextColumn("Description", disabled=True),
            "amount": st.column_config.NumberColumn("Amount (EUR)", format="€%.2f", disabled=True),
            "category": st.column_config.SelectboxColumn("Category", options=all_cats, required=True),
            **({"subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subcats, required=False)}
               if has_subcategory else {}),
            "type": st.column_config.TextColumn("Type", disabled=True),
            "bank": st.column_config.TextColumn("Bank", disabled=True),
            "payment_method": st.column_config.TextColumn("Method", disabled=True),
            "city": st.column_config.TextColumn("City", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key=f"tx_editor_{'_'.join(sel_cats) or 'all'}",
    )

    cat_changed = display["category"] != edited["category"]
    sub_changed = (
        display["subcategory"].fillna("") != edited["subcategory"].fillna("")
        if has_subcategory else pd.Series(False, index=display.index)
    )
    rec_changed = display["receiver"].fillna("") != edited["receiver"].fillna("")
    changed_mask = cat_changed | sub_changed | rec_changed
    n_changed = int(changed_mask.sum())

    save_col, info_col = st.columns([1, 4])
    with save_col:
        save_clicked = st.button("Save changes", type="primary", disabled=(n_changed == 0))
    with info_col:
        if n_changed > 0:
            st.info(f"{n_changed} row(s) modified — not yet saved.")

    if save_clicked:
        raw = pd.read_csv(CUMULATIVE_CSV)
        for orig_idx in changed_mask[changed_mask].index:
            raw.at[orig_idx, "category"] = edited.at[orig_idx, "category"]
            if has_subcategory:
                raw.at[orig_idx, "subcategory"] = edited.at[orig_idx, "subcategory"]
            raw.at[orig_idx, "receiver"] = edited.at[orig_idx, "receiver"]
        raw.to_csv(CUMULATIVE_CSV, index=False)
        st.cache_data.clear()
        st.success(f"Saved {n_changed} change(s) to `{CUMULATIVE_CSV}`.")
        st.rerun()


# ── Page 6: Pipeline & Data ───────────────────────────────────────────────────
def page_pipeline(df: pd.DataFrame):
    st.title("Pipeline & Data")
    st.caption("Statement processing status, data quality, and foreign currency transactions.")

    entries = load_pipeline_status_data()
    processed_entries = [e for e in entries if e.get("status") == "processed"]
    pending_entries = [e for e in entries if e.get("status") == "pending"]
    total = len(entries)
    n_processed = len(processed_entries)
    n_pending = len(pending_entries)
    total_tx = sum(e.get("transaction_count") or 0 for e in processed_entries)

    date_min = df["date"].min().strftime("%Y-%m-%d") if not df.empty else "—"
    date_max = df["date"].max().strftime("%Y-%m-%d") if not df.empty else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Processed Statements", n_processed)
    c2.metric("Pending Statements", n_pending)
    c3.metric("Total Transactions", f"{total_tx:,}")
    c4.metric("Data Range", f"{date_min} → {date_max}")

    if total > 0:
        progress = n_processed / total
        st.progress(progress, text=f"{progress*100:.0f}% of statements processed")

    if not entries:
        st.info("No statements discovered yet. Add PDFs to `statements/` and run `/process-statements`.")
        return

    # ── Processed statements ──────────────────────────────────────────────────
    if processed_entries:
        st.markdown('<p class="section-header">Processed Statements</p>', unsafe_allow_html=True)
        processed_df = pd.DataFrame([
            {
                "File": e["filename"],
                "Transactions": e.get("transaction_count") or 0,
                "Processed At": (e.get("processed_at") or "")[:19].replace("T", " "),
                "Output CSV": (e.get("output") or {}).get("csv", ""),
            }
            for e in processed_entries
        ])

        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.dataframe(processed_df, hide_index=True, use_container_width=True)
        with col_r:
            fig = go.Figure(go.Bar(
                x=processed_df["Transactions"],
                y=processed_df["File"],
                orientation="h",
                marker_color=ACCENT_PRIMARY,
                hovertemplate="<b>%{y}</b><br>%{x} transactions<extra></extra>",
            ))
            fig.update_layout(
                title="Transactions per statement",
                yaxis=dict(autorange="reversed"),
                **chart_defaults(),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Pending statements ────────────────────────────────────────────────────
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

    # ── Data quality ──────────────────────────────────────────────────────────
    if not df.empty:
        st.markdown('<p class="section-header">Data Quality</p>', unsafe_allow_html=True)
        n = len(df)
        quality = [
            {"Dimension": "With city", "Count": int(df["city"].notna().sum()), "Coverage %": f"{df['city'].notna().mean()*100:.1f}%"},
            {"Dimension": "With subcategory", "Count": int(df["subcategory"].notna().sum()) if "subcategory" in df.columns else 0,
             "Coverage %": f"{df['subcategory'].notna().mean()*100:.1f}%" if "subcategory" in df.columns else "0%"},
            {"Dimension": "Foreign currency", "Count": int(df["currency_original"].notna().sum()), "Coverage %": f"{df['currency_original'].notna().mean()*100:.1f}%"},
            {"Dimension": "Internal transfers", "Count": int(df["is_internal_transfer"].astype(str).str.lower().eq("true").sum()),
             "Coverage %": f"{df['is_internal_transfer'].astype(str).str.lower().eq('true').mean()*100:.1f}%"},
            {"Dimension": "Total transactions", "Count": n, "Coverage %": "100%"},
        ]
        st.dataframe(pd.DataFrame(quality), hide_index=True, use_container_width=True)

    # ── Foreign currency / Travel ─────────────────────────────────────────────
    fx = df[df["currency_original"].notna()].copy() if not df.empty else pd.DataFrame()
    with st.expander(f"Foreign Currency Transactions ({len(fx)} rows)"):
        if fx.empty:
            st.info("No foreign currency transactions in the selected range.")
        else:
            total_fx_eur = fx["amount"].abs().sum()
            currencies = fx["currency_original"].nunique()
            cities = fx["city"].dropna().nunique()
            f1, f2, f3 = st.columns(3)
            f1.metric("Total FX Spend (EUR)", fmt_eur(total_fx_eur))
            f2.metric("Currencies", str(currencies))
            f3.metric("Cities", str(cities))

            col_l, col_r = st.columns(2)
            with col_l:
                by_ccy = (
                    fx.groupby("currency_original")["amount"]
                    .apply(lambda x: x.abs().sum())
                    .reset_index()
                    .rename(columns={"amount": "EUR equivalent"})
                    .sort_values("EUR equivalent", ascending=False)
                )
                fig_ccy = px.bar(
                    by_ccy, x="currency_original", y="EUR equivalent",
                    color="currency_original",
                    labels={"currency_original": "Currency"},
                    title="By currency",
                    color_discrete_sequence=["#FF6B35", "#45B7D1", "#FFEAA7", "#DDA0DD"],
                )
                fig_ccy.update_layout(**chart_defaults(), showlegend=False)
                st.plotly_chart(fig_ccy, use_container_width=True)

            with col_r:
                by_city = (
                    fx[fx["city"].notna()].groupby("city")["amount"]
                    .apply(lambda x: x.abs().sum())
                    .reset_index()
                    .rename(columns={"amount": "EUR equivalent"})
                    .sort_values("EUR equivalent", ascending=True)
                )
                if not by_city.empty:
                    fig_city = px.bar(
                        by_city, x="EUR equivalent", y="city",
                        orientation="h",
                        labels={"city": "City"},
                        title="By city",
                        color_discrete_sequence=[CATEGORY_COLORS["transport"]],
                    )
                    fig_city.update_layout(**chart_defaults())
                    st.plotly_chart(fig_city, use_container_width=True)

            detail = fx[["date", "receiver", "city", "currency_original", "amount_original", "exchange_rate", "amount", "bank"]].copy()
            detail["date"] = detail["date"].dt.strftime("%Y-%m-%d")
            detail["amount"] = detail["amount"].apply(lambda x: fmt_eur(abs(x)))
            detail["amount_original"] = detail.apply(
                lambda r: f"{r['amount_original']:,.2f} {r['currency_original']}" if pd.notna(r["amount_original"]) else "",
                axis=1,
            )
            detail["exchange_rate"] = detail["exchange_rate"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")
            st.dataframe(
                detail.rename(columns={
                    "date": "Date", "receiver": "Merchant", "city": "City",
                    "currency_original": "Currency", "amount_original": "Original Amount",
                    "exchange_rate": "Rate", "amount": "EUR Amount", "bank": "Bank",
                }),
                hide_index=True, use_container_width=True,
            )

            amex_fx = fx[fx["bank"] == "Amex"]["amount"].abs().sum()
            if amex_fx > 0:
                st.info(f"Estimated Amex FX fees (2%): {fmt_eur(amex_fx * 0.02)} on {fmt_eur(amex_fx)} of foreign spend.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    df = load_data()

    if df.empty:
        st.warning("No data found. Run `/process-statements` then `/clean-data` first.")
        return

    page, filtered = sidebar(df)

    dispatch = {
        "Dashboard":                 page_dashboard,
        "Spending":                  page_spending,
        "Income & Savings":          page_income_savings,
        "Merchants & Subscriptions": page_merchants,
        "Transactions":              page_transactions,
        "Pipeline & Data":           page_pipeline,
    }

    dispatch[page](filtered)


if __name__ == "__main__":
    main()
