# Roadmap (deferred)

v1 deliberately stays lean. Candidates, each a clean extension of an existing seam:

## EGX / Thndr per-holding pricing
Today Thndr is a manual lump EGP balance, so stock gains can't be separated from deposits.
To fix: maintain a small holdings file (ticker + quantity) and add an EGX `RateSource`
(price per share). Then revalue stocks like any other asset → `unrealized_stock` becomes real
and the manual weekly reconcile disappears. Slots into `sources/` + `revalue.py` with no
architectural change. Free, reliable EGX history is the open problem.

## Parallel / black-market EGP rate
v1 uses the official EGP series, which diverged hugely from reality in 2022–2024. Add an
alternate `RateSource` (or a manual override table) for the parallel rate and let the dashboard
switch between "official" and "real" views.

## More
- Realized vs unrealized split (track cost basis through sells).
- Per-holding P&L table in the dashboard from anchor cost basis.
- Additional assets/brokers (crypto detail, more metals).
- Backfill historical external rates fully (currently anchors + interpolation suffice).
