"""Local Markdown publisher."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from doc_harvester.publishers.base import Publisher, PublishRequest, PublishResult


class LocalPublisher(Publisher):
    name = "local"

    def __init__(self, root: str | Path) -> None:
        configured = Path(root).expanduser()
        if configured.is_symlink():
            raise ValueError(f"publisher root is a symbolic link: {configured}")
        self.root = configured.resolve()

    def _path(self, destination: str) -> Path:
        relative = destination.strip("/")
        if not relative:
            raise ValueError("publisher destination cannot be empty")
        if not Path(relative).suffix:
            relative = f"{relative}.md"
        candidate = self.root / relative
        for path in (candidate, *candidate.parents):
            if path == self.root:
                break
            if path.is_symlink():
                raise ValueError(f"publisher destination contains a symbolic link: {destination}")
        target = candidate.resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"destination escapes publisher root: {destination}")
        return target

    def publish(
        self,
        request: PublishRequest,
        *,
        dry_run: bool = True,
        create_missing: bool = False,
    ) -> PublishResult:
        del create_missing
        if request.source.is_symlink() or not request.source.is_file():
            raise FileNotFoundError(request.source)
        target = self._path(request.destination)
        if request.source.resolve() == target:
            raise ValueError("publisher source and destination must differ")
        status = "would_update" if target.exists() else "would_create"
        if dry_run:
            return PublishResult(self.name, request.destination, status)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(request.source, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return PublishResult(self.name, request.destination, "published", metadata={"path": str(target)})
