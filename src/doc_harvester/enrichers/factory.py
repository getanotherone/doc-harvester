"""Built-in metadata-enricher selection."""

from __future__ import annotations

from doc_harvester.core import MetadataEnricher
from doc_harvester.enrichers.basic import BasicMetadataEnricher


def available_enrichers() -> tuple[str, ...]:
    return ("basic",)


def create_enricher(name: str = "basic") -> MetadataEnricher:
    normalized = name.strip().lower()
    if normalized in {"basic", "default"}:
        return BasicMetadataEnricher()
    raise ValueError(
        f"unknown metadata enricher '{name}'; available enrichers: "
        f"{', '.join(available_enrichers())}"
    )
