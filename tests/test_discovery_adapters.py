from __future__ import annotations

import gzip

import pytest

from doc_harvester.core import DiscoveryRequest, FetchedArtifact, Fetcher, ResourceRef
from doc_harvester.discovery import (
    ManualDiscoveryProvider,
    SitemapDiscoveryProvider,
    available_discovery_providers,
    create_discovery_provider,
)
from doc_harvester.fetchers import FetchError


class MappingFetcher(Fetcher):
    name = "mapping"

    def __init__(self, resources):
        self.resources = resources
        self.calls = []

    def fetch(self, resource):
        self.calls.append(resource.uri)
        value = self.resources.get(resource.uri)
        if value is None:
            raise FetchError("not found")
        if isinstance(value, Exception):
            raise value
        content, media_type = value if isinstance(value, tuple) else (value, "application/xml")
        return FetchedArtifact(resource, content, media_type=media_type)


def test_manual_discovery_deduplicates_defragments_guesses_type_and_limits():
    request = DiscoveryRequest(
        manual_uris=(
            "https://example.com/guide.pdf#page=2",
            "https://example.com/guide.pdf",
            "docs/readme.txt",
        ),
        limit=2,
    )

    resources = ManualDiscoveryProvider().discover(request)

    assert [item.uri for item in resources] == [
        "https://example.com/guide.pdf",
        "docs/readme.txt",
    ]
    assert [item.media_type for item in resources] == ["application/pdf", "text/plain"]
    assert all(item.source == "manual" for item in resources)


def test_manual_discovery_uses_portable_markdown_media_type():
    resources = ManualDiscoveryProvider().discover(
        DiscoveryRequest(manual_uris=("README.md", "guide.markdown"))
    )

    assert [item.media_type for item in resources] == ["text/markdown", "text/markdown"]


def test_manual_discovery_validates_input_and_credentials():
    provider = ManualDiscoveryProvider()
    with pytest.raises(ValueError, match="manual_uris"):
        provider.discover(DiscoveryRequest(root_uri="https://example.com"))
    with pytest.raises(ValueError, match="unsupported"):
        provider.discover(DiscoveryRequest(manual_uris=("s3://bucket/key",)))
    with pytest.raises(ValueError, match="embedded credentials"):
        provider.discover(
            DiscoveryRequest(manual_uris=("https://user:password@example.com/file",))
        )


def test_sitemap_discovery_reads_robots_indexes_and_same_origin_pages():
    origin = "https://example.com"
    resources = {
        f"{origin}/robots.txt": b"User-agent: *\nSitemap: /custom-index.xml\n",
        f"{origin}/custom-index.xml": b"""
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap><loc>https://example.com/products.xml</loc></sitemap>
              <sitemap><loc>https://other.example/private.xml</loc></sitemap>
            </sitemapindex>
        """,
        f"{origin}/products.xml": b"""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://example.com/a.pdf</loc></url>
              <url><loc>/b.html</loc></url>
              <url><loc>https://example.com/a.pdf</loc></url>
              <url><loc>https://other.example/outside</loc></url>
              <url><loc>javascript:alert(1)</loc></url>
              <url><loc>https://example.com:bad-port/nope</loc></url>
            </urlset>
        """,
    }
    fetcher = MappingFetcher(resources)
    provider = SitemapDiscoveryProvider(fetcher=fetcher, max_sitemaps=10)

    discovered = provider.discover(DiscoveryRequest(root_uri=f"{origin}/docs", limit=10))

    assert [item.uri for item in discovered] == [
        f"{origin}/a.pdf",
        f"{origin}/b.html",
    ]
    assert [item.media_type for item in discovered] == ["application/pdf", "text/html"]
    assert all(item.source == "sitemap" for item in discovered)
    assert "https://other.example/private.xml" not in fetcher.calls


def test_sitemap_discovery_supports_bounded_gzip_and_request_limit():
    root = "https://example.com/sitemap.xml.gz"
    xml = b"""
        <urlset>
          <url><loc>https://example.com/first</loc></url>
          <url><loc>https://example.com/second</loc></url>
        </urlset>
    """
    fetcher = MappingFetcher({root: (gzip.compress(xml), "application/gzip")})
    provider = SitemapDiscoveryProvider(fetcher=fetcher, include_robots=False)

    discovered = provider.discover(DiscoveryRequest(root_uri=root, limit=1))

    assert [item.uri for item in discovered] == ["https://example.com/first"]


@pytest.mark.parametrize(
    "content",
    [
        b"not gzip",
        gzip.compress(b"x" * 101),
    ],
)
def test_sitemap_discovery_skips_corrupt_or_oversized_gzip(content):
    root = "https://example.com/sitemap.xml.gz"
    provider = SitemapDiscoveryProvider(
        fetcher=MappingFetcher({root: (content, "application/gzip")}),
        include_robots=False,
        max_xml_bytes=100,
    )

    assert provider.discover(DiscoveryRequest(root_uri=root)) == []


def test_sitemap_discovery_rejects_entity_declarations():
    root = "https://example.com/sitemap.xml"
    malicious = b"""<!DOCTYPE urlset [<!ENTITY x "https://example.com/unsafe">]>
        <urlset><url><loc>&x;</loc></url></urlset>"""
    provider = SitemapDiscoveryProvider(
        fetcher=MappingFetcher({root: malicious}), include_robots=False
    )

    assert provider.discover(DiscoveryRequest(root_uri=root)) == []


def test_sitemap_discovery_validates_root_and_configuration():
    with pytest.raises(ValueError, match="absolute HTTP"):
        SitemapDiscoveryProvider().discover(DiscoveryRequest(root_uri="docs/sitemap.xml"))
    with pytest.raises(ValueError, match="embedded credentials"):
        SitemapDiscoveryProvider().discover(
            DiscoveryRequest(root_uri="https://user:password@example.com/sitemap.xml")
        )
    with pytest.raises(ValueError, match="at least 1"):
        SitemapDiscoveryProvider(max_sitemaps=0)


def test_discovery_factory_lists_and_builds_builtin_adapters():
    assert available_discovery_providers() == ("manual", "sitemap")
    assert isinstance(create_discovery_provider("MANUAL"), ManualDiscoveryProvider)
    assert isinstance(
        create_discovery_provider("sitemap", fetcher=MappingFetcher({})),
        SitemapDiscoveryProvider,
    )
    with pytest.raises(ValueError, match="unknown discovery provider"):
        create_discovery_provider("search-engine")
