"""Daily ccy->EGP rate series.

Built from three inputs, in order of trust:
  1. Anchors embedded in the user's own cross-currency transfers (the exact rate used
     on that date) — always available, offline.
  2. The account's current rate at the snapshot date.
  3. Optional external daily series (see sources/) to fill gaps between anchors.

Gaps are linearly interpolated then forward/back filled, so the series is dense daily.
"""

from __future__ import annotations

import pandas as pd

from . import config


def extract_anchors(entries: pd.DataFrame, currency: str) -> pd.Series:
    """Real EGP-per-`currency` rates pulled from genuine {EGP, currency} conversions.

    Only *transfers* carry a real conversion rate. Standalone income/expense entries on a
    foreign account may store a degenerate ``rate = 1.0`` (the app's "no rate set" sentinel);
    trusting those would crater the series and spike the USD/gold valuation. We skip both.
    """
    pairs = entries.apply(
        lambda r: {r["src"], r["tgt"]} == {config.BASE_CURRENCY, currency}
        and bool(r["is_transfer"])
        and bool(r["rate"])
        and r["rate"] > 0
        and abs(r["rate"] - 1.0) > 1e-9,
        axis=1,
    )
    e = entries[pairs]
    if e.empty:
        return pd.Series(dtype=float)
    # Stored rate is source-per-target. EGP-per-ccy = rate if ccy is the target, else 1/rate.
    rate_egp = [
        (rate if tgt == currency else 1.0 / rate) for rate, tgt in zip(e["rate"], e["tgt"])
    ]
    s = pd.Series(rate_egp, index=pd.DatetimeIndex(e["date"]))
    return s.groupby(level=0).mean()


def build_daily_rates(
    entries: pd.DataFrame,
    accounts: pd.DataFrame,
    external: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Dense daily DataFrame indexed by date, one column per currency (EGP == 1.0)."""
    start = entries["date"].min()
    snapshot = min(entries["date"].max(), pd.Timestamp.today().normalize())
    idx = pd.date_range(start, snapshot, freq="D")

    current = accounts.dropna(subset=["rate_egp"]).groupby("currency")["rate_egp"].last()
    cols: dict[str, pd.Series] = {config.BASE_CURRENCY: pd.Series(1.0, index=idx)}

    for ccy in config.NON_BASE:
        pts = extract_anchors(entries, ccy)
        if ccy in current.index:
            pts = pd.concat([pts, pd.Series({snapshot: current[ccy]})])
        if external and ccy in external and not external[ccy].empty:
            pts = pd.concat([pts, external[ccy]])
        if pts.empty:
            cols[ccy] = pd.Series(1.0, index=idx)
            continue
        pts = pts.groupby(level=0).mean().sort_index()
        dense = (
            pts.reindex(idx.union(pts.index))
            .interpolate(method="time")
            .reindex(idx)
            .ffill()
            .bfill()
        )
        cols[ccy] = dense

    return pd.DataFrame(cols).reindex(idx)


def to_sqlite(rates: pd.DataFrame, path) -> None:
    import sqlite3

    long = rates.reset_index(names="date").melt(
        id_vars="date", var_name="currency", value_name="rate_egp"
    )
    long["date"] = long["date"].dt.strftime("%Y-%m-%d")
    with sqlite3.connect(str(path)) as con:
        long.to_sql("rates", con, if_exists="replace", index=False)
