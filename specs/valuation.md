# Valuation & attribution (the truth engine)

Goal: separate *real performance* from *money added* and from *EGP devaluation*.

## Daily series (`revalue.py`)
For each day `d`:
- `position[account, d]` = `initial_balance` + cumulative `delta` up to `d` (account ccy),
  forward-filled daily (`build_positions`). `initial_balance` is the reconciled opening balance
  from `normalize` (a one-time per-account offset corrects accounts whose `ZINITIALBALANCE` is
  wrong; see `specs/data-model.md`), so `build_positions` itself needs no special-casing.
- `rate_egp[ccy, d]` = dense daily ccy→EGP series from `rates.build_daily_rates`
  (anchors + current rate + optional external, interpolated).
- `value_egp = position × rate_egp`; `value_usd = value_egp / rate_egp[USD]`.
- `net_worth[d] = Σ value_egp` (and USD).

## Attribution (`build_attribution`)
Entries are first classified by `flow_type` (see `specs/data-model.md`). Per day:
- `external_flow` = Σ `delta × rate_egp` over **cashflow** entries (real income/expense,
  "add to stats" ON) — the money you actually added or spent.
- `realized_gain` = Σ `delta × rate_egp` over **adjustment** entries (non-transfer, "add to
  stats" OFF) — gains/corrections you booked manually (e.g. a Thndr/IBKR investment gain).
- `unrealized_fx` = Σ over USD/AED/SAR of `position(d-1) × Δrate_egp(d)`.
- `unrealized_gold` = same for XAU.
- `total_change = external_flow + realized_gain + unrealized_fx + unrealized_gold`.

Transfers (`flow_type == "transfer"`) are excluded from all buckets — they're internal and
their two legs net to ~0.

### Identity
`Δ net_worth(d) == total_change(d)` holds exactly when the rate series equals the transfer
anchor on transfer dates (it does, since anchors define the series). Asserted in
`tests/test_revalue.py::test_attribution_identity`. Small residuals can appear with external
rates merged — keep a tolerance.

### Why this answers the question
"Real gain" = `net_worth − cumulative external_flow` = `realized_gain + unrealized_fx +
unrealized_gold`. The dashboard plots net worth against cumulative *contributions* (cashflow
only); the gap is your gain. Comparing the EGP vs USD net-worth lines shows how much of an EGP
"gain" is just the pound weakening.

## Known v1 limitations
- **Stocks (Thndr / IBKR):** no live per-share pricing. Their gains are whatever you book via
  stats-off `adjustment` entries — captured in `realized_gain`, but only as accurately as you
  record them. A real holdings source would make this automatic (`specs/roadmap.md`).
- **EGP rate** is the official series only (no parallel/black-market rate) for v1.
- `realized_gain` mixes booked investment gains with manual balance corrections — both are
  non-contribution net-worth changes, so the contributions-vs-gain split stays correct.
