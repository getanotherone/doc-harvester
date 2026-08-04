"""Built-in chunker selection."""

from __future__ import annotations

from doc_harvester.core import Chunker
from doc_harvester.chunkers.structure import StructureAwareChunker


def available_chunkers() -> tuple[str, ...]:
    return ("structure-aware",)


def create_chunker(name: str) -> Chunker:
    normalized = name.strip().lower()
    if normalized in {"default", "structure-aware"}:
        return StructureAwareChunker()
    raise ValueError(
        f"unknown chunker '{name}'; available chunkers: {', '.join(available_chunkers())}"
    )

