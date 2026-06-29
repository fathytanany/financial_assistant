"""Bronze layer: obtain the latest Budget Flow backup (the read-only source of truth)."""

from __future__ import annotations

from pathlib import Path

from .storage import Storage


def ingest(storage: Storage) -> Path:
    """Return a local path to the newest backup; we never modify it."""
    return storage.latest_backup()
