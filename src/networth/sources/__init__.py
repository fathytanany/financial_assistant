"""External rate sources (Adapter pattern).

Each source returns a daily ``pd.Series`` of EGP-per-currency. They are *enhancements*:
the pipeline already works offline from transaction anchors + current rates, so any source
failing (e.g. no network in CI) degrades gracefully to an empty series.
"""

from __future__ import annotations

import pandas as pd

from .. import config
from .fx import ErApiFx
from .gold import GoldApi


def fetch_external() -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for ccy in config.FIAT_FX:
        s = ErApiFx(ccy).fetch()
        if not s.empty:
            out[ccy] = s
    gold = GoldApi().fetch()
    if not gold.empty:
        out["XAU"] = gold
    return out


def fetch_current_rates() -> dict[str, float]:
    """Latest live EGP-per-currency rates for today's valuation.

    Sourced keyless from open.er-api.com (FX) + api.gold-api.com (gold). Any source failing
    (e.g. no network) just drops out and the caller falls back to the backup's stored rate.
    """
    out: dict[str, float] = {}
    for ccy in config.FIAT_FX:
        s = ErApiFx(ccy).fetch()
        if not s.empty:
            out[ccy] = float(s.iloc[-1])
    gold = GoldApi().fetch()
    if not gold.empty:
        out["XAU"] = float(gold.iloc[-1])
    return out
