# Data model — Budget Flow backup (decoded & validated)

The backup is an Apple **Core Data** SQLite store. All app data lives in one wide table
`ZITEM`, discriminated by `Z_ENT` (names in `Z_PRIMARYKEY.Z_NAME`). `ACHANGE`,
`ATRANSACTION`, `Z_MODELCACHE` are Core Data internals — ignore.

## Entities we use
- **Account** `Z_ENT=10`: `ZNAME`, `ZCURRENCYCODE`, `ZINITIALBALANCE`,
  `ZEXCHANGERATE` (current EGP-per-unit; EGP = 1.0 ⇒ **base = EGP**), `ZISARCHIVED`.
  The app stores only the *latest* rate — no history.
- **TransactionGroup** `Z_ENT=19` = the money definition: `ZACCOUNT1`→account PK,
  `ZAMOUNT1` = amount **in the source currency**, `ZTYPE1` (0=income, 1=expense),
  `ZEXCHANGERATE1` = rate (source-per-account-ccy), `ZSOURCECURRENCYCODE`/
  `ZTARGETCURRENCYCODE`, `ZCONTRAENTRY`→PK of the other leg of a transfer,
  `ZINCLUDEINSTATISTICS` = the app's "add to stats" toggle (1 = real income/expense,
  0 = excluded from stats). A group does **not** post to the ledger by itself.
- **Transaction** `Z_ENT=18` = a dated **occurrence** of a group (`ZTRANSACTIONGROUP2`→group PK,
  `ZDATE1` = date). This is the actual ledger row. A one-off entry is one group with one
  occurrence; a **recurring** entry is one group with *many* occurrences. The occurrence owns
  the date, the group owns the amount — so balances must sum occurrences, not groups (the group
  carries no date of its own that we rely on). This matches the app's own CSV export, which is
  one row per occurrence.

Dates are seconds since 2001-01-01 → `datetime(col + 978307200, 'unixepoch')`.
There is **no balance table** (`Z_ENT=11` has 0 rows) — balances are computed.

## Balance reconstruction (validated)
For each occurrence (Z_ENT=18), join its parent group (Z_ENT=19) for the money. For an account
with currency `cA`:

```
delta = ZAMOUNT1                 if ZSOURCECURRENCYCODE == cA
      = ZAMOUNT1 / ZEXCHANGERATE1   otherwise   # amount is in the source ccy
balance = ZINITIALBALANCE + Σ delta   (summed over occurrences)
```

Because recurring entries are now counted per occurrence, this matches the app's CSV export
**to the cent on every account**. Implemented in `normalize.py`.

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

## Full reconciliation against the app (validated, to the cent)
Every account reconstructs to the app's displayed balance exactly — verified against Budget
Flow's own CSV export (one row per occurrence). Two things were needed to get there:

- **Future-dated occurrences are excluded.** The app doesn't count a planned transaction until
  its date; `normalize` drops `date > today`.
- **Recurring entries must be counted per occurrence.** This was the source of the old "opening
  offset" mystery. A few accounts (the credit cards, flagged `ZTYPE = 2`, plus one current
  account) carry recurring entries. Summing *groups* counted each recurring entry once and so
  under-counted by a **constant** per account — which looked like a wrong `ZINITIALBALANCE`. It
  was stable across backups precisely because the recurring-occurrence count is stable while
  ordinary transactions change. Summing *occurrences* (`Z_ENT=18`) recovers it exactly — no
  per-account offset, no `opening_adjustments.json`. The earlier claim that this was "not
  derivable from the backup" was wrong: the occurrences were there all along in `Z_ENT=18`,
  previously dismissed as a wrapper.

## Edge cases / notes
- Credit-card accounts may have sign quirks — confirm against the app if a balance looks off.
- Transfers appear as two `ZCONTRAENTRY`-linked rows; `is_transfer` flags them in `entries`.
- `ZAMOUNT1` for a gold/USD *buy* attached to the asset account is in EGP (the source); the
  divide-by-rate branch converts it to the asset quantity.
