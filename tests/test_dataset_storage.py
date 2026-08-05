from __future__ import annotations

import json

import pytest

from doc_harvester.cli import main
from doc_harvester.dataset_storage import (
    DatasetValidationError,
    store_dataset,
    validate_dataset,
)
from doc_harvester.storage import LocalStorage


def make_dataset(root):
    document_root = root / "documents/00000"
    document_root.mkdir(parents=True)
    for filename in ("document.json", "chunks.json", "quality.json"):
        (document_root / filename).write_text(
            json.dumps({"schema_version": 1}), encoding="utf-8"
        )
    report = {
        "schema_version": 1,
        "processed_count": 1,
        "outcomes": [
            {
                "index": 0,
                "status": "processed",
                "directory": "documents/00000",
            }
        ],
    }
    (root / "processing-report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return report


def test_store_dataset_validates_and_copies_to_local_backend(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    report = make_dataset(dataset)
    storage_root = tmp_path / "storage"

    result = store_dataset(
        dataset,
        "review/run-1",
        storage=LocalStorage(storage_root),
    )

    assert validate_dataset(dataset) == report
    assert result.provider == "local"
    assert result.destination == "review/run-1"
    assert result.files_uploaded == 4
    assert (storage_root / "review/run-1/processing-report.json").is_file()
    assert (storage_root / "review/run-1/documents/00000/quality.json").is_file()


def test_store_dataset_rejects_invalid_dataset_before_writing(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    (dataset / "documents/00000/quality.json").unlink()
    storage_root = tmp_path / "storage"

    with pytest.raises(DatasetValidationError, match="missing quality.json"):
        store_dataset(dataset, "review/run-1", storage=LocalStorage(storage_root))

    assert not (storage_root / "review").exists()


def test_validate_dataset_rejects_unsafe_outcome_directory(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    report = make_dataset(dataset)
    report["outcomes"][0]["directory"] = "../outside"
    (dataset / "processing-report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )

    with pytest.raises(DatasetValidationError, match="unsafe directory"):
        validate_dataset(dataset)


def test_validate_dataset_rejects_symbolic_links(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    (dataset / "linked.txt").symlink_to(outside)

    with pytest.raises(DatasetValidationError, match="symbolic link"):
        validate_dataset(dataset)


def test_validate_dataset_rejects_duplicate_or_invalid_outcome_indexes(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    report = make_dataset(dataset)
    report["outcomes"].append(
        {"index": 0, "status": "skipped", "reason": "unsupported_format"}
    )
    (dataset / "processing-report.json").write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="duplicated"):
        validate_dataset(dataset)

    report["outcomes"][-1]["index"] = -1
    (dataset / "processing-report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="non-negative integer"):
        validate_dataset(dataset)


def test_source_store_cli_uses_explicit_local_destination(tmp_path, capsys):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    storage_root = tmp_path / "storage"

    result = main(
        [
            "source",
            "store",
            str(dataset),
            "--storage",
            "local",
            "--local-root",
            str(storage_root),
            "--destination",
            "manual-test/run-1",
        ]
    )

    assert result == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["provider"] == "local"
    assert summary["files_uploaded"] == 4
    assert (storage_root / "manual-test/run-1/processing-report.json").is_file()


def test_source_store_cli_preserves_existing_destination_by_default(tmp_path, capsys):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)
    storage_root = tmp_path / "storage"
    existing = storage_root / "manual-test/run-1/processing-report.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep", encoding="utf-8")

    result = main(
        [
            "source",
            "store",
            str(dataset),
            "--local-root",
            str(storage_root),
            "--destination",
            "manual-test/run-1",
        ]
    )

    assert result == 1
    assert "already contains" in capsys.readouterr().err
    assert existing.read_text(encoding="utf-8") == "keep"
    assert not (storage_root / "manual-test/run-1/documents").exists()


@pytest.mark.parametrize("destination", ["", "../outside", "safe/../../outside"])
def test_store_dataset_rejects_unsafe_destination(tmp_path, destination):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    make_dataset(dataset)

    with pytest.raises(ValueError, match="safe non-empty relative path"):
        store_dataset(dataset, destination, storage=LocalStorage(tmp_path / "storage"))
