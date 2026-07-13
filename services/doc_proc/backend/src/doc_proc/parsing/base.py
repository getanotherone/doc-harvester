"""Parser protocol — interface for all format-specific parsers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from doc_proc.models import ParseResult


@runtime_checkable
class Parser(Protocol):
    """Protocol for document parsers.

    Each parser handles one or more file formats and returns a ParseResult
    with typed elements and an explicit format_hint.
    """

    def can_handle(self, filename: str, content: bytes | None = None) -> bool:
        """Check if this parser can handle the given file."""
        ...

    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse document content and return structured elements."""
        ...

    def parse_from_path(self, path: str, filename: str) -> ParseResult:
        """Parse from file path (avoids loading large files into memory)."""
        ...
