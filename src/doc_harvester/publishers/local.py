"""Local Markdown publisher."""

from __future__ import annotations

import shutil
from pathlib import Path

from doc_harvester.publishers.base import Publisher, PublishRequest, PublishResult


class LocalPublisher(Publisher):
    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _path(self, destination: str) -> Path:
        relative = destination.strip("/")
        if not Path(relative).suffix:
            relative = f"{relative}.md"
        target = (self.root / relative).resolve()
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
        if not request.source.is_file():
            raise FileNotFoundError(request.source)
        target = self._path(request.destination)
        status = "would_update" if target.exists() else "would_create"
        if dry_run:
            return PublishResult(self.name, request.destination, status)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(request.source, target)
        return PublishResult(self.name, request.destination, "published", metadata={"path": str(target)})
