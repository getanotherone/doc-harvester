from __future__ import annotations

import hashlib
import json

import pytest

from doc_harvester.cli import main
from doc_harvester.dataset_publication import render_dataset_document
from doc_harvester.dataset_storage import DatasetValidationError


def make_dataset(root):
    document_root = root / "documents/00000"
    document_root.mkdir(parents=True)
    document = {
        "schema_version": 1,
        "filename": "installation-guide.html",
        "resource": {"uri": "https://example.test/guide?token=private"},
        "metadata": {"quality_status": "passed"},
        "blocks": [
            {"kind": "heading", "text": "Installation"},
            {"kind": "text", "text": "Connect the device."},
            {"kind": "list_item", "text": "Verify the status light"},
        ],
    }
    (document_root / "document.json").write_text(json.dumps(document), encoding="utf-8")
    for filename in ("chunks.json", "quality.json"):
        (document_root / filename).write_text(
            json.dumps({"schema_version": 1}), encoding="utf-8"
        )
    report = {
        "schema_version": 1,
        "processed_count": 1,
        "outcomes": [
            {"index": 0, "status": "processed", "directory": "documents/00000"}
        ],
    }
    (root / "processing-report.json").write_text(json.dumps(report), encoding="utf-8")


def test_render_dataset_document_creates_reviewable_markdown_without_source_uri(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    output = tmp_path / "review.md"

    result = render_dataset_document(dataset, output, document_index=0)
    rendered = output.read_text(encoding="utf-8")

    assert "# installation-guide" in rendered
    assert "## Installation" in rendered
    assert "- Verify the status light" in rendered
    assert "token=private" not in rendered
    assert result["source_uri_included"] is False
    assert result["bytes"] == len(output.read_bytes())
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_render_dataset_document_includes_source_uri_only_when_requested(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    output = tmp_path / "review.md"

    result = render_dataset_document(
        dataset, output, document_index=0, include_source_uri=True
    )

    assert "token=private" in output.read_text(encoding="utf-8")
    assert result["source_uri_included"] is True


def test_render_dataset_document_preserves_existing_output_by_default(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    output = tmp_path / "review.md"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        render_dataset_document(dataset, output, document_index=0)

    assert output.read_text(encoding="utf-8") == "keep"


def test_render_dataset_document_rejects_dataset_root_symlink(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    linked_dataset = tmp_path / "linked-dataset"
    linked_dataset.symlink_to(dataset, target_is_directory=True)

    with pytest.raises(DatasetValidationError, match="not a directory"):
        render_dataset_document(
            linked_dataset, tmp_path / "review.md", document_index=0
        )


def test_render_dataset_document_enforces_index_block_and_output_boundaries(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)

    with pytest.raises(DatasetValidationError, match="index not found"):
        render_dataset_document(dataset, tmp_path / "missing.md", document_index=1)
    with pytest.raises(DatasetValidationError, match="exceeds 2 blocks"):
        render_dataset_document(
            dataset, tmp_path / "large.md", document_index=0, max_blocks=2
        )
    with pytest.raises(ValueError, match="source dataset"):
        render_dataset_document(
            dataset, dataset / "review.md", document_index=0
        )
    target = tmp_path / "target.md"
    target.write_text("keep", encoding="utf-8")
    linked_output = tmp_path / "linked.md"
    linked_output.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        render_dataset_document(dataset, linked_output, document_index=0, overwrite=True)
    assert target.read_text(encoding="utf-8") == "keep"


def test_source_render_cli_emits_summary_and_rejects_negative_index(tmp_path, capsys):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    output = tmp_path / "review.md"

    assert main(
        [
            "source",
            "render",
            str(dataset),
            "--document-index",
            "0",
            "--output",
            str(output),
            "--title",
            "Reviewed guide",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Reviewed guide"
    with pytest.raises(SystemExit):
        main(
            [
                "source",
                "render",
                str(dataset),
                "--document-index",
                "-1",
                "--output",
                str(tmp_path / "invalid.md"),
            ]
        )
