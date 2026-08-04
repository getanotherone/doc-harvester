"""Stable provider-neutral interfaces for discovery through publication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from doc_harvester.core.models import (
    Chunk,
    ChunkingOptions,
    CrawlPolicy,
    DiscoveryRequest,
    EnrichmentResult,
    ExtractedDocument,
    FetchedArtifact,
    PublishRequest,
    PublishResult,
    QualityReport,
    ResourceRef,
    StorageResult,
)


class DiscoveryProvider(ABC):
    """Discover resource references through search, sitemap, or manual inputs."""

    name: str

    @abstractmethod
    def discover(self, request: DiscoveryRequest) -> Sequence[ResourceRef]:
        raise NotImplementedError


class Crawler(ABC):
    """Traverse and filter resources under an explicit crawl policy."""

    name: str

    @abstractmethod
    def crawl(
        self,
        seeds: Sequence[ResourceRef],
        policy: CrawlPolicy,
    ) -> Sequence[ResourceRef]:
        raise NotImplementedError


class Fetcher(ABC):
    """Fetch raw bytes from HTTP, local files, or object storage."""

    name: str

    @abstractmethod
    def fetch(self, resource: ResourceRef) -> FetchedArtifact:
        raise NotImplementedError


class Extractor(ABC):
    """Convert a supported fetched artifact into normalized content blocks."""

    name: str

    @abstractmethod
    def supports(self, artifact: FetchedArtifact) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract(self, artifact: FetchedArtifact) -> ExtractedDocument:
        raise NotImplementedError


class Chunker(ABC):
    """Apply one selectable chunking strategy to an extracted document."""

    name: str

    @abstractmethod
    def chunk(
        self,
        document: ExtractedDocument,
        options: ChunkingOptions,
    ) -> Sequence[Chunk]:
        raise NotImplementedError


class MetadataEnricher(ABC):
    """Classify a document and enrich document/chunk metadata."""

    name: str

    @abstractmethod
    def enrich(
        self,
        document: ExtractedDocument,
        chunks: Sequence[Chunk],
    ) -> EnrichmentResult:
        raise NotImplementedError


class QualityGate(ABC):
    """Evaluate extraction and chunk quality without storing or publishing data."""

    name: str

    @abstractmethod
    def evaluate(
        self,
        document: ExtractedDocument,
        chunks: Sequence[Chunk],
    ) -> QualityReport:
        raise NotImplementedError


class StorageBackend(ABC):
    """Store original files and processed artifacts behind one backend contract."""

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
            relative_parts = path.relative_to(source_path).parts
            if not path.is_file() or any(part.startswith(".") for part in relative_parts):
                continue
            relative = path.relative_to(source_path).as_posix()
            target = "/".join(part for part in (destination.strip("/"), relative) if part)
            self.put_file(path, target, overwrite=overwrite)
            count += 1
            total_bytes += path.stat().st_size
        return StorageResult(self.name, destination, count, total_bytes)


class Publisher(ABC):
    """Publish processed artifacts to documentation or delivery destinations."""

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
