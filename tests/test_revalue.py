import numpy as np
import pandas as pd

from networth import rates as rates_mod
from networth.normalize import normalize
from networth.revalue import revalue


def _setup(fixture_backup):
    norm = normalize(fixture_backup)
    rates = rates_mod.build_daily_rates(norm.entries, norm.accounts)
    gold = revalue(norm, rates)
    return norm, rates, gold


def test_rate_series_uses_anchor_then_current(fixture_backup):
    _, rates, _ = _setup(fixture_backup)
    assert rates.loc[pd.Timestamp("2025-01-10"), "USD"] == 50   # transfer anchor
    assert round(rates["USD"].iloc[-1], 2) == 55                # today's (current) anchor
    assert rates.index[-1] >= pd.Timestamp("2025-01-15")        # series extended to today
    assert rates["XAU"].nunique() == 1                          # gold flat in fixture


def test_recurring_occurrences_step_the_series(fixture_backup):
    """The recurring -100 rent (one group, three occurrences) shows up as three separate
    month-by-month steps in Cash, not a single -100 hit."""
    norm, rates, gold = _setup(fixture_backup)
    v = gold.daily_valuation
    cash = v[v.account == "Cash"].sort_values("date").set_index("date")["value_egp"]
    for d in ("2025-01-20", "2025-02-20", "2025-03-20"):
        ts = pd.Timestamp(d)
        assert round(cash.loc[ts] - cash.loc[ts - pd.Timedelta(days=1)], 2) == -100.0


def test_anchors_ignore_standalone_and_unit_rate():
    """Only genuine conversions (transfers) with a real rate become anchors."""
    e = pd.DataFrame(
        [
            {"src": "USD", "tgt": "EGP", "rate": 0.02, "is_transfer": True,
             "date": pd.Timestamp("2025-03-01")},   # real conversion -> 50 EGP/USD
            {"src": "USD", "tgt": "EGP", "rate": 1.0, "is_transfer": False,
             "date": pd.Timestamp("2025-07-22")},   # standalone income, junk rate
            {"src": "EGP", "tgt": "USD", "rate": 1.0, "is_transfer": True,
             "date": pd.Timestamp("2025-08-01")},   # transfer but degenerate 1.0
        ]
    )
    anc = rates_mod.extract_anchors(e, "USD")
    assert list(anc.index) == [pd.Timestamp("2025-03-01")]
    assert round(anc.iloc[0], 2) == 50.0


def test_final_net_worth_matches_balances(fixture_backup):
    _, _, gold = _setup(fixture_backup)
    last = gold.daily_valuation["date"].max()
    nw = gold.daily_valuation.loc[gold.daily_valuation["date"] == last, "value_egp"].sum()
    assert round(nw, 2) == 307000.0


def test_attribution_components(fixture_backup):
    _, _, gold = _setup(fixture_backup)
    a = gold.pnl_attribution
    assert round(a["external_flow"].sum(), 2) == 0.0        # 500 income - 200 expense - 3x100 rent
    assert round(a["realized_gain"].sum(), 2) == 1000.0     # booked gain (stats off)
    assert round(a["unrealized_fx"].sum(), 2) == 1000.0     # USD 50 -> 55 on 200 units
    assert round(a["unrealized_gold"].sum(), 2) == 0.0


def test_attribution_identity(fixture_backup):
    """Day-over-day net-worth change equals the sum of its attributed causes."""
    _, _, gold = _setup(fixture_backup)
    a = gold.pnl_attribution
    delta_nw = a["net_worth_egp"].diff().to_numpy()[1:]
    total = a["total_change"].to_numpy()[1:]
    assert np.allclose(delta_nw, total, atol=1e-6)
