from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_harvester.cli import build_parser, main
from doc_harvester.core import FetchedArtifact
from doc_harvester.fetchers import FetchError
from doc_harvester.manifest_processing import (
    ManifestValidationError,
    load_manifest,
    process_manifest,
)
from tests.pdf_fixture import build_text_pdf


def write_manifest(path: Path, resources, **overrides):
    payload = {
        "schema_version": 1,
        "provider": "manual",
        "count": len(resources),
        "resources": resources,
        **overrides,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class MappingFetcher:
    def __init__(self, name, mapping):
        self.name = name
        self.mapping = mapping

    def fetch(self, resource):
        value = self.mapping[resource.uri]
        if isinstance(value, Exception):
            raise value
        content, media_type, filename = value
        return FetchedArtifact(
            resource,
            content,
            media_type=media_type,
            filename=filename,
            metadata={"bytes": len(content)},
        )


def test_process_manifest_writes_local_text_and_html_dataset(tmp_path):
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "guide.md").write_text(
        "# Guide\n\nA technical paragraph with useful content.", encoding="utf-8"
    )
    (source_root / "page.html").write_text(
        "<html><body><nav>Menu</nav><main><h1>Product</h1>"
        "<p>Technical description.</p><p>Installation requirement.</p></main></body></html>",
        encoding="utf-8",
    )
    manifest = write_manifest(
        tmp_path / "manifest.json",
        [
            {"uri": "guide.md", "source": "manual", "media_type": "text/markdown"},
            {"uri": "page.html", "source": "manual", "media_type": "text/html"},
        ],
    )
    output = tmp_path / "dataset"

    report = process_manifest(manifest, output, root=source_root, max_tokens=80)

    assert report["status"] == "complete"
    assert report["processed_count"] == 2
    assert report["failed_count"] == report["skipped_count"] == 0
    persisted = json.loads((output / "processing-report.json").read_text())
    assert persisted == report
    first_document = json.loads(
        (output / "documents/00000/document.json").read_text(encoding="utf-8")
    )
    first_chunks = json.loads(
        (output / "documents/00000/chunks.json").read_text(encoding="utf-8")
    )
    assert first_document["extractor"] == "text"
    assert first_document["blocks"]
    assert first_chunks["count"] >= 1
    assert first_chunks["chunks"][0]["text"]
    assert sorted(path.name for path in output.rglob("*") if path.is_file()) == [
        "chunks.json",
        "chunks.json",
        "document.json",
        "document.json",
        "processing-report.json",
    ]


def test_process_manifest_preserves_mixed_outcomes(tmp_path):
    resources = [
        {"uri": "https://example.com/good.txt", "source": "manual"},
        {"uri": "https://example.com/unsupported.docx", "source": "manual"},
        {"uri": "https://example.com/fail.txt", "source": "manual"},
    ]
    manifest = write_manifest(tmp_path / "manifest.json", resources)
    mapping = {
        resources[0]["uri"]: (b"Useful technical text.", "text/plain", "good.txt"),
        resources[1]["uri"]: (
            b"PK synthetic",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "unsupported.docx",
        ),
        resources[2]["uri"]: FetchError("HTTP 503 while fetching https://example.com/fail.txt"),
    }
    calls = []

    def builder(name, **options):
        calls.append((name, options))
        return MappingFetcher(name, mapping)

    output = tmp_path / "dataset"
    report = process_manifest(
        manifest,
        output,
        fetcher_builder=builder,
        max_fetch_bytes=99,
        timeout_seconds=2.5,
    )

    assert report["status"] == "partial"
    assert (report["processed_count"], report["skipped_count"], report["failed_count"]) == (
        1,
        1,
        1,
    )
    assert [item["status"] for item in report["outcomes"]] == [
        "processed",
        "skipped",
        "failed",
    ]
    assert report["outcomes"][2]["error"] == (
        "HTTP 503 while fetching https://example.com/fail.txt"
    )
    assert all(name == "http" for name, _ in calls)
    assert all(options == {"max_bytes": 99, "timeout_seconds": 2.5} for _, options in calls)
    assert (output / "documents/00000/chunks.json").is_file()
    assert not (output / "documents/00001").exists()


def test_process_manifest_extracts_and_chunks_local_pdf(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    (root / "guide.pdf").write_bytes(
        build_text_pdf("Installation requirements.", "Maintenance instructions.")
    )
    manifest = write_manifest(
        tmp_path / "manifest.json",
        [{"uri": "guide.pdf", "media_type": "application/pdf"}],
    )
    output = tmp_path / "dataset"

    report = process_manifest(manifest, output, root=root, max_pdf_pages=5)

    assert report["status"] == "complete"
    assert report["outcomes"][0]["extractor"] == "pdf"
    document = json.loads(
        (output / "documents/00000/document.json").read_text(encoding="utf-8")
    )
    chunks = json.loads(
        (output / "documents/00000/chunks.json").read_text(encoding="utf-8")
    )
    assert [block["page"] for block in document["blocks"]] == [1, 2]
    assert document["metadata"]["page_count"] == 2
    assert chunks["count"] >= 1


def test_process_manifest_reports_image_only_pdf_as_ocr_required(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    (root / "scan.pdf").write_bytes(build_text_pdf(""))
    manifest = write_manifest(tmp_path / "manifest.json", [{"uri": "scan.pdf"}])

    report = process_manifest(manifest, tmp_path / "dataset", root=root)

    assert report["status"] == "failed"
    assert report["processed_count"] == report["failed_count"] == 0
    assert report["skipped_count"] == 1
    assert report["outcomes"][0] == {
        "index": 0,
        "uri": "scan.pdf",
        "status": "skipped",
        "reason": "ocr_required",
        "media_type": "application/pdf",
        "filename": "scan.pdf",
        "pages": 1,
    }


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema_version": 2, "provider": "manual", "count": 0, "resources": []},
        {"schema_version": 1, "provider": "", "count": 0, "resources": []},
        {"schema_version": 1, "provider": "manual", "count": 1, "resources": []},
        {
            "schema_version": 1,
            "provider": "manual",
            "count": 1,
            "resources": [{"uri": "", "metadata": {}}],
        },
        {
            "schema_version": 1,
            "provider": "manual",
            "count": 1,
            "resources": [{"uri": "guide.txt", "metadata": []}],
        },
    ],
)
def test_invalid_manifest_is_rejected_without_output(tmp_path, payload):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "dataset"

    with pytest.raises(ManifestValidationError):
        process_manifest(manifest, output)

    assert not output.exists()
    assert not list(tmp_path.glob(".dataset.*.tmp"))


def test_manifest_byte_bound_is_enforced(tmp_path):
    manifest = write_manifest(tmp_path / "manifest.json", [])

    with pytest.raises(ManifestValidationError, match="exceeds"):
        load_manifest(manifest, max_bytes=5)


def test_existing_output_is_preserved(tmp_path):
    manifest = write_manifest(tmp_path / "manifest.json", [])
    output = tmp_path / "dataset"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        process_manifest(manifest, output)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_processing_limit_selects_only_first_manifest_resource(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    (root / "one.txt").write_text("First useful document.", encoding="utf-8")
    (root / "two.txt").write_text("Second useful document.", encoding="utf-8")
    manifest = write_manifest(
        tmp_path / "manifest.json",
        [{"uri": "one.txt"}, {"uri": "two.txt"}],
    )

    report = process_manifest(manifest, tmp_path / "dataset", root=root, limit=1)

    assert report["selected_count"] == report["processed_count"] == 1
    assert len(report["outcomes"]) == 1


def test_source_process_cli_runs_local_pipeline(tmp_path, capsys):
    root = tmp_path / "sources"
    root.mkdir()
    (root / "guide.txt").write_text("Useful technical document.", encoding="utf-8")
    manifest = write_manifest(tmp_path / "manifest.json", [{"uri": "guide.txt"}])
    output = tmp_path / "dataset"

    result = main(
        [
            "source",
            "process",
            str(manifest),
            "--root",
            str(root),
            "--output",
            str(output),
            "--max-tokens",
            "50",
        ]
    )

    assert result == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "complete"
    assert summary["processed_count"] == 1
    assert summary["output"] == str(output)


@pytest.mark.parametrize(
    "option",
    [
        "--limit",
        "--max-manifest-bytes",
        "--max-bytes",
        "--timeout",
        "--max-tokens",
        "--max-pdf-pages",
    ],
)
def test_source_process_cli_rejects_non_positive_bounds(option):
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(
            ["source", "process", "manifest.json", "--output", "dataset", option, "0"]
        )
    assert caught.value.code == 2
