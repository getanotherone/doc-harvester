import ast
from pathlib import Path
import subprocess
import sys

import pytest

import doc_harvester.core as core
from doc_harvester.publishers import LocalPublisher
from doc_harvester.publishers.base import Publisher as LegacyPublisher
from doc_harvester.storage import LocalStorage, StorageProvider


class ManualDiscovery(core.DiscoveryProvider):
    name = "manual"

    def discover(self, request):
        return [core.ResourceRef(uri, source=self.name) for uri in request.manual_uris]


class BoundedCrawler(core.Crawler):
    name = "bounded"

    def crawl(self, seeds, policy):
        return list(seeds[: policy.max_pages])


class MemoryFetcher(core.Fetcher):
    name = "memory"

    def fetch(self, resource):
        return core.FetchedArtifact(resource, b"alpha\nbeta", media_type="text/plain")


class TextExtractor(core.Extractor):
    name = "text"

    def supports(self, artifact):
        return artifact.media_type == "text/plain"

    def extract(self, artifact):
        blocks = tuple(core.ContentBlock(line) for line in artifact.content.decode().splitlines())
        return core.ExtractedDocument(artifact.resource, blocks)


class LineChunker(core.Chunker):
    name = "lines"

    def chunk(self, document, options):
        assert options.strategy == self.name
        return [core.Chunk(block.text, index) for index, block in enumerate(document.blocks)]


class StaticEnricher(core.MetadataEnricher):
    name = "static"

    def enrich(self, document, chunks):
        enriched = tuple(
            core.Chunk(chunk.text, chunk.index, {**chunk.metadata, "class": "example"})
            for chunk in chunks
        )
        return core.EnrichmentResult(document, enriched)


class NonEmptyQualityGate(core.QualityGate):
    name = "non-empty"

    def evaluate(self, document, chunks):
        passed = bool(document.blocks and chunks and all(chunk.text for chunk in chunks))
        return core.QualityReport(passed, metrics={"chunks": len(chunks)})


def test_universal_contracts_compose_without_provider_dependencies():
    request = core.DiscoveryRequest(manual_uris=("memory://example.txt",))
    resources = ManualDiscovery().discover(request)
    crawled = BoundedCrawler().crawl(resources, core.CrawlPolicy(max_pages=1))
    artifact = MemoryFetcher().fetch(crawled[0])
    extractor = TextExtractor()

    assert extractor.supports(artifact)
    document = extractor.extract(artifact)
    chunks = LineChunker().chunk(document, core.ChunkingOptions(strategy="lines"))
    enriched = StaticEnricher().enrich(document, chunks)
    report = NonEmptyQualityGate().evaluate(enriched.document, enriched.chunks)

    assert [chunk.text for chunk in enriched.chunks] == ["alpha", "beta"]
    assert enriched.chunks[0].metadata["class"] == "example"
    assert report.passed is True
    assert report.metrics["chunks"] == 2


def test_core_validates_portable_policy_boundaries():
    with pytest.raises(ValueError, match="requires"):
        core.DiscoveryRequest()
    with pytest.raises(ValueError, match="at least 1"):
        core.CrawlPolicy(max_pages=0)
    with pytest.raises(ValueError, match="cannot be negative"):
        core.CrawlPolicy(delay_seconds=-0.1)
    with pytest.raises(ValueError, match="cannot be negative"):
        core.CrawlPolicy(max_depth=-1)
    with pytest.raises(ValueError, match="smaller"):
        core.ChunkingOptions(max_tokens=100, overlap_tokens=100)
    with pytest.raises(ValueError, match="negative"):
        core.Chunk("invalid", -1)


def test_existing_storage_and_publisher_adapters_use_core_contracts(tmp_path):
    storage = LocalStorage(tmp_path / "storage")
    publisher = LocalPublisher(tmp_path / "published")

    assert issubclass(StorageProvider, core.StorageBackend)
    assert isinstance(storage, core.StorageBackend)
    assert isinstance(publisher, core.Publisher)
    assert LegacyPublisher is core.Publisher


def test_core_package_has_no_provider_specific_imports():
    package_dir = Path(core.__file__).parent
    imported_modules: set[str] = set()

    for source_path in package_dir.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    assert not any("yandex" in module.lower() for module in imported_modules)
    assert not any("confluence" in module.lower() for module in imported_modules)
    assert not any("notion" in module.lower() for module in imported_modules)

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import doc_harvester.core; "
                "blocked=('yandex', 'notion', 'confluence', 'boto3'); "
                "assert not any(any(word in name.lower() for word in blocked) "
                "for name in sys.modules)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
