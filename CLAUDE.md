# CLAUDE.md

Persistent context for working on this repo. Read this first; deep dives live in `specs/`.

## What this is
A daily pipeline that turns the **Budget Flow** iOS app's SQLite backup into **truthful
net-worth tracking** — decomposing every change into *contributions* vs *unrealized FX* vs
*unrealized gold*, reported in EGP and USD. Also a portfolio piece (clean Python on public
GitHub). The core math is deterministic; **one** Claude step writes plain-language insights.

## Two problems it solves
1. Budget Flow doesn't record FX/gold rate changes, so real performance is invisible.
2. It doesn't price Egyptian stocks (a manual weekly chore). Stocks are deferred — see
   `specs/roadmap.md`.

## Hard rules
- **Never commit real financial data or secrets.** The backup, rates, gold layer, and the
  real dashboard live in S3 only. The repo is logic + a tiny synthetic test fixture.
- Keep it simple: fewest moving parts. Only two patterns — medallion (bronze/silver/gold) and
  the `RateSource` adapter. Don't add frameworks.
- The pipeline is idempotent: everything is rebuilt from `latest backup + rate history`.
- Round numbers that reach a screen.

## Architecture (medallion)
`ingest` (bronze) → `normalize` (silver) → `rates` + `sources/` → `revalue` (gold) →
`agent` (Claude) → `dashboard` (Streamlit). Code map in `src/networth/`. See
`specs/architecture.md`.

## Backup cheat-sheet (Core Data SQLite)
All data is in one wide table `ZITEM`, tagged by `Z_ENT`. Accounts = `Z_ENT=10`;
TransactionGroup (the real money entry) = `Z_ENT=19`; `Z_ENT=18` is a wrapper (ignore).
Dates = seconds since 2001-01-01 (add `978307200`). No balance table — balances are computed.
Full reference: `specs/data-model.md`.

**Balance rule (validated):** for account currency `cA`, per group row
`delta = ZAMOUNT1 if ZSOURCECURRENCYCODE == cA else ZAMOUNT1 / ZEXCHANGERATE1`;
`balance = ZINITIALBALANCE + Σ delta`. Cross-currency transfers store the *real rate used that
day* in `ZEXCHANGERATE1` → these are historical rate anchors. Validated net worth ≈ [redacted].

## Attribution (the truth engine) — `specs/valuation.md`
`Δ net_worth = external_flow + realized_gain + unrealized_fx + unrealized_gold`. Entries are
classified by `flow_type`: **transfer** (contra-linked, internal, net-zero), **cashflow**
(real income/expense, `ZINCLUDEINSTATISTICS=1`) → `external_flow` (contributions), and
**adjustment** (non-transfer, `ZINCLUDEINSTATISTICS=0`, i.e. the "add to stats" toggle off) →
`realized_gain` (booked investment gains/corrections). Unrealized = `yesterday's holdings ×
today's rate change`.

## Commands
```bash
uv sync                                                   # install (Python pinned to 3.12)
uv run python tests/make_fixture.py                       # (re)build the test fixture
uv run pytest                                             # tests
NETWORTH_BACKUP_DIR=. uv run python -m networth.pipeline  # run against a local backup
uv run --extra dashboard streamlit run dashboard/app.py   # dashboard
```

## Config / env (`src/networth/config.py`)
`NETWORTH_STORAGE` (local|s3), `NETWORTH_BACKUP_DIR`, `NETWORTH_DATA_DIR`,
`NETWORTH_S3_BUCKET`/`_PREFIX`, `ANTHROPIC_API_KEY`, `NETWORTH_CLAUDE_MODEL`.
Currencies are fixed for v1: EGP (base), USD, AED, SAR, XAU.

## Live rates, future entries & opening reconciliation
- The valuation series **extends to today** and anchors today at **live** rates
  (`sources.fetch_current_rates`), falling back to the backup's stored rate offline. So the
  daily cron keeps net worth current even with no new upload.
- **Future-dated entries are excluded** (`normalize` drops `date > today`): Budget Flow doesn't
  count a planned transaction until its date arrives, so neither do we.
- **Opening reconciliation (validated against the app).** 13/19 accounts reconstruct to the
  app's balance *to the cent* from transactions alone. Three accounts (both credit cards + the
  main `Cib Account`) carry a charge from before tracking that Budget Flow applies to the
  displayed balance but never exports — so their `ZINITIALBALANCE` is off by a **constant**
  (proven: identical to the cent across 4 days of changing transactions). `normalize` adds a
  one-time per-account offset from `opening_adjustments.json` (data store, gitignored / S3)
  straight onto `initial_balance`, so every downstream step is correction-unaware and each new
  upload still moves the balance correctly. The app's *total* will differ from ours — its FX/gold
  rates lag; ours are live. Match per-account **native** balances, not the app's EGP total.

## Specs index
`architecture.md` · `data-model.md` · `valuation.md` · `sources.md` · `dashboard.md` ·
`deployment.md` · `roadmap.md`
