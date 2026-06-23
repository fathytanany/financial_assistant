# Valuation & attribution (the truth engine)

Goal: separate *real performance* from *money added* and from *EGP devaluation*.

## Daily series (`revalue.py`)
For each day `d`:
- `position[account, d]` = `ZINITIALBALANCE` + cumulative `delta` up to `d` (account ccy),
  forward-filled daily (`build_positions`).
- `rate_egp[ccy, d]` = dense daily ccy→EGP series from `rates.build_daily_rates`
  (anchors + current rate + optional external, interpolated).
- `value_egp = position × rate_egp`; `value_usd = value_egp / rate_egp[USD]`.
- `net_worth[d] = Σ value_egp` (and USD).

## Attribution (`build_attribution`)
Per day:
- `external_flow` = Σ `delta × rate_egp` over **non-transfer** income/expense entries
  (transfers are internal and net to zero across the portfolio).
- `unrealized_fx` = Σ over USD/AED/SAR of `position(d-1) × Δrate_egp(d)`.
- `unrealized_gold` = same for XAU.
- `total_change = external_flow + unrealized_fx + unrealized_gold (+ unrealized_stock)`.

### Identity
`Δ net_worth(d) == total_change(d)` holds exactly when the rate series equals the transfer
anchor on transfer dates (it does, since anchors define the series). Asserted in
`tests/test_revalue.py::test_attribution_identity`. Small residuals can appear with external
rates merged — keep a tolerance.

### Why this answers the question
"Real gain" = `net_worth − cumulative external_flow`. The dashboard plots net worth against
cumulative contributions; the gap is unrealized gain. Comparing the EGP vs USD net-worth lines
shows how much of an EGP "gain" is just the pound weakening.

## Known v1 limitations
- **Stocks (Thndr):** a manually-updated lump EGP balance. If updates are entered as income,
  stock appreciation shows up as a *contribution*, not a gain, until a real holdings source is
  added (`specs/roadmap.md`).
- **EGP rate** is the official series only (no parallel/black-market rate) for v1.
