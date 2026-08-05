"""Validated storage orchestration for universal processed datasets."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from doc_harvester.core import StorageBackend, StorageResult
from doc_harvester.storage import create_storage


DEFAULT_MAX_REPORT_BYTES = 5 * 1024 * 1024
REQUIRED_DOCUMENT_FILES = ("document.json", "chunks.json", "quality.json")


class DatasetValidationError(ValueError):
    """Raised when a directory is not a safe version-1 processed dataset."""


def _load_report(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if max_bytes < 1:
        raise ValueError("max report bytes must be at least 1")
    try:
        with path.open("rb") as source:
            raw = source.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise DatasetValidationError(f"processing report exceeds {max_bytes} bytes")
        report = json.loads(raw.decode("utf-8"))
    except DatasetValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DatasetValidationError(
            f"processing report could not be read: {type(error).__name__}"
        ) from None
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise DatasetValidationError("processing report schema_version must be 1")
    if not isinstance(report.get("outcomes"), list):
        raise DatasetValidationError("processing report outcomes must be an array")
    return report


def validate_dataset(
    source: str | Path,
    *,
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES,
) -> dict[str, Any]:
    """Validate dataset identity, artifact references, and filesystem safety."""
    root = Path(source).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise DatasetValidationError(f"dataset is not a directory: {root}")
    root = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise DatasetValidationError(
                f"dataset contains a symbolic link: {path.relative_to(root)}"
            )

    report_path = root / "processing-report.json"
    if not report_path.is_file():
        raise DatasetValidationError("dataset is missing processing-report.json")
    report = _load_report(report_path, max_bytes=max_report_bytes)

    processed = 0
    indexes: set[int] = set()
    for index, outcome in enumerate(report["outcomes"]):
        if not isinstance(outcome, dict):
            raise DatasetValidationError(f"processing outcome {index} must be an object")
        document_index = outcome.get("index")
        if (
            not isinstance(document_index, int)
            or isinstance(document_index, bool)
            or document_index < 0
        ):
            raise DatasetValidationError(
                f"processing outcome {index} requires a non-negative integer index"
            )
        if document_index in indexes:
            raise DatasetValidationError(
                f"processing outcome index is duplicated: {document_index}"
            )
        indexes.add(document_index)
        if outcome.get("status") != "processed":
            continue
        processed += 1
        relative = outcome.get("directory")
        if not isinstance(relative, str) or not relative.strip():
            raise DatasetValidationError(
                f"processed outcome {index} requires a directory"
            )
        parts = PurePosixPath(relative).parts
        if PurePosixPath(relative).is_absolute() or ".." in parts:
            raise DatasetValidationError(
                f"processed outcome {index} has an unsafe directory"
            )
        document_root = (root / Path(*parts)).resolve()
        if root not in document_root.parents:
            raise DatasetValidationError(
                f"processed outcome {index} directory escapes the dataset"
            )
        for filename in REQUIRED_DOCUMENT_FILES:
            artifact = document_root / filename
            if not artifact.is_file():
                raise DatasetValidationError(
                    f"processed outcome {index} is missing {filename}"
                )

    declared = report.get("processed_count")
    if not isinstance(declared, int) or isinstance(declared, bool) or declared != processed:
        raise DatasetValidationError(
            "processing report processed_count does not match outcomes"
        )
    return report


def store_dataset(
    source: str | Path,
    destination: str,
    *,
    storage_name: str | None = None,
    overwrite: bool = False,
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES,
    storage: StorageBackend | None = None,
    **storage_options: Any,
) -> StorageResult:
    """Validate and store a processed dataset through a universal backend."""
    normalized_destination = destination.strip("/")
    destination_parts = PurePosixPath(normalized_destination).parts
    if not normalized_destination or ".." in destination_parts:
        raise ValueError("storage destination must be a safe non-empty relative path")
    validate_dataset(source, max_report_bytes=max_report_bytes)
    backend = storage or create_storage(storage_name, **storage_options)
    return backend.upload_tree(source, normalized_destination, overwrite=overwrite)
