"""Fiat FX source: EGP-per-currency via Stooq's ``{ccy}egp`` pair (e.g. usdegp)."""

from __future__ import annotations

import pandas as pd

from .base import RateSource, fetch_stooq


class StooqFx(RateSource):
    def __init__(self, currency: str):
        self.currency = currency

    def fetch(self) -> pd.Series:
        try:
            return fetch_stooq(f"{self.currency.lower()}egp")
        except Exception:
            return pd.Series(dtype=float)
