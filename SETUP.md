# Setup & getting started

Everything you need to run this locally and to deploy the daily cloud pipeline. For design
details see [`CLAUDE.md`](CLAUDE.md) and [`specs/`](specs/).

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (manages Python; the repo pins 3.12 via `.python-version`).
- A **Budget Flow** SQLite backup (only for real data — a synthetic fixture works without one).
- *For production only:* an S3 bucket (or Cloudflare R2) and an Anthropic API key.

## 1. Install
```bash
git clone <your-repo-url> && cd financial_assistant
uv sync
```

## 2. Run the tests
```bash
uv run pytest          # 8 tests: schema decode, rate anchors, valuation, attribution identity
```

## 3. Try it locally — no cloud, no secrets

**With the synthetic fixture (no real data needed):**
```bash
uv run python tests/make_fixture.py
cp tests/fixtures/sample.sqlite /tmp/demo.sqlite
NETWORTH_BACKUP_DIR=/tmp uv run python -m networth.pipeline
uv run --extra dashboard streamlit run dashboard/app.py   # http://localhost:8501
```

**With your real backup** — point `NETWORTH_BACKUP_DIR` at the *folder* holding the `.sqlite`
(the newest one is used):
```bash
NETWORTH_BACKUP_DIR=/path/to/backups uv run python -m networth.pipeline
uv run --extra dashboard streamlit run dashboard/app.py
```
Outputs land in `data/` (git-ignored). Set `ANTHROPIC_API_KEY` first if you want the written
Claude insights instead of the offline fallback.

## 4. Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NETWORTH_STORAGE` | `local` | `local` or `s3` |
| `NETWORTH_BACKUP_DIR` | `.` | folder scanned for the newest backup (local mode) |
| `NETWORTH_DATA_DIR` | `data` | where outputs are written/read |
| `NETWORTH_S3_BUCKET` / `NETWORTH_S3_PREFIX` | — / `networth` | S3 location (s3 mode) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` | — | AWS creds |
| `ANTHROPIC_API_KEY` | — | enables the Claude insights step |
| `NETWORTH_CLAUDE_MODEL` | `claude-sonnet-4-6` | insights model |

## 5. Deploy (production)

Full details in [`specs/deployment.md`](specs/deployment.md). In short:

1. **S3** — create a private bucket. The Shortcut uploads to
   `s3://<bucket>/<prefix>/backups/`; the pipeline writes the gold layer + `insights.md` back.
2. **iOS Shortcut** — Budget Flow → export backup → upload to that `backups/` path daily.
3. **GitHub Actions** — add repo secrets: `NETWORTH_S3_BUCKET`, `NETWORTH_S3_PREFIX`,
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `ANTHROPIC_API_KEY`.
   The [`daily`](.github/workflows/daily.yml) workflow runs the pipeline on a cron.
4. **Streamlit Community Cloud** — deploy `dashboard/app.py`, set the app **private** with an
   email whitelist, and configure env with `NETWORTH_STORAGE=s3` + **read-only** AWS creds.

## 6. Push to GitHub

The repo is committed and ready. Create the remote and push:
```bash
# with the GitHub CLI
gh repo create networth --public --source=. --remote=origin --push

# or manually
git remote add origin git@github.com:<you>/networth.git
git push -u origin main
```

## Safety check
Real data and secrets are never committed (see [`.gitignore`](.gitignore)). Confirm before any
push:
```bash
git status            # nothing under data/, no *.sqlite except tests/fixtures/sample.sqlite
git ls-files | grep -E '\.(sqlite|parquet|env)$'   # should show ONLY tests/fixtures/sample.sqlite
```
