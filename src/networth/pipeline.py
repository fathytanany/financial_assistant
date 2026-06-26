"""Orchestrate the daily run: ingest -> normalize -> rates -> revalue -> insights -> persist.

Idempotent: everything is rebuilt from the latest backup plus the (accumulating) rate history,
so re-running is always safe.
"""

from __future__ import annotations

import json

import pandas as pd

from . import agent, config, rates as rates_mod
from .ingest import ingest
from .normalize import normalize
from .revalue import revalue
from .storage import Storage, get_storage

# Artifact keys (also the S3 object names under the configured prefix).
RATES_KEY = "rates.sqlite"
VALUATION_KEY = "gold/daily_valuation.parquet"
ATTRIBUTION_KEY = "gold/pnl_attribution.parquet"
INSIGHTS_KEY = "insights.md"
# One-time per-account opening-balance reconciliation (see normalize.normalize). Real balances,
# so it lives in the data store (S3/local), never git.
OPENING_ADJUSTMENTS_KEY = "opening_adjustments.json"


def _save_df(storage: Storage, key: str, df: pd.DataFrame) -> None:
    path = storage.out_path(key)
    df.to_parquet(path, index=False)
    storage.put(key, path)


def _load_opening_adjustments(storage: Storage) -> dict[str, float]:
    path = storage.get(OPENING_ADJUSTMENTS_KEY)
    if not path:
        return {}
    try:
        return {k: float(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def run(storage: Storage | None = None) -> dict:
    storage = storage or get_storage()

    backup = ingest(storage)
    adjustments = _load_opening_adjustments(storage)
    norm = normalize(backup, opening_adjustments=adjustments)

    external: dict = {}
    current: dict = {}
    try:
        from . import sources

        external = sources.fetch_external()
        current = sources.fetch_current_rates()  # live rates for today's valuation
    except Exception:
        pass

    rates = rates_mod.build_daily_rates(norm.entries, norm.accounts, external, current_rates=current)
    gold = revalue(norm, rates)

    rates_path = storage.out_path(RATES_KEY)
    rates_mod.to_sqlite(rates, rates_path)
    storage.put(RATES_KEY, rates_path)

    _save_df(storage, VALUATION_KEY, gold.daily_valuation)
    _save_df(storage, ATTRIBUTION_KEY, gold.pnl_attribution)

    insights = agent.generate_insights(norm, gold)
    ins_path = storage.out_path(INSIGHTS_KEY)
    ins_path.write_text(insights, encoding="utf-8")
    storage.put(INSIGHTS_KEY, ins_path)

    summary = {
        "net_worth_egp": norm.net_worth_egp,
        "net_worth_usd": float(gold.pnl_attribution.iloc[-1]["net_worth_usd"]),
        "days": len(gold.pnl_attribution),
        "live_rates": current,
        "reconciled_accounts": adjustments,
        "as_of": gold.pnl_attribution.iloc[-1]["date"],
    }
    return summary


if __name__ == "__main__":
    s = run()
    rates_note = "live" if s["live_rates"] else "stored (no live fetch)"
    print(
        f"net worth: {s['net_worth_egp']:,.0f} EGP / {s['net_worth_usd']:,.0f} USD "
        f"as of {str(s['as_of'])[:10]} | rates: {rates_note} | reconciled: {len(s['reconciled_accounts'])}"
    )
