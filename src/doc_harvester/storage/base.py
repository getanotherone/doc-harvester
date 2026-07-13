"""Storage provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageResult:
    provider: str
    destination: str
    files_uploaded: int
    bytes_uploaded: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class StorageProvider(ABC):
    """Minimal contract implemented by local and remote object stores."""

    name: str

    @abstractmethod
    def exists(self, destination: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def put_bytes(self, data: bytes, destination: str, *, overwrite: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def put_file(self, source: str | Path, destination: str, *, overwrite: bool = True) -> None:
        raise NotImplementedError

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
        count = 0
        total_bytes = 0
        for path in sorted(source_path.rglob("*")):
            if not path.is_file() or any(part.startswith(".") for part in path.relative_to(source_path).parts):
                continue
            relative = path.relative_to(source_path).as_posix()
            target = "/".join(part for part in (destination.strip("/"), relative) if part)
            self.put_file(path, target, overwrite=overwrite)
            count += 1
            total_bytes += path.stat().st_size
        return StorageResult(self.name, destination, count, total_bytes)
