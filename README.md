# Financial Assistant

Truthful multi-currency net-worth tracking, built from a budgeting app's daily backup.

Most budgeting apps tell you your balance. They **don't** tell you *why* it changed — how
much was new savings, how much was your home currency weakening, and how much was gold or
other assets moving. This project answers that, by ingesting the daily SQLite backup from the
[Budget Flow](https://apps.apple.com/us/app/budget-flow-expense-tracker/id1640091876) iOS app, enriching it with daily FX and
gold rates (and reusing the exact rates already embedded in your own transactions), and
decomposing every day's change into **contributions vs. unrealized FX vs. unrealized gold**.

> This repository contains **logic only** — no financial data and no secrets. The real backup,
> rates, and rendered dashboard live in private object storage (S3). See
> [`specs/deployment.md`](specs/deployment.md).

## How it works

A daily [medallion](https://en.wikipedia.org/wiki/Medallion_architecture) pipeline:

```
backup.sqlite ──► ingest ──► normalize ──► rates ──► revalue ──► agent ──► dashboard
   (bronze)                  (silver)              (gold)      (Claude)   (Streamlit)
```

| Stage | Module | What it does |
|-------|--------|--------------|
| ingest | `ingest.py` | fetch the latest backup from storage |
| normalize | `normalize.py` | decode the Core Data backup; reconstruct balances |
| rates | `rates.py` + `sources/` | build a dense daily ccy→EGP series from transaction anchors + external feeds |
| revalue | `revalue.py` | `daily_valuation` + `pnl_attribution` (the truth engine) |
| agent | `agent.py` | Claude writes a plain-language read of the numbers |
| dashboard | `dashboard/app.py` | private interactive Streamlit app |

Design choices live in [`specs/`](specs/); persistent context for contributors (human or AI)
is in [`CLAUDE.md`](CLAUDE.md).

## Quickstart

```bash
uv sync                                   # install
uv run pytest                             # run the test suite
uv run python -m networth.pipeline        # run the pipeline against a local backup
uv run --extra dashboard streamlit run dashboard/app.py   # view the dashboard
```

By default everything runs locally with `LocalStorage` and needs no credentials — point it at a
backup with `NETWORTH_BACKUP_DIR`. Production runs on GitHub Actions with `NETWORTH_STORAGE=s3`.

New here? **[SETUP.md](SETUP.md)** walks through install, a no-data demo, configuration, and
deployment step by step.

## Status

v1 in progress. Tracks EGP (base), USD, AED, SAR, and gold (XAU). Egyptian-stock per-holding
pricing is on the [roadmap](specs/roadmap.md).
