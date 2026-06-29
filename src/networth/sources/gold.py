"""Gold source: EGP per troy ounce = XAU/USD price x USD/EGP rate (both from Stooq)."""

from __future__ import annotations

import pandas as pd

from .base import RateSource, fetch_stooq


class StooqGold(RateSource):
    currency = "XAU"

    def fetch(self) -> pd.Series:
        try:
            xau_usd = fetch_stooq("xauusd")   # USD per ounce
            usd_egp = fetch_stooq("usdegp")   # EGP per USD
            if xau_usd.empty or usd_egp.empty:
                return pd.Series(dtype=float)
            idx = xau_usd.index.union(usd_egp.index)
            return (xau_usd.reindex(idx).ffill() * usd_egp.reindex(idx).ffill()).dropna()
        except Exception:
            return pd.Series(dtype=float)
