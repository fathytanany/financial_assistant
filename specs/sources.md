# Rate sources

`RateSource` (`sources/base.py`) is the adapter: each returns a daily `pd.Series` of
**EGP per 1 unit** of its currency. Sources are *enhancements* — the pipeline already works
offline from transaction anchors + the account's current rate, so a failing/blocked source
degrades to an empty series (important for CI with no network).

## Implemented
- **`StooqFx(currency)`** (`fx.py`) — free, keyless daily history from Stooq via the
  `{ccy}egp` pair (e.g. `usdegp`).
- **`StooqGold`** (`gold.py`) — EGP per troy ounce = `xauusd` (USD/oz) × `usdegp` (EGP/USD).

`sources.fetch_external()` gathers all of them into `{currency: series}` for
`rates.build_daily_rates(..., external=...)`.

## Merge precedence (`rates.build_daily_rates`)
Per non-base currency, combine: transaction **anchors** + the **current** account rate at the
snapshot date + optional **external** series → group by date (mean) → reindex daily →
`interpolate("time")` → `ffill` → `bfill`. EGP is always 1.0.

## Notes / gotchas
- ECB/Frankfurter is **not** usable — it doesn't publish EGP/AED/SAR.
- AED and SAR are USD-pegged (~3.6725 / ~3.75 per USD), so flat-ish series are expected; if a
  Stooq pair is missing they fall back to anchors + current rate.

## Adding a source
Subclass `RateSource`, implement `fetch()` returning EGP-per-ccy daily, and include it in
`fetch_external()`. No other code changes. (This is also how EGX stock pricing will slot in —
see `specs/roadmap.md`.)
