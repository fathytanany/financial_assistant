"""External rate sources (Adapter pattern).

Each source returns a daily ``pd.Series`` of EGP-per-currency. They are *enhancements*:
the pipeline already works offline from transaction anchors + current rates, so any source
failing (e.g. no network in CI) degrades gracefully to an empty series.
"""

from __future__ import annotations

import pandas as pd

from .. import config
from .fx import StooqFx
from .gold import StooqGold


def fetch_external() -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for ccy in config.FIAT_FX:
        s = StooqFx(ccy).fetch()
        if not s.empty:
            out[ccy] = s
    gold = StooqGold().fetch()
    if not gold.empty:
        out["XAU"] = gold
    return out


def fetch_current_rates() -> dict[str, float]:
    """Latest live EGP-per-currency rates for today's valuation.

    AED/SAR are USD-pegged, so they're derived from USD/EGP when a direct quote is missing.
    Any source failing (e.g. no network) just drops out and the caller falls back to the
    backup's stored rate.
    """
    out: dict[str, float] = {}
    usd = StooqFx("USD").fetch()
    if not usd.empty:
        out["USD"] = float(usd.iloc[-1])
    for ccy in ("AED", "SAR"):
        s = StooqFx(ccy).fetch()
        if not s.empty:
            out[ccy] = float(s.iloc[-1])
    gold = StooqGold().fetch()
    if not gold.empty:
        out["XAU"] = float(gold.iloc[-1])
    if "USD" in out:
        out.setdefault("AED", out["USD"] / 3.6725)
        out.setdefault("SAR", out["USD"] / 3.75)
    return out
