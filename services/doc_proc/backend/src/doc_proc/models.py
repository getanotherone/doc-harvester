"""Typed dataclasses for pipeline inter-stage data transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ParsedElement:
    """Single element extracted by a parser."""

    index: int
    text: str
    element_type: Literal["data", "section_header", "table_row", "text", "heading", "image"]
    attributes: dict[str, Any] = field(default_factory=dict)
    section: str = ""
    page: int | None = None
    confidence: float = 1.0
    row_type: str = "data"  # compat: data, section_header, subtotal, column_number


@dataclass
class ExtractedImage:
    """Image extracted from a document."""

    index: int
    image_data: bytes
    mime_type: str = "image/png"
    page: int | None = None
    section: str = ""
    caption: str = ""


@dataclass
class ParseResult:
    """Output of the Parse stage."""

    elements: list[ParsedElement]
    images: list[ExtractedImage] = field(default_factory=list)
    format_hint: Literal["tabular", "document", "mixed"] = "document"
    document_type: str = "unknown"
    page_count: int = 0
    tables_count: int = 0
    has_ocr: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawChunk:
    """Single chunk produced by the Chunk stage (before embedding)."""

    text: str
    chunk_type: str = "text"  # text, table, heading, list, image, normative
    section: str = ""
    page: int | None = None
    context_header: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    # Domain metadata (electrical engineering)
    vendor: str = ""
    standard_id: str = ""
    doc_type: str = ""
    lang: str = ""
    source_type: str = ""
    year: int | None = None
    block_types: list[str] = field(default_factory=lambda: ["normal"])


@dataclass
class ChunkResult:
    """Output of the Chunk stage."""

    chunks: list[RawChunk]
    strategy_used: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedChunk:
    """Chunk with embedding vector attached."""

    chunk: RawChunk
    embedding: list[float] = field(default_factory=list)


@dataclass
class EmbedResult:
    """Output of the Embed stage."""

    chunks: list[EmbeddedChunk]
    model: str = ""
    dimension: int = 0


@dataclass
class QualityMetric:
    """Quality metric for a single chunk."""

    chunk_index: int
    text_density: float = 0.0
    token_count: int = 0
    text_length: int = 0
    embedding_norm: float | None = None


@dataclass
class QualityReport:
    """Output of the Evaluate stage."""

    total_chunks: int = 0
    total_tokens: int = 0
    avg_tokens: float = 0.0
    min_tokens: int = 0
    max_tokens: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_section: dict[str, int] = field(default_factory=dict)
    metrics: list[QualityMetric] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Output of comparing multiple strategies on the same document."""

    document_id: str = ""
    strategies: dict[str, QualityReport] = field(default_factory=dict)
    sample_chunks: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


CHARS_PER_TOKEN = 4  # Fallback ratio for char-based splitting heuristics

try:
    import tiktoken as _tiktoken

    _encoder = _tiktoken.get_encoding("cl100k_base")

    from functools import lru_cache as _lru_cache

    @_lru_cache(maxsize=50_000)
    def _count_tokens_cached(text: str) -> int:
        return len(_encoder.encode(text))

    def count_tokens(text: str) -> int:
        """Exact token count via tiktoken cl100k_base (cached)."""
        return _count_tokens_cached(text or "")

except ImportError:
    def count_tokens(text: str) -> int:
        """Fallback: approximate token count when tiktoken is not installed."""
        return max(1, len((text or "").strip()) // CHARS_PER_TOKEN)


def estimate_tokens(text: str) -> int:
    """Count tokens — uses tiktoken when available, char estimate otherwise."""
    return max(1, count_tokens(text))
