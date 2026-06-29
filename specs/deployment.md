# Deployment

Public repo = logic only. Real data + secrets live outside git.

## S3 layout (private bucket, prefix `networth/`)
```
networth/backups/<timestamp>.sqlite     # uploaded by the iOS Shortcut (latest is used)
networth/opening_adjustments.json        # one-time per-account opening offsets (see specs/data-model.md)
networth/rates.sqlite                    # accumulating rate history (written by the run)
networth/gold/daily_valuation.parquet    # gold layer for the dashboard
networth/gold/pnl_attribution.parquet
networth/insights.md
```

**Daily refresh without an upload:** the cron always runs against the *latest* backup and
fetches **live** rates, and the valuation series extends to *today* — so net worth stays current
every day whether or not you uploaded a new backup. Live rates need outbound network (present on
GitHub Actions / Streamlit Cloud); offline it falls back to the backup's stored rates.

## iOS Shortcut (daily upload)
1. Budget Flow → export backup (`.sqlite`).
2. Shortcut: "Get File" → upload to `s3://<bucket>/networth/backups/<timestamp>.sqlite`
   (S3 PUT with the access key, or via an S3-capable action). A daily Automation runs it.
3. The GitHub Action (cron) picks up the newest backup under `backups/`.

## GitHub Actions (`.github/workflows/daily.yml`)
Daily cron + `workflow_dispatch`. Secrets required:
`NETWORTH_S3_BUCKET`, `NETWORTH_S3_PREFIX`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_DEFAULT_REGION`, `ANTHROPIC_API_KEY`. Steps: checkout → setup-uv → `uv sync` →
`uv run python -m networth.pipeline` (with `NETWORTH_STORAGE=s3`).

## Streamlit Community Cloud (private dashboard)
Deploy `dashboard/app.py`; set the app to **private** and whitelist your email. Configure
secrets/env: `NETWORTH_STORAGE=s3`, bucket/prefix, and **read-only** AWS creds. It reads the
gold layer from S3 — no compute.

## Credentials hygiene
- Two IAM users: the Action gets read/write to the prefix; Streamlit gets read-only.
- Never put real numbers or keys in the repo. `.gitignore` already blocks `*.sqlite`, `data/`,
  `.env`.

## Costs
GitHub Actions (daily job) and Streamlit Community Cloud are free tiers; S3 for a few small
objects is cents/month. Claude is ~cents/day. Cloudflare R2 is a zero-egress alternative to S3
(set creds accordingly; the `S3Storage` client is S3-compatible).
