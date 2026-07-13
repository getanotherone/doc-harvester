"""Chunker protocol — interface for all chunking strategies."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from doc_proc.models import ChunkResult, ParseResult


@runtime_checkable
class Chunker(Protocol):
    """Protocol for document chunking strategies.

    Each strategy receives a ParseResult and returns a ChunkResult
    with typed chunks ready for embedding.
    """

    @property
    def name(self) -> str:
        """Strategy name for logging and comparison."""
        ...

    def chunk(self, parse_result: ParseResult, **config) -> ChunkResult:
        """Split parsed elements into chunks."""
        ...
