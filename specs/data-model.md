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
  `ZTARGETCURRENCYCODE`, `ZDATE2` = date, `ZCONTRAENTRY`→PK of the other leg of a transfer,
  `ZINCLUDEINSTATISTICS` = the app's "add to stats" toggle (1 = real income/expense,
  0 = excluded from stats).
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

This reproduces sane balances (Gold [redacted], Cib USD [redacted]; net worth ≈ [redacted] ≈
[redacted] at the validation snapshot). Implemented in `normalize.py`.

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

## Entry classification (`flow_type`)
`normalize.py` tags every TransactionGroup so attribution knows what each entry *means*:
- **transfer** — `ZCONTRAENTRY` is set (an internal move between your own accounts, recorded
  as two related +/− legs). Net-zero across the portfolio; never a contribution.
- **cashflow** — not a transfer **and** `ZINCLUDEINSTATISTICS = 1`: a real income/expense, i.e.
  money you actually added or spent → a **contribution**.
- **adjustment** — not a transfer **and** `ZINCLUDEINSTATISTICS = 0`: an entry you flagged out
  of stats, used to **book a gain/loss or correction** (e.g. marking a Thndr/IBKR investment
  gain). Counts as a realized/booked gain, **not** a contribution. Any unlinked internal moves
  that happen to be stats-off simply net to ~0 here, so they don't distort.

## Gold-layer output tables
- `daily_valuation(date, account, currency, quantity, rate_egp, rate_usd, value_egp, value_usd)`
- `pnl_attribution(date, net_worth_egp, net_worth_usd, external_flow, realized_gain,
  unrealized_fx, unrealized_gold, total_change)`
  where `external_flow` = cashflow entries, `realized_gain` = adjustment entries.

## Opening reconciliation (validated against the app)
Compared against a full app screenshot, **13 of 19 accounts reconstruct to the displayed
balance to the cent** — the transaction model is sound. The exceptions:

- **Cash** was off by exactly one *future-dated* entry. The app doesn't count a planned
  transaction until its date; `normalize` now drops `date > today`, and Cash matches.
- **Both credit cards + `Cib Account`** carry a charge from *before* tracking began that Budget
  Flow applies to the displayed balance but never exports as a transaction. The result is a
  wrong `ZINITIALBALANCE`, off by a **constant** — proven: the offset is identical to the cent
  across 4 backups spanning days of new transactions (e.g. the Cib card is −[redacted] every
  time; recomputing the implied app value reproduces the prior manual reconcile exactly). It is
  *not* derivable from the backup (no balance is cached anywhere — the `Balance` entity
  `Z_ENT=11` has 0 rows). `normalize(opening_adjustments=...)` adds the one-time per-account
  offset (from `opening_adjustments.json`, data store only) onto `initial_balance`, so every
  downstream step is correction-unaware. Credit cards are flagged by `ZTYPE = 2` (regular = 0,
  asset/investment = 3/4).

## Edge cases / notes
- Credit-card accounts may have sign quirks — confirm against the app if a balance looks off.
- Transfers appear as two `ZCONTRAENTRY`-linked rows; `is_transfer` flags them in `entries`.
- `ZAMOUNT1` for a gold/USD *buy* attached to the asset account is in EGP (the source); the
  divide-by-rate branch converts it to the asset quantity.
