"""Filesystem storage provider."""

from __future__ import annotations

import shutil
from pathlib import Path

from doc_harvester.storage.base import StorageProvider


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, destination: str) -> Path:
        candidate = (self.root / destination.strip("/")).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"destination escapes storage root: {destination}")
        return candidate

    def exists(self, destination: str) -> bool:
        return self._path(destination).exists()

    def put_bytes(self, data: bytes, destination: str, *, overwrite: bool = True) -> None:
        target = self._path(destination)
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def put_file(self, source: str | Path, destination: str, *, overwrite: bool = True) -> None:
        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        target = self._path(destination)
        if source_path == target:
            return
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)

    def upload_tree(
        self,
        source: str | Path,
        destination: str,
        *,
        overwrite: bool = True,
    ):
        source_path = Path(source).expanduser().resolve()
        target = self._path(destination)
        if (
            source_path == target
            or source_path in target.parents
            or target in source_path.parents
        ):
            raise ValueError("local source and storage destination trees overlap")
        return super().upload_tree(source, destination, overwrite=overwrite)
