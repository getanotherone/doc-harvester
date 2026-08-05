from __future__ import annotations

import json

import pytest

from doc_harvester.cli import build_parser, main
from doc_harvester.core import FetchedArtifact, ResourceRef
from doc_harvester.fetchers import FetchError
import doc_harvester.source_cli as source_cli


class StaticDiscoveryProvider:
    name = "sitemap"

    def __init__(self, resources):
        self.resources = resources
        self.requests = []

    def discover(self, request):
        self.requests.append(request)
        return self.resources


class StaticFetcher:
    def __init__(self, name="http", content=b"downloaded", error=None):
        self.name = name
        self.content = content
        self.error = error
        self.resources = []

    def fetch(self, resource):
        self.resources.append(resource)
        if self.error:
            raise self.error
        return FetchedArtifact(
            resource,
            self.content,
            media_type="text/plain",
            filename="source.txt",
            metadata={"status_code": 200, "bytes": len(self.content)},
        )


class StaticCrawler:
    name = "html"

    def __init__(self, resources):
        self.resources = resources
        self.calls = []
        self.last_report = {"schema_version": 1, "discovered_count": len(resources)}

    def crawl(self, seeds, policy):
        self.calls.append((seeds, policy))
        return self.resources


def test_parser_exposes_credential_free_source_commands():
    parser = build_parser()

    manual = parser.parse_args(["source", "discover", "manual", "README.md"])
    sitemap = parser.parse_args(
        ["source", "discover", "sitemap", "https://example.com/sitemap.xml"]
    )
    crawl = parser.parse_args(["source", "crawl", "https://example.com/docs"])
    fetch = parser.parse_args(
        ["source", "fetch", "README.md", "--output", "/tmp/readme.md"]
    )
    process = parser.parse_args(
        ["source", "process", "manifest.json", "--output", "/tmp/dataset"]
    )
    inspect = parser.parse_args(["source", "inspect", "/tmp/dataset"])
    store = parser.parse_args(
        [
            "source",
            "store",
            "/tmp/dataset",
            "--destination",
            "review/run-1",
        ]
    )
    render = parser.parse_args(
        [
            "source",
            "render",
            "/tmp/dataset",
            "--document-index",
            "0",
            "--output",
            "/tmp/review.md",
        ]
    )

    assert (manual.command, manual.source_command, manual.discovery_mode) == (
        "source",
        "discover",
        "manual",
    )
    assert sitemap.discovery_mode == "sitemap"
    assert crawl.source_command == "crawl"
    assert crawl.limit == 100
    assert crawl.max_depth == 3
    assert crawl.respect_robots_txt is True
    assert fetch.source_command == "fetch"
    assert process.source_command == "process"
    assert process.include_hidden_xlsx_sheets is False
    assert process.fail_on_quality is False
    assert inspect.source_command == "inspect"
    assert inspect.include_source_uri is False
    assert inspect.max_artifact_bytes == 10 * 1024 * 1024
    assert inspect.max_documents == 10_000
    assert store.source_command == "store"
    assert store.storage == "local"
    assert store.overwrite is False
    assert render.source_command == "render"
    assert render.document_index == 0
    assert render.include_source_uri is False
    assert render.overwrite is False


def test_store_parser_exposes_non_secret_s3_connection_overrides():
    store = build_parser().parse_args(
        [
            "source",
            "store",
            "/tmp/dataset",
            "--destination",
            "review/run-1",
            "--storage",
            "s3",
            "--s3-bucket",
            "test-bucket",
            "--s3-prefix",
            "doc-harvester",
            "--s3-endpoint-url",
            "https://objects.example.test",
            "--s3-region",
            "test-1",
        ]
    )

    assert store.s3_bucket == "test-bucket"
    assert store.s3_prefix == "doc-harvester"
    assert store.s3_endpoint_url == "https://objects.example.test"
    assert store.s3_region == "test-1"


def test_process_parser_can_include_hidden_xlsx_sheets():
    args = build_parser().parse_args(
        [
            "source",
            "process",
            "manifest.json",
            "--output",
            "/tmp/dataset",
            "--include-hidden-xlsx-sheets",
        ]
    )

    assert args.include_hidden_xlsx_sheets is True


def test_process_parser_hidden_xlsx_environment_default_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DOC_HARVESTER_XLSX_INCLUDE_HIDDEN", "1")

    enabled = build_parser().parse_args(
        ["source", "process", "manifest.json", "--output", "/tmp/dataset"]
    )
    disabled = build_parser().parse_args(
        [
            "source",
            "process",
            "manifest.json",
            "--output",
            "/tmp/dataset",
            "--no-include-hidden-xlsx-sheets",
        ]
    )

    assert enabled.include_hidden_xlsx_sheets is True
    assert disabled.include_hidden_xlsx_sheets is False


def test_process_parser_quality_environment_default_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DOC_HARVESTER_FAIL_ON_QUALITY", "1")

    enabled = build_parser().parse_args(
        ["source", "process", "manifest.json", "--output", "/tmp/dataset"]
    )
    disabled = build_parser().parse_args(
        [
            "source",
            "process",
            "manifest.json",
            "--output",
            "/tmp/dataset",
            "--no-fail-on-quality",
        ]
    )

    assert enabled.fail_on_quality is True
    assert disabled.fail_on_quality is False


def test_manual_discovery_emits_versioned_manifest(capsys):
    assert (
        main(
            [
                "source",
                "discover",
                "manual",
                "README.md#intro",
                "README.md",
                "docs/architecture.md",
                "--limit",
                "2",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "schema_version": 1,
        "provider": "manual",
        "count": 2,
        "resources": [
            {
                "uri": "README.md",
                "source": "manual",
                "media_type": "text/markdown",
                "metadata": {},
            },
            {
                "uri": "docs/architecture.md",
                "source": "manual",
                "media_type": "text/markdown",
                "metadata": {},
            },
        ],
    }


def test_manual_discovery_can_write_manifest_file(tmp_path, capsys):
    output = tmp_path / "nested" / "manifest.json"

    assert (
        main(
            [
                "source",
                "discover",
                "manual",
                "README.md",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert json.loads(output.read_text(encoding="utf-8"))["count"] == 1
    assert capsys.readouterr().out == ""


def test_sitemap_discovery_forwards_bounds_and_controls(monkeypatch, capsys):
    provider = StaticDiscoveryProvider(
        [ResourceRef("https://example.com/guide.pdf", source="sitemap")]
    )
    fetcher = object()
    factory_calls = []

    def fake_create_fetcher(name, **options):
        factory_calls.append(("fetcher", name, options))
        return fetcher

    def fake_create_provider(name, **options):
        factory_calls.append(("provider", name, options))
        return provider

    monkeypatch.setattr(source_cli, "create_fetcher", fake_create_fetcher)
    monkeypatch.setattr(source_cli, "create_discovery_provider", fake_create_provider)

    assert (
        main(
            [
                "source",
                "discover",
                "sitemap",
                "https://example.com/sitemap.xml",
                "--limit",
                "3",
                "--max-sitemaps",
                "4",
                "--max-xml-bytes",
                "5000",
                "--timeout",
                "2.5",
                "--no-robots",
                "--allow-cross-origin",
            ]
        )
        == 0
    )

    assert factory_calls[0] == (
        "fetcher",
        "http",
        {"timeout_seconds": 2.5, "max_bytes": 5000},
    )
    provider_options = factory_calls[1][2]
    assert provider_options == {
        "fetcher": fetcher,
        "max_sitemaps": 4,
        "max_xml_bytes": 5000,
        "include_robots": False,
        "same_origin_only": False,
    }
    assert provider.requests[0].root_uri == "https://example.com/sitemap.xml"
    assert provider.requests[0].limit == 3
    assert json.loads(capsys.readouterr().out)["count"] == 1


def test_source_crawl_forwards_policy_bounds_and_emits_manifest(monkeypatch, capsys):
    crawler = StaticCrawler(
        [ResourceRef("https://example.com/guide", source="html", metadata={"depth": 1})]
    )
    fetcher = object()
    robots_fetcher = object()
    calls = []

    def fake_create_fetcher(name, **options):
        calls.append(("fetcher", name, options))
        return fetcher if len(calls) == 1 else robots_fetcher

    def fake_create_crawler(name, **options):
        calls.append(("crawler", name, options))
        return crawler

    monkeypatch.setattr(source_cli, "create_fetcher", fake_create_fetcher)
    monkeypatch.setattr(source_cli, "create_crawler", fake_create_crawler)

    assert main(
        [
            "source",
            "crawl",
            "https://example.com/",
            "--limit",
            "5",
            "--max-depth",
            "2",
            "--delay",
            "0.5",
            "--ignore-robots",
            "--allowed-domain",
            "example.com",
            "--include",
            "*/docs/*",
            "--exclude",
            "*/private/*",
            "--max-html-bytes",
            "5000",
            "--max-robots-bytes",
            "500",
            "--max-links-per-page",
            "50",
            "--timeout",
            "2.5",
        ]
    ) == 0

    assert calls[0] == (
        "fetcher",
        "http",
        {"timeout_seconds": 2.5, "max_bytes": 5000},
    )
    assert calls[1] == (
        "fetcher",
        "http",
        {"timeout_seconds": 2.5, "max_bytes": 500},
    )
    assert calls[2][0:2] == ("crawler", "html")
    assert calls[2][2] == {
        "fetcher": fetcher,
        "robots_fetcher": robots_fetcher,
        "max_html_bytes": 5000,
        "max_robots_bytes": 500,
        "max_links_per_page": 50,
    }
    seeds, policy = crawler.calls[0]
    assert [seed.uri for seed in seeds] == ["https://example.com/"]
    assert policy.max_pages == 5
    assert policy.max_depth == 2
    assert policy.delay_seconds == 0.5
    assert policy.respect_robots_txt is False
    assert policy.allowed_domains == ("example.com",)
    assert policy.include_patterns == ("*/docs/*",)
    assert policy.exclude_patterns == ("*/private/*",)
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["provider"] == "html"
    assert manifest["count"] == 1
    assert manifest["crawl"]["discovered_count"] == 1


def test_source_crawl_preserves_existing_manifest_by_default(monkeypatch, tmp_path, capsys):
    crawler = StaticCrawler([])
    monkeypatch.setattr(source_cli, "create_fetcher", lambda *args, **kwargs: object())
    monkeypatch.setattr(source_cli, "create_crawler", lambda *args, **kwargs: crawler)
    output = tmp_path / "crawl.json"
    output.write_text("keep", encoding="utf-8")

    assert main(
        ["source", "crawl", "https://example.com/", "--output", str(output)]
    ) == 1
    assert output.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err
    assert crawler.calls == []


def test_source_crawl_rejects_output_symlink_before_network(monkeypatch, tmp_path, capsys):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network factory must not be called")

    monkeypatch.setattr(source_cli, "create_fetcher", fail_if_called)
    target = tmp_path / "target.json"
    target.write_text("keep", encoding="utf-8")
    output = tmp_path / "crawl.json"
    output.symlink_to(target)

    assert main(
        [
            "source",
            "crawl",
            "https://example.com/",
            "--output",
            str(output),
            "--overwrite",
        ]
    ) == 1
    assert called is False
    assert target.read_text(encoding="utf-8") == "keep"
    assert "symbolic link" in capsys.readouterr().err


def test_local_fetch_auto_selection_writes_bytes_and_receipt(tmp_path, capsys):
    root = tmp_path / "source-root"
    root.mkdir()
    source = root / "guide.txt"
    source.write_text("hello", encoding="utf-8")
    output = tmp_path / "output" / "guide-copy.txt"

    assert (
        main(
            [
                "source",
                "fetch",
                "guide.txt",
                "--root",
                str(root),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert output.read_bytes() == b"hello"
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["schema_version"] == 1
    assert receipt["fetcher"] == "local-file"
    assert receipt["resource"] == "guide.txt"
    assert receipt["output"] == str(output)
    assert receipt["bytes"] == 5


def test_fetch_refuses_existing_output_then_overwrites_atomically(tmp_path, capsys):
    source = tmp_path / "source.txt"
    source.write_text("replacement", encoding="utf-8")
    output = tmp_path / "output.txt"
    output.write_text("keep me", encoding="utf-8")
    arguments = [
        "source",
        "fetch",
        str(source),
        "--root",
        str(tmp_path),
        "--output",
        str(output),
    ]

    assert main(arguments) == 1
    assert output.read_text(encoding="utf-8") == "keep me"
    assert "already exists" in capsys.readouterr().err

    assert main([*arguments, "--overwrite"]) == 0
    assert output.read_text(encoding="utf-8") == "replacement"
    assert not list(tmp_path.glob(".output.txt.*.tmp"))


def test_http_fetch_auto_selection_passes_limits(monkeypatch, tmp_path, capsys):
    fetcher = StaticFetcher()
    calls = []

    def fake_create_fetcher(name, **options):
        calls.append((name, options))
        return fetcher

    monkeypatch.setattr(source_cli, "create_fetcher", fake_create_fetcher)
    output = tmp_path / "download.txt"

    assert (
        main(
            [
                "source",
                "fetch",
                "https://example.com/source.txt",
                "--output",
                str(output),
                "--max-bytes",
                "99",
                "--timeout",
                "1.5",
            ]
        )
        == 0
    )

    assert calls == [("http", {"max_bytes": 99, "timeout_seconds": 1.5})]
    assert output.read_bytes() == b"downloaded"
    assert json.loads(capsys.readouterr().out)["fetcher"] == "http"


def test_fetch_failure_creates_no_output(monkeypatch, tmp_path, capsys):
    fetcher = StaticFetcher(error=FetchError("safe failure"))
    monkeypatch.setattr(source_cli, "create_fetcher", lambda *args, **options: fetcher)
    output = tmp_path / "missing.txt"

    result = main(
        [
            "source",
            "fetch",
            "https://example.com/source.txt?token=not-real",
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert not output.exists()
    assert capsys.readouterr().err == "source fetch failed: safe failure\n"


def test_auto_fetch_rejects_unknown_scheme_without_output(tmp_path, capsys):
    output = tmp_path / "unknown.bin"

    assert (
        main(
            [
                "source",
                "fetch",
                "s3://bucket/key",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert not output.exists()
    assert "cannot infer" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["source", "discover", "manual", "README.md", "--limit", "0"],
        [
            "source",
            "discover",
            "sitemap",
            "https://example.com",
            "--max-sitemaps",
            "-1",
        ],
        ["source", "fetch", "README.md", "--output", "out", "--max-bytes", "0"],
        ["source", "fetch", "README.md", "--output", "out", "--timeout", "0"],
    ],
)
def test_source_cli_rejects_non_positive_bounds(argv):
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(argv)
    assert caught.value.code == 2


def test_fetch_environment_defaults_are_parsed(monkeypatch):
    monkeypatch.setenv("DOC_HARVESTER_FETCH_ROOT", "/tmp/source-root")
    monkeypatch.setenv("DOC_HARVESTER_MAX_FETCH_BYTES", "123")
    monkeypatch.setenv("DOC_HARVESTER_HTTP_TIMEOUT", "4.5")

    args = build_parser().parse_args(
        ["source", "fetch", "README.md", "--output", "/tmp/output"]
    )

    assert args.root == "/tmp/source-root"
    assert args.max_bytes == 123
    assert args.timeout == 4.5


def test_invalid_numeric_environment_default_fails_during_parsing(monkeypatch):
    monkeypatch.setenv("DOC_HARVESTER_MAX_FETCH_BYTES", "unbounded")

    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(
            ["source", "fetch", "README.md", "--output", "/tmp/output"]
        )

    assert caught.value.code == 2
