"""Storage abstraction (Strategy): the pipeline never knows if data is local or in S3.

`LocalStorage` is the default and needs no credentials — ideal for development and CI.
`S3Storage` is the production backend used by the GitHub Actions run.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from . import config


class Storage(ABC):
    """Read the latest backup; read/write derived artifacts by key."""

    @abstractmethod
    def latest_backup(self) -> Path:
        """Return a local path to the most recent Budget Flow backup."""

    @abstractmethod
    def get(self, key: str) -> Path | None:
        """Return a local path for a stored artifact, or None if absent."""

    @abstractmethod
    def put(self, key: str, local_path: Path) -> None:
        """Persist a local file under `key`."""

    @abstractmethod
    def out_path(self, key: str) -> Path:
        """A local path safe to write to for `key` (parent dirs created)."""


def _newest_backup(folder: Path) -> Path:
    backups = [
        p
        for p in folder.glob("*.sqlite")
        if p.name not in {"rates.sqlite"} and "fixture" not in str(p)
    ]
    if not backups:
        raise FileNotFoundError(f"No *.sqlite backup found in {folder.resolve()}")
    return max(backups, key=lambda p: p.stat().st_mtime)


class LocalStorage(Storage):
    def __init__(self, data_dir: Path | None = None, backup_dir: Path | None = None):
        self.data_dir = Path(data_dir or config.DATA_DIR)
        self.backup_dir = Path(backup_dir or config.BACKUP_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def latest_backup(self) -> Path:
        return _newest_backup(self.backup_dir)

    def out_path(self, key: str) -> Path:
        p = self.data_dir / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def get(self, key: str) -> Path | None:
        p = self.data_dir / key
        return p if p.exists() else None

    def put(self, key: str, local_path: Path) -> None:
        dest = self.out_path(key)
        if Path(local_path) != dest:
            shutil.copyfile(local_path, dest)


class S3Storage(Storage):
    """Mirrors objects to a local working dir under DATA_DIR, syncing with S3.

    Layout in the bucket: ``{prefix}/backups/*.sqlite`` and ``{prefix}/{key}``.
    """

    def __init__(self, bucket: str | None = None, prefix: str | None = None):
        import boto3  # lazy: only needed in production

        self.bucket = bucket or config.S3_BUCKET
        self.prefix = (prefix or config.S3_PREFIX).strip("/")
        self.data_dir = Path(config.DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._s3 = boto3.client("s3")

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}"

    def latest_backup(self) -> Path:
        resp = self._s3.list_objects_v2(Bucket=self.bucket, Prefix=f"{self.prefix}/backups/")
        objs = [o for o in resp.get("Contents", []) if o["Key"].endswith(".sqlite")]
        if not objs:
            raise FileNotFoundError("No backup under s3://%s/%s/backups/" % (self.bucket, self.prefix))
        newest = max(objs, key=lambda o: o["LastModified"])
        dest = self.data_dir / "backup.sqlite"
        self._s3.download_file(self.bucket, newest["Key"], str(dest))
        return dest

    def out_path(self, key: str) -> Path:
        p = self.data_dir / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def get(self, key: str) -> Path | None:
        dest = self.out_path(key)
        try:
            self._s3.download_file(self.bucket, self._key(key), str(dest))
            return dest
        except Exception:
            return None

    def put(self, key: str, local_path: Path) -> None:
        self._s3.upload_file(str(local_path), self.bucket, self._key(key))


def get_storage() -> Storage:
    """Factory honoring NETWORTH_STORAGE."""
    if config.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage()
