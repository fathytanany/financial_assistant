# Dashboard (Streamlit)

`dashboard/app.py`. Reads the gold layer (`daily_valuation`, `pnl_attribution`) + `insights.md`
via `Storage` — locally in dev, from S3 in production. Does **no** ETL.

## Controls
- **Currency toggle** EGP / USD (sidebar). Net worth uses the stored series; EGP-only
  attribution components are converted with the per-day EGP/USD rate derived from
  `net_worth_egp / net_worth_usd`.
- **Date range** (from-date) filters all panels.

## Panels
1. **KPIs** — net worth, change over window, real gain (change − contributions), contributions.
2. **Net worth vs. contributions** — area line of net worth + dashed cumulative-contributions
   line; the gap is unrealized gain.
3. **Allocation** — donut of the latest day's holdings by account.
4. **What moved it** — monthly stacked bars: savings added / FX moves / gold moves.
5. **Insights** — the Claude markdown.

## Run / deploy
```bash
uv run --extra dashboard streamlit run dashboard/app.py     # local (reads data/)
```
Production: Streamlit Community Cloud, app set to **private with an email whitelist**, env
configured with `NETWORTH_STORAGE=s3` + AWS creds (read-only). See `specs/deployment.md`.

Keep displayed numbers rounded. Colors: net worth `#378ADD`, contributions `#888780`,
FX `#378ADD`, gold `#EF9F27`, savings `#B4B2A9`.
