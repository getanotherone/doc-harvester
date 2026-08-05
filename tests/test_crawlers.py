from __future__ import annotations

import pytest

from doc_harvester.core import Crawler, CrawlPolicy, FetchedArtifact, ResourceRef
from doc_harvester.crawlers import HTMLCrawler, available_crawlers, create_crawler
from doc_harvester.fetchers import FetchError


class MappingFetcher:
    name = "mapping"

    def __init__(self, resources):
        self.resources = resources
        self.calls = []

    def fetch(self, resource):
        self.calls.append(resource.uri)
        value = self.resources.get(resource.uri)
        if value is None:
            raise FetchError("unavailable")
        if isinstance(value, Exception):
            raise value
        content, media_type, metadata = (
            value
            if isinstance(value, tuple) and len(value) == 3
            else (*value, {})
            if isinstance(value, tuple)
            else (value, "text/html", {})
        )
        return FetchedArtifact(
            resource, content, media_type=media_type, metadata=metadata
        )


def test_html_crawler_traverses_breadth_first_with_robots_and_safe_links():
    origin = "https://example.com"
    fetcher = MappingFetcher(
        {
            f"{origin}/robots.txt": (
                b"User-agent: *\nDisallow: /private\nCrawl-delay: 2\n",
                "text/plain",
            ),
            f"{origin}/": b"""
                <a href="/guide">Guide</a>
                <a href="/guide#section">Duplicate fragment</a>
                <a href="/private/secret">Private</a>
                <a href="/skip/page">Excluded</a>
                <a href="/manual.pdf">Manual</a>
                <a href="/photo.png">Image</a>
                <a href="https://outside.test/page">Outside</a>
                <a href="javascript:alert(1)">Unsafe</a>
            """,
            f"{origin}/guide": b"<h1>Guide</h1>",
        }
    )
    delays = []
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=delays.append)

    resources = crawler.crawl(
        [ResourceRef(f"{origin}/")],
        CrawlPolicy(max_pages=10, max_depth=2, exclude_patterns=("*/skip/*",)),
    )

    assert [resource.uri for resource in resources] == [
        f"{origin}/",
        f"{origin}/manual.pdf",
        f"{origin}/guide",
    ]
    assert [resource.metadata["depth"] for resource in resources] == [0, 1, 1]
    assert f"{origin}/manual.pdf" not in fetcher.calls
    assert f"{origin}/private/secret" not in fetcher.calls
    assert delays == [2.0, 2.0]
    assert crawler.last_report == {
        "schema_version": 1,
        "seed_count": 1,
        "fetched_pages": 2,
        "discovered_count": 3,
        "skipped_robots": 1,
        "skipped_filtered": 2,
        "skipped_unsupported": 1,
        "failed_fetches": 0,
        "blocked_redirects": 0,
        "truncated": False,
    }


def test_include_pattern_filters_output_without_blocking_traversal():
    origin = "https://example.com"
    fetcher = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": b'<a href="/bridge">Bridge</a>',
            f"{origin}/bridge": b'<a href="/target">Target</a>',
            f"{origin}/target": b"<h1>Target</h1>",
        }
    )
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=lambda _: None)

    resources = crawler.crawl(
        [ResourceRef(f"{origin}/")],
        CrawlPolicy(
            max_pages=10,
            max_depth=2,
            delay_seconds=0,
            include_patterns=("*/target",),
        ),
    )

    assert [resource.uri for resource in resources] == [f"{origin}/target"]
    assert resources[0].metadata["depth"] == 2


def test_crawler_fails_closed_when_robots_unavailable_and_can_be_explicitly_ignored():
    root = "https://example.com/"
    fetcher = MappingFetcher({root: b"<h1>Allowed only after opt-out</h1>"})
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=lambda _: None)

    assert crawler.crawl([ResourceRef(root)], CrawlPolicy()) == []
    assert crawler.last_report["skipped_robots"] == 1
    assert fetcher.calls == ["https://example.com/robots.txt"]

    resources = crawler.crawl(
        [ResourceRef(root)],
        CrawlPolicy(respect_robots_txt=False, delay_seconds=0),
    )
    assert [resource.uri for resource in resources] == [root]


def test_crawler_treats_missing_robots_file_as_allowing_crawl():
    root = "https://example.com/"
    fetcher = MappingFetcher(
        {
            "https://example.com/robots.txt": FetchError(
                "HTTP 404 while fetching https://example.com/robots.txt"
            ),
            root: b"<h1>Public page</h1>",
        }
    )
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=lambda _: None)

    resources = crawler.crawl(
        [ResourceRef(root)], CrawlPolicy(delay_seconds=0)
    )

    assert [resource.uri for resource in resources] == [root]
    assert crawler.last_report["skipped_robots"] == 0


def test_crawler_blocks_cross_origin_redirect_and_enforces_page_bound():
    origin = "https://example.com"
    fetcher = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": (
                b"<h1>Redirected</h1>",
                "text/html",
                {"final_uri": "https://outside.test/private?token=secret"},
            ),
        }
    )
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=lambda _: None)

    assert crawler.crawl([ResourceRef(f"{origin}/")], CrawlPolicy()) == []
    assert crawler.last_report["blocked_redirects"] == 1
    assert "secret" not in str(crawler.last_report)


def test_crawler_limits_fetches_even_when_include_pattern_matches_nothing():
    origin = "https://example.com"
    fetcher = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": b'<a href="/a">A</a><a href="/b">B</a>',
            f"{origin}/a": b'<a href="/c">C</a>',
            f"{origin}/b": b"<h1>B</h1>",
            f"{origin}/c": b"<h1>C</h1>",
        }
    )
    crawler = HTMLCrawler(fetcher=fetcher, sleeper=lambda _: None)

    resources = crawler.crawl(
        [ResourceRef(f"{origin}/")],
        CrawlPolicy(
            max_pages=2,
            max_depth=3,
            delay_seconds=0,
            include_patterns=("*/never",),
        ),
    )

    assert resources == []
    assert crawler.last_report["fetched_pages"] == 2
    assert crawler.last_report["truncated"] is True
    assert f"{origin}/b" not in fetcher.calls


def test_crawler_records_per_page_link_truncation():
    origin = "https://example.com"
    fetcher = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": b'<a href="/a">A</a><a href="/b">B</a>',
            f"{origin}/a": b"<h1>A</h1>",
        }
    )
    crawler = HTMLCrawler(
        fetcher=fetcher, max_links_per_page=1, sleeper=lambda _: None
    )

    resources = crawler.crawl(
        [ResourceRef(f"{origin}/")], CrawlPolicy(delay_seconds=0)
    )

    assert [resource.uri for resource in resources] == [f"{origin}/", f"{origin}/a"]
    assert crawler.last_report["truncated"] is True


def test_crawler_fails_safely_on_oversized_robots_and_html():
    origin = "https://example.com"
    oversized_robots = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": b"<h1>Page</h1>",
        }
    )
    crawler = HTMLCrawler(
        fetcher=oversized_robots,
        max_robots_bytes=5,
        sleeper=lambda _: None,
    )
    assert crawler.crawl([ResourceRef(f"{origin}/")], CrawlPolicy()) == []
    assert crawler.last_report["skipped_robots"] == 1

    oversized_html = MappingFetcher(
        {
            f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n",
            f"{origin}/": b"<h1>Page</h1>",
        }
    )
    crawler = HTMLCrawler(
        fetcher=oversized_html,
        max_html_bytes=5,
        sleeper=lambda _: None,
    )
    assert crawler.crawl([ResourceRef(f"{origin}/")], CrawlPolicy()) == []
    assert crawler.last_report["failed_fetches"] == 1


def test_crawler_uses_dedicated_robots_fetcher():
    origin = "https://example.com"
    pages = MappingFetcher({f"{origin}/": b"<h1>Page</h1>"})
    robots = MappingFetcher(
        {f"{origin}/robots.txt": b"User-agent: *\nDisallow:\n"}
    )
    crawler = HTMLCrawler(
        fetcher=pages,
        robots_fetcher=robots,
        sleeper=lambda _: None,
    )

    resources = crawler.crawl([ResourceRef(f"{origin}/")], CrawlPolicy())

    assert [resource.uri for resource in resources] == [f"{origin}/"]
    assert robots.calls == [f"{origin}/robots.txt"]
    assert pages.calls == [f"{origin}/"]


@pytest.mark.parametrize(
    "seed",
    ["relative/page", "ftp://example.com/file", "https://user:pass@example.com/"],
)
def test_crawler_rejects_unsafe_seeds(seed):
    with pytest.raises(ValueError, match="absolute HTTP"):
        HTMLCrawler(fetcher=MappingFetcher({})).crawl(
            [ResourceRef(seed)], CrawlPolicy()
        )


def test_crawler_factory_and_configuration_validation():
    assert available_crawlers() == ("html",)
    assert isinstance(create_crawler("web", fetcher=MappingFetcher({})), Crawler)
    with pytest.raises(ValueError, match="unknown crawler"):
        create_crawler("browser")
    with pytest.raises(ValueError, match="at least 1"):
        HTMLCrawler(max_links_per_page=0)
    with pytest.raises(ValueError, match="hostnames"):
        HTMLCrawler(fetcher=MappingFetcher({})).crawl(
            [ResourceRef("https://example.com/")],
            CrawlPolicy(allowed_domains=("https://example.com",)),
        )
