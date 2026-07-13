"""Publisher contract for documentation and generated artifacts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublishRequest:
    source: Path
    destination: str
    title: str = ""


@dataclass(frozen=True)
class PublishResult:
    provider: str
    destination: str
    status: str
    external_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Publisher(ABC):
    name: str

    @abstractmethod
    def publish(
        self,
        request: PublishRequest,
        *,
        dry_run: bool = True,
        create_missing: bool = False,
    ) -> PublishResult:
        raise NotImplementedError
