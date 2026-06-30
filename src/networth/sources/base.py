"""RateSource interface + shared keyless HTTP helpers.

Sources return EGP-per-currency. Stooq's free CSV feed was retired behind a JavaScript
anti-bot wall (it now serves a challenge page, not CSV), so live rates come from two free,
keyless JSON APIs instead: open.er-api.com (FX) and api.gold-api.com (gold spot). These give
the *latest* quote rather than full history, so a fetch returns a single-point series dated
today — enough to anchor today's valuation; the timeline between transaction anchors is still
interpolated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

import pandas as pd
import requests

_HEADERS = {"User-Agent": "networth/1.0"}


class RateSource(ABC):
    """A daily EGP-per-currency series provider."""

    currency: str

    @abstractmethod
    def fetch(self) -> pd.Series:  # index: date, values: EGP per 1 unit of `currency`
        ...


def _today_series(value: float) -> pd.Series:
    return pd.Series([float(value)], index=[pd.Timestamp.now().normalize()])


@lru_cache(maxsize=1)
def fetch_usd_base_rates() -> dict[str, float]:
    """Latest FX rates with USD as base (e.g. ``{"EGP": 49.5, "AED": 3.67, ...}``) from
    open.er-api.com — free and keyless. Cached so one pipeline run hits the API once."""
    r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=20, headers=_HEADERS)
    r.raise_for_status()
    return {k: float(v) for k, v in r.json()["rates"].items()}


@lru_cache(maxsize=1)
def fetch_gold_usd() -> float:
    """Latest gold price in USD per troy ounce from api.gold-api.com — free and keyless."""
    r = requests.get("https://api.gold-api.com/price/XAU", timeout=20, headers=_HEADERS)
    r.raise_for_status()
    return float(r.json()["price"])
