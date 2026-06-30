"""Central configuration: currencies, Core Data constants, and environment wiring.

Everything tunable lives here so the rest of the code reads like plain domain logic.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Domain: currencies -----------------------------------------------------
BASE_CURRENCY = "EGP"
# Non-base fiat whose moves are "unrealized FX" gains/losses.
FIAT_FX = ["USD", "AED", "SAR"]
# Non-fiat assets priced like a currency; their moves are "unrealized gold".
ASSETS = ["XAU"]
NON_BASE = FIAT_FX + ASSETS
CURRENCIES = [BASE_CURRENCY, *NON_BASE]

# --- Budget Flow backup (Apple Core Data SQLite) ----------------------------
# Core Data stores timestamps as seconds since 2001-01-01 UTC.
CORE_DATA_EPOCH = 978307200
# Entity discriminators in the single wide ZITEM table (see specs/data-model.md).
ENT_ACCOUNT = 10
ENT_GROUP = 19  # TransactionGroup: carries the money (amount/account/rate)
ENT_TXN = 18  # Transaction: one dated occurrence of a group (recurring -> many); the ledger row

# --- Environment ------------------------------------------------------------
# Where finished outputs (gold layer, rates.sqlite, insights) are kept locally.
DATA_DIR = Path(os.environ.get("NETWORTH_DATA_DIR", "data")).expanduser()
# Where to look for the latest backup when using local storage.
BACKUP_DIR = Path(os.environ.get("NETWORTH_BACKUP_DIR", ".")).expanduser()

# Storage backend: "local" or "s3".
STORAGE_BACKEND = os.environ.get("NETWORTH_STORAGE", "local")
S3_BUCKET = os.environ.get("NETWORTH_S3_BUCKET", "")
S3_PREFIX = os.environ.get("NETWORTH_S3_PREFIX", "networth")

# Claude insights agent. Sonnet keeps a daily run at ~cents; override as desired.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("NETWORTH_CLAUDE_MODEL", "claude-sonnet-4-6")
