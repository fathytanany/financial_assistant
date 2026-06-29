"""RateSource interface + a shared Stooq fetcher (free, keyless, daily history)."""

from __future__ import annotations

import io
from abc import ABC, abstractmethod

import pandas as pd
import requests


class RateSource(ABC):
    """A daily EGP-per-currency series provider."""

    currency: str

    @abstractmethod
    def fetch(self) -> pd.Series:  # index: date, values: EGP per 1 unit of `currency`
        ...


def fetch_stooq(symbol: str) -> pd.Series:
    """Daily close series for a Stooq symbol (e.g. ``usdegp``, ``xauusd``)."""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    if "Close" not in df.columns or "Date" not in df.columns:
        return pd.Series(dtype=float)
    return pd.Series(df["Close"].to_numpy(), index=pd.to_datetime(df["Date"])).sort_index()
