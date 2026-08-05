from __future__ import annotations

import json

import pytest

from doc_harvester.cli import main
from doc_harvester.dataset_review import inspect_dataset
from doc_harvester.dataset_storage import DatasetValidationError


def make_mixed_dataset(root):
    document_root = root / "documents/00000"
    document_root.mkdir(parents=True)
    (document_root / "document.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "resource": {"uri": "https://example.test/guide?token=secret"},
                "filename": "/private/source/guide.html",
                "media_type": "text/html",
                "extractor": "html",
                "blocks": [
                    {"kind": "text", "text": "private document body"},
                    {"kind": "text", "text": "second private block"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (document_root / "chunks.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "count": 1,
                "chunks": [{"index": 0, "text": "private chunk body"}],
            }
        ),
        encoding="utf-8",
    )
    (document_root / "quality.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "passed": False,
                "findings": [
                    {
                        "code": "tiny_ratio_exceeded",
                        "severity": "warning",
                        "message": "private quality details",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "status": "partial",
        "processed_count": 1,
        "outcomes": [
            {
                "index": 0,
                "status": "processed",
                "uri": "https://example.test/guide?token=secret",
                "directory": "documents/00000",
            },
            {
                "index": 1,
                "status": "skipped",
                "uri": "https://example.test/scan?token=secret",
                "filename": "/private/source/scan.pdf",
                "media_type": "application/pdf",
                "reason": "ocr_required",
            },
            {
                "index": 2,
                "status": "failed",
                "uri": "https://example.test/fail?token=secret",
                "error": "HTTP failure for private customer URL",
            },
        ],
    }
    (root / "processing-report.json").write_text(json.dumps(report), encoding="utf-8")


def test_inspect_dataset_returns_review_inventory_without_private_content(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_mixed_dataset(dataset)

    result = inspect_dataset(dataset)
    rendered = json.dumps(result)

    assert result["status"] == "partial"
    assert result["selected_count"] == 3
    assert (result["processed_count"], result["skipped_count"], result["failed_count"]) == (
        1,
        1,
        1,
    )
    assert result["quality_failed_count"] == 1
    assert result["source_uris_included"] is False
    assert result["documents"] == [
        {
            "index": 0,
            "status": "processed",
            "filename": "guide.html",
            "media_type": "text/html",
            "extractor": "html",
            "blocks": 2,
            "chunks": 1,
            "quality_passed": False,
            "quality_findings": 1,
            "quality_finding_codes": ["tiny_ratio_exceeded"],
            "quality_severity_counts": {"warning": 1},
        },
        {
            "index": 1,
            "status": "skipped",
            "filename": "scan.pdf",
            "media_type": "application/pdf",
            "reason": "ocr_required",
        },
        {"index": 2, "status": "failed", "reason": "processing_failed"},
    ]
    assert "secret" not in rendered
    assert "private" not in rendered
    assert '"source_uri":' not in rendered


def test_inspect_dataset_includes_source_uris_only_by_explicit_opt_in(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_mixed_dataset(dataset)

    result = inspect_dataset(dataset, include_source_uri=True)

    assert result["source_uris_included"] is True
    assert all("source_uri" in document for document in result["documents"])
    assert "token=secret" in result["documents"][0]["source_uri"]


def test_inspect_dataset_validates_bounds_and_artifact_counts(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_mixed_dataset(dataset)

    with pytest.raises(DatasetValidationError, match="exceeds 2 outcomes"):
        inspect_dataset(dataset, max_documents=2)
    with pytest.raises(DatasetValidationError, match="document 0 exceeds"):
        inspect_dataset(dataset, max_artifact_bytes=10)

    chunks_path = dataset / "documents/00000/chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks["count"] = 2
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="count does not match"):
        inspect_dataset(dataset)

    chunks["count"] = True
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="count does not match"):
        inspect_dataset(dataset)


def test_source_inspect_cli_emits_inventory_and_handles_invalid_dataset(tmp_path, capsys):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_mixed_dataset(dataset)

    assert main(["source", "inspect", str(dataset)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["documents"][0]["filename"] == "guide.html"
    assert main(["source", "inspect", str(tmp_path / "missing")]) == 1
    assert "source inspection failed" in capsys.readouterr().err
