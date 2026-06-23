# Data model — Budget Flow backup (decoded & validated)

The backup is an Apple **Core Data** SQLite store. All app data lives in one wide table
`ZITEM`, discriminated by `Z_ENT` (names in `Z_PRIMARYKEY.Z_NAME`). `ACHANGE`,
`ATRANSACTION`, `Z_MODELCACHE` are Core Data internals — ignore.

## Entities we use
- **Account** `Z_ENT=10`: `ZNAME`, `ZCURRENCYCODE`, `ZINITIALBALANCE`,
  `ZEXCHANGERATE` (current EGP-per-unit; EGP = 1.0 ⇒ **base = EGP**), `ZISARCHIVED`.
  The app stores only the *latest* rate — no history.
- **TransactionGroup** `Z_ENT=19` = the real money entry: `ZACCOUNT1`→account PK,
  `ZAMOUNT1` = amount **in the source currency**, `ZTYPE1` (0=income, 1=expense),
  `ZEXCHANGERATE1` = rate (source-per-account-ccy), `ZSOURCECURRENCYCODE`/
  `ZTARGETCURRENCYCODE`, `ZDATE2` = date, `ZCONTRAENTRY`→PK of the other leg of a transfer.
- **Transaction** `Z_ENT=18` = wrapper only (`ZTRANSACTIONGROUP2` + date); ignore for value.

Dates are seconds since 2001-01-01 → `datetime(col + 978307200, 'unixepoch')`.
There is **no balance table** (`Z_ENT=11` has 0 rows) — balances are computed.

## Balance reconstruction (validated)
For an account with currency `cA`, for each of its group rows:

```
delta = ZAMOUNT1                 if ZSOURCECURRENCYCODE == cA
      = ZAMOUNT1 / ZEXCHANGERATE1   otherwise   # amount is in the source ccy
balance = ZINITIALBALANCE + Σ delta
```

This reproduces sane balances (Gold 1.865 XAU, Cib USD $10,269; net worth ≈ 1.91M EGP ≈
$38.3K at the validation snapshot). Implemented in `normalize.py`.

## Rate anchors (the key win)
A cross-currency **transfer** (`{src,tgt}` = `{EGP, ccy}`, `is_transfer == True`) stores the
**actual rate used that day** in `ZEXCHANGERATE1`. EGP-per-ccy = `rate` if `tgt == ccy` else
`1/rate`. These give real historical anchors; external feeds only fill the daily gaps.
Implemented in `rates.extract_anchors`.

> Gotcha: standalone income/expense entries on a foreign account (not transfers) may store a
> degenerate `ZEXCHANGERATE1 = 1.0` (the app's "no rate set" sentinel). These are **not**
> conversions — `extract_anchors` skips non-transfer rows and any `rate == 1.0`, otherwise the
> series would crater to 1.0 on that day and the USD/gold valuation would spike (the bug fixed
> for e.g. 2025-07-22 USD and 2025-05-30 XAU).

## Gold-layer output tables
- `daily_valuation(date, account, currency, quantity, rate_egp, rate_usd, value_egp, value_usd)`
- `pnl_attribution(date, net_worth_egp, net_worth_usd, external_flow, unrealized_fx,
  unrealized_gold, unrealized_stock, total_change)`

## Edge cases / notes
- Credit-card accounts may have sign quirks — confirm against the app if a balance looks off.
- Transfers appear as two `ZCONTRAENTRY`-linked rows; `is_transfer` flags them in `entries`.
- `ZAMOUNT1` for a gold/USD *buy* attached to the asset account is in EGP (the source); the
  divide-by-rate branch converts it to the asset quantity.
