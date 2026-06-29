# Architecture

A daily, idempotent [medallion](https://en.wikipedia.org/wiki/Medallion_architecture) pipeline.
Deterministic core does all math; a single Claude step writes insights.

```
 iPhone (Shortcut)        S3 (private)              GitHub Actions (daily cron)
  backup.sqlite  ───────►  backups/*.sqlite  ─────►  ingest → normalize → rates → revalue → agent
                           rates.sqlite      ◄─────  ───────────────────────────────────────┐
                           gold/*.parquet    ◄───────────────────────────────────────────────┘
                           insights.md       ◄───┘
                                  ▲
        Streamlit (private, email-gated)  ── reads gold layer, renders dashboard
```

## Layers
- **bronze** — `ingest.py`: fetch the latest backup; never mutate it.
- **silver** — `normalize.py`: decode `ZITEM` into `accounts` + `entries`; reconstruct balances.
  `rates.py` + `sources/`: dense daily ccy→EGP series.
- **gold** — `revalue.py`: `daily_valuation` + `pnl_attribution`.
- **insight** — `agent.py`: Claude narrates the gold layer.
- **view** — `dashboard/app.py`: Streamlit reads the gold layer.

## State
The only *accumulating* state is the rate history (`rates.sqlite`); silver/gold are rebuilt
each run from `latest backup + rate history`. Re-running is always safe.

## Patterns (only two — keep it that way)
- **Medallion** layering (above).
- **Adapter/Strategy**: `RateSource` (`sources/base.py`) for data feeds; `Storage`
  (`storage.py`) for local-vs-S3. New source or backend = a new class, no rewrites.

## Module map
`config.py` (knobs) · `storage.py` (Local/S3) · `ingest.py` · `normalize.py` · `rates.py` ·
`sources/{base,fx,gold}.py` · `revalue.py` · `agent.py` · `pipeline.py` (wires it together).
