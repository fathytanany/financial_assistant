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
