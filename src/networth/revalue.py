"""Gold layer: revalue holdings daily and attribute every change to a cause.

Produces two tables (see specs/valuation.md):
  - daily_valuation:   per account per day, quantity x that-day rate -> EGP & USD value.
  - pnl_attribution:   per day, net-worth change split into contributions vs unrealized
                       FX vs unrealized gold.

Attribution identity (holds exactly when rates align with transfer anchors):
    delta(net_worth) == external_flow + unrealized_fx + unrealized_gold
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config


def build_positions(
    entries: pd.DataFrame,
    accounts: pd.DataFrame,
    idx: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Per account, daily balance in the account's own currency.

    Starts from each account's `initial_balance` and lays the daily `delta` cumulatively over
    the date index.
    """
    pos = pd.DataFrame(index=idx)
    for _, a in accounts.iterrows():
        e = entries[entries["account_pk"] == a["pk"]]
        daily = e.groupby("date")["delta"].sum().reindex(idx, fill_value=0.0)
        pos[a["pk"]] = a["initial_balance"] + daily.cumsum()
    return pos


def build_daily_valuation(pos: pd.DataFrame, accounts: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    acc = accounts.set_index("pk")
    usd = rates["USD"]
    frames = []
    for pk in pos.columns:
        ccy = acc.loc[pk, "currency"]
        rate = rates[ccy] if ccy in rates.columns else pd.Series(1.0, index=pos.index)
        value_egp = pos[pk] * rate
        frames.append(
            pd.DataFrame(
                {
                    "date": pos.index,
                    "account": acc.loc[pk, "name"],
                    "currency": ccy,
                    "quantity": pos[pk].to_numpy(),
                    "rate_egp": rate.to_numpy(),
                    "value_egp": value_egp.to_numpy(),
                    "rate_usd": (rate / usd).to_numpy(),
                    "value_usd": (value_egp / usd).to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _currency_totals(pos: pd.DataFrame, accounts: pd.DataFrame, currency: str) -> pd.Series:
    acc = accounts.set_index("pk")
    pks = [pk for pk in pos.columns if acc.loc[pk, "currency"] == currency]
    if not pks:
        return pd.Series(0.0, index=pos.index)
    return pos[pks].sum(axis=1)


def build_attribution(
    entries: pd.DataFrame,
    pos: pd.DataFrame,
    accounts: pd.DataFrame,
    rates: pd.DataFrame,
    valuation: pd.DataFrame,
) -> pd.DataFrame:
    idx = pos.index
    nw_egp = valuation.groupby("date")["value_egp"].sum().reindex(idx)
    nw_usd = valuation.groupby("date")["value_usd"].sum().reindex(idx)

    def _egp_by_day(rows: pd.DataFrame) -> pd.Series:
        """Daily EGP total of a set of entries, each valued at its day's rate."""
        if rows.empty:
            return pd.Series(0.0, index=idx)
        rate = [
            rates[ccy].get(d, 1.0) if ccy in rates.columns else 1.0
            for ccy, d in zip(rows["account_currency"], rows["date"])
        ]
        egp = pd.Series(rows["delta"].to_numpy() * rate, index=pd.DatetimeIndex(rows["date"]))
        return egp.groupby(level=0).sum().reindex(idx, fill_value=0.0)

    # Contributions = real income/expense ("add to stats" ON). Booked/realized gains are the
    # entries you flagged out of stats (e.g. marking an investment gain). Transfers are internal.
    external_flow = _egp_by_day(entries[entries["flow_type"] == "cashflow"])
    realized_gain = _egp_by_day(entries[entries["flow_type"] == "adjustment"])

    # Unrealized: yesterday's holdings revalued by today's rate change.
    ufx = pd.Series(0.0, index=idx)
    ugold = pd.Series(0.0, index=idx)
    for ccy in config.FIAT_FX:
        ufx += _currency_totals(pos, accounts, ccy).shift(1).fillna(0.0) * rates[ccy].diff().fillna(0.0)
    for ccy in config.ASSETS:
        ugold += _currency_totals(pos, accounts, ccy).shift(1).fillna(0.0) * rates[ccy].diff().fillna(0.0)

    out = pd.DataFrame(
        {
            "date": idx,
            "net_worth_egp": nw_egp.to_numpy(),
            "net_worth_usd": nw_usd.to_numpy(),
            "external_flow": external_flow.to_numpy(),
            "realized_gain": realized_gain.to_numpy(),
            "unrealized_fx": ufx.to_numpy(),
            "unrealized_gold": ugold.to_numpy(),
        }
    )
    out["total_change"] = (
        out["external_flow"] + out["realized_gain"] + out["unrealized_fx"] + out["unrealized_gold"]
    )
    return out


@dataclass
class GoldLayer:
    daily_valuation: pd.DataFrame
    pnl_attribution: pd.DataFrame


def revalue(normalized, rates: pd.DataFrame) -> GoldLayer:
    idx = rates.index
    pos = build_positions(normalized.entries, normalized.accounts, idx)
    valuation = build_daily_valuation(pos, normalized.accounts, rates)
    attribution = build_attribution(normalized.entries, pos, normalized.accounts, rates, valuation)
    return GoldLayer(valuation, attribution)
