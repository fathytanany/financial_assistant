"""Fiat FX source: EGP-per-currency derived from open.er-api.com's USD-based rates."""

from __future__ import annotations

import pandas as pd

from .base import RateSource, _today_series, fetch_usd_base_rates


class ErApiFx(RateSource):
    def __init__(self, currency: str):
        self.currency = currency

    def fetch(self) -> pd.Series:
        try:
            rates = fetch_usd_base_rates()               # units of X per 1 USD
            egp_per_usd = rates["EGP"]                   # EGP per USD
            per_usd = rates[self.currency]              # `currency` per USD
            return _today_series(egp_per_usd / per_usd)  # -> EGP per `currency`
        except Exception:
            return pd.Series(dtype=float)
