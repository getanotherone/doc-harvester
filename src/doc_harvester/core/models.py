"""Provider-neutral data contracts for the ingestion pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


Metadata = Mapping[str, Any]


@dataclass(frozen=True)
class DiscoveryRequest:
    """Inputs accepted by search, sitemap, and manual discovery providers."""

    query: str = ""
    root_uri: str = ""
    manual_uris: tuple[str, ...] = ()
    limit: int = 100
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (self.query.strip() or self.root_uri.strip() or self.manual_uris):
            raise ValueError("discovery request requires a query, root_uri, or manual_uris")
        if self.limit < 1:
            raise ValueError("discovery limit must be at least 1")


@dataclass(frozen=True)
class ResourceRef:
    """A provider-neutral reference to a discoverable or fetchable resource."""

    uri: str
    source: str = ""
    media_type: str = ""
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise ValueError("resource uri cannot be empty")


@dataclass(frozen=True)
class CrawlPolicy:
    """Traversal, filtering, rate-limit, and robots controls for a crawler."""

    max_pages: int = 100
    delay_seconds: float = 1.0
    respect_robots_txt: bool = True
    allowed_domains: tuple[str, ...] = ()
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_pages < 1:
            raise ValueError("crawl max_pages must be at least 1")
        if self.delay_seconds < 0:
            raise ValueError("crawl delay_seconds cannot be negative")


@dataclass(frozen=True)
class FetchedArtifact:
    """Raw bytes returned by HTTP, local-file, or object-storage fetchers."""

    resource: ResourceRef
    content: bytes
    media_type: str = ""
    filename: str = ""
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class ContentBlock:
    """One structure-preserving unit produced by an extractor."""

    text: str
    kind: str = "text"
    page: int | None = None
    section: str = ""
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedDocument:
    """Normalized extraction output independent of the source file format."""

    resource: ResourceRef
    blocks: tuple[ContentBlock, ...]
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A retrieval-oriented text chunk."""

    text: str
    index: int
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("chunk index cannot be negative")


@dataclass(frozen=True)
class ChunkingOptions:
    """Portable chunking controls passed to a selected strategy."""

    strategy: str = "default"
    max_tokens: int = 800
    overlap_tokens: int = 80
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")


@dataclass(frozen=True)
class EnrichmentResult:
    """Document and chunks after classification and metadata enrichment."""

    document: ExtractedDocument
    chunks: tuple[Chunk, ...]


@dataclass(frozen=True)
class QualityFinding:
    """One extraction or chunk-quality observation."""

    code: str
    severity: str
    message: str
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class QualityReport:
    """Quality-gate decision plus provider-neutral findings and metrics."""

    passed: bool
    findings: tuple[QualityFinding, ...] = ()
    metrics: Metadata = field(default_factory=dict)


@dataclass(frozen=True)
class StorageResult:
    provider: str
    destination: str
    files_uploaded: int
    bytes_uploaded: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


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
