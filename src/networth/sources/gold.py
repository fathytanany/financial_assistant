"""Gold source: EGP per troy ounce = XAU/USD spot (api.gold-api.com) x USD/EGP (open.er-api)."""

from __future__ import annotations

import pandas as pd

from .base import RateSource, _today_series, fetch_gold_usd, fetch_usd_base_rates


class GoldApi(RateSource):
    currency = "XAU"

    def fetch(self) -> pd.Series:
        try:
            xau_usd = fetch_gold_usd()                   # USD per ounce
            egp_per_usd = fetch_usd_base_rates()["EGP"]  # EGP per USD
            return _today_series(xau_usd * egp_per_usd)  # -> EGP per ounce
        except Exception:
            return pd.Series(dtype=float)
