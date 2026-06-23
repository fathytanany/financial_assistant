"""Private interactive net-worth dashboard (Streamlit).

Reads the gold layer produced by the pipeline (locally or from S3) and renders it. It does
NO heavy computation — all truth-tracking happens upstream in the Python core.

Run locally:  uv run --extra dashboard streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from networth.pipeline import ATTRIBUTION_KEY, INSIGHTS_KEY, VALUATION_KEY  # noqa: E402
from networth.storage import get_storage  # noqa: E402

st.set_page_config(page_title="Net worth", page_icon="📈", layout="wide")
storage = get_storage()


@st.cache_data(ttl=3600)
def load():
    v, a, i = storage.get(VALUATION_KEY), storage.get(ATTRIBUTION_KEY), storage.get(INSIGHTS_KEY)
    val = pd.read_parquet(v) if v else None
    attr = pd.read_parquet(a) if a else None
    text = Path(i).read_text(encoding="utf-8") if i else ""
    return val, attr, text


val, attr, insights = load()
if attr is None or val is None:
    st.info("No data yet — run `uv run python -m networth.pipeline` first.")
    st.stop()

attr["date"] = pd.to_datetime(attr["date"])
val["date"] = pd.to_datetime(val["date"])
# EGP/USD spot per day, derived from the two net-worth series.
attr["usd_rate"] = (attr["net_worth_egp"] / attr["net_worth_usd"]).replace([float("inf")], pd.NA)

cur = st.sidebar.radio("Currency", ["EGP", "USD"], horizontal=True)
sym = "E£" if cur == "EGP" else "$"
nw_col = "net_worth_egp" if cur == "EGP" else "net_worth_usd"
min_d, max_d = attr["date"].min().date(), attr["date"].max().date()
start = st.sidebar.date_input("From", value=max(min_d, (attr["date"].max() - pd.Timedelta(days=365)).date()),
                              min_value=min_d, max_value=max_d)

a = attr[attr["date"] >= pd.Timestamp(start)].copy()
factor = pd.Series(1.0, index=a.index) if cur == "EGP" else (1.0 / a["usd_rate"])
fmt = lambda x: f"{sym}{x:,.0f}"  # noqa: E731

flows = (a["external_flow"] * factor).cumsum()
ufx = (a["unrealized_fx"] * factor)
ugold = (a["unrealized_gold"] * factor)
change = a[nw_col].iloc[-1] - a[nw_col].iloc[0]
contrib = (a["external_flow"] * factor).sum()

st.title("Net worth")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Net worth", fmt(a[nw_col].iloc[-1]))
c2.metric("Change (window)", fmt(change))
c3.metric("Real gain (excl. deposits)", fmt(change - contrib))
c4.metric("You put in (window)", fmt(contrib))

# Net worth vs. contributions
base = a[nw_col].iloc[0]
fig = go.Figure()
fig.add_scatter(x=a["date"], y=a[nw_col], name="Net worth", fill="tozeroy",
                line=dict(color="#378ADD"))
fig.add_scatter(x=a["date"], y=base + flows, name="Contributions",
                line=dict(color="#888780", dash="dash"))
fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), yaxis_tickprefix=sym,
                  legend=dict(orientation="h"))
st.subheader("Net worth vs. money you put in")
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)

# Allocation (latest day)
last_day = val["date"].max()
vcol = "value_egp" if cur == "EGP" else "value_usd"
alloc = (val[val["date"] == last_day].groupby("account")[vcol].sum())
alloc = alloc[alloc > 0]
pie = go.Figure(go.Pie(labels=alloc.index, values=alloc.to_numpy(), hole=0.6))
pie.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
left.subheader("Where it sits today")
left.plotly_chart(pie, width="stretch")

# Monthly attribution
m = a.set_index("date")
monthly = pd.DataFrame({
    "Savings added": (m["external_flow"] * factor.values).resample("ME").sum(),
    "FX moves": (m["unrealized_fx"] * factor.values).resample("ME").sum(),
    "Gold moves": (m["unrealized_gold"] * factor.values).resample("ME").sum(),
})
bar = go.Figure()
for col, color in [("Savings added", "#B4B2A9"), ("FX moves", "#378ADD"), ("Gold moves", "#EF9F27")]:
    bar.add_bar(x=monthly.index, y=monthly[col], name=col, marker_color=color)
bar.update_layout(barmode="relative", height=320, margin=dict(l=0, r=0, t=10, b=0),
                  yaxis_tickprefix=sym, legend=dict(orientation="h"))
right.subheader("What moved it (monthly)")
right.plotly_chart(bar, width="stretch")

if insights:
    st.subheader("Insights")
    st.markdown(insights)
