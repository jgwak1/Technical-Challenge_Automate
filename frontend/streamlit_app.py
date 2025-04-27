"""Streamlit dashboard for interacting with the Invoice API."""
import os
import streamlit as st
import pandas as pd
import requests
import altair as alt

# 1️⃣  Where to find the API root
API_ROOT = (
    st.secrets.get("API_ROOT")               # ← .streamlit/secrets.toml or Cloud “Secrets”
    or os.getenv("API_ROOT")                 # ← container / CI / docker-compose
    or "http://localhost:8000"               # ← last-ditch local default
)

st.set_page_config(page_title="Invoice Dashboard", layout="wide")
st.title("📊 Invoice Dashboard")

# ---- Helpers ---------------------------------------------------------------

def _safe_get(url: str, timeout: float = 10):
    """GET wrapper that shows nice Streamlit errors instead of hard crashes."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ API request failed: {e}")
        st.stop()

@st.cache_data(ttl=12 * 60 * 60)  # 12 h
def get_companies():
    return _safe_get(f"{API_ROOT}/companies")

@st.cache_data(ttl=5 * 60)        # 5 min
def get_company_data(name: str):
    invoices = _safe_get(f"{API_ROOT}/company/{name}/invoices")
    metrics  = _safe_get(f"{API_ROOT}/company/{name}/metrics")
    return pd.DataFrame(invoices), metrics

# ---- UI --------------------------------------------------------------------

companies = get_companies()
if not companies:
    st.warning("No companies found. Is the backend running at `{API_ROOT}`?")
    st.stop()

company = st.selectbox("Select a company", companies)

invoices_df, metrics = get_company_data(company)

st.subheader("Invoice List")
st.dataframe(invoices_df, use_container_width=True, hide_index=True)

st.metric("Average Days-to-Pay", metrics.get("average_days_to_pay", "—"))
st.metric("Min Days-to-Pay", metrics.get("min_days_to_pay", "—"))
st.metric("Max Days-to-Pay", metrics.get("max_days_to_pay", "—"))


st.subheader("Monthly Totals (Invoice vs Paid)")

# Build the DataFrame from whatever `metrics` returns
monthly = pd.DataFrame(metrics.get("monthly_totals", []))

if not monthly.empty:
    # Keep only the columns we need
    monthly = monthly[["month", "invoice_total", "paid_total"]]

    # Reshape to long format for Altair
    melted = monthly.melt(
        id_vars="month",
        value_vars=["invoice_total", "paid_total"],
        var_name="Type",
        value_name="Amount",
    )

    # Grouped-bar chart (xOffset gives the side-by-side effect)
    chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("month:N", title="Month"),
            xOffset="Type:N",
            y=alt.Y("Amount:Q", title="USD"),
            color=alt.Color("Type:N", legend=alt.Legend(title="")),
            tooltip=["month", "Type", "Amount"],
        )
        .properties(height=400, width="container")
    )

    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No monthly data yet.")


threshold = metrics.get("average_days_to_pay", "—")
st.subheader(f"Late Invoices Beyond Average Days-to-Pay (> {threshold} days)")
late = metrics.get("late_invoices_gt_avg_dtp", [])
if late:
    st.write(", ".join(late))
else:
    st.success("No late invoices 🎉")


st.subheader(f"Late Invoices (> 30 days)")
late = metrics.get("late_invoices_gt_30", [])
if late:
    st.write(", ".join(late))
else:
    st.success("No late invoices 🎉")