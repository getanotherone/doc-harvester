"""Yandex Disk adapter for the storage contract."""

from __future__ import annotations

import os
from pathlib import Path

from doc_harvester.storage.base import StorageProvider, StorageResult


class YandexDiskStorage(StorageProvider):
    name = "yandex"

    def __init__(self, token: str | None = None) -> None:
        self.token = (token or os.environ.get("YANDEX_DISK_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("YANDEX_DISK_TOKEN is required for the Yandex storage provider")

    def _client(self):
        import yandex

        yandex.configure_token(self.token)
        return yandex

    def exists(self, destination: str) -> bool:
        return self._client().path_exists(destination)

    def put_bytes(self, data: bytes, destination: str, *, overwrite: bool = True) -> None:
        self._client().upload_bytes(data, destination, overwrite=overwrite)

    def put_file(self, source: str | Path, destination: str, *, overwrite: bool = True) -> None:
        self._client().upload_file(str(source), destination, overwrite=overwrite)

    def upload_tree(
        self,
        source: str | Path,
        destination: str,
        *,
        overwrite: bool = True,
    ) -> StorageResult:
        source_path = Path(source)
        if not source_path.is_dir():
            raise FileNotFoundError(f"source directory not found: {source_path}")
        total_bytes = sum(
            path.stat().st_size
            for path in source_path.rglob("*")
            if path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(source_path).parts)
        )
        count = self._client().upload_directory(
            str(source_path), destination, overwrite=overwrite, skip_hidden=True
        )
        return StorageResult(self.name, destination, count, total_bytes)
