"""Privacy-safe inventory for reviewing processed datasets."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from doc_harvester.dataset_storage import (
    DEFAULT_MAX_REPORT_BYTES,
    DatasetValidationError,
    validate_dataset,
)


DEFAULT_MAX_ARTIFACT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_DOCUMENTS = 10_000
_SAFE_FINDING_SEVERITIES = {"info", "warning", "error"}
_SAFE_REPORT_STATUSES = {"complete", "partial", "failed"}
_SAFE_SKIP_REASONS = {"ocr_required", "unsupported_format"}


def _load_json(path: Path, *, max_bytes: int, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as source:
            raw = source.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise DatasetValidationError(f"{label} exceeds {max_bytes} bytes")
        payload = json.loads(raw.decode("utf-8"))
    except DatasetValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DatasetValidationError(
            f"{label} could not be read: {type(error).__name__}"
        ) from None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DatasetValidationError(f"{label} schema_version must be 1")
    return payload


def _safe_text(value: object, *, fallback: str, max_length: int) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        return fallback
    return normalized


def _safe_filename(value: object) -> str:
    normalized = _safe_text(value, fallback="unknown", max_length=1024)
    if normalized == "unknown":
        return normalized
    filename = PurePosixPath(normalized.replace("\\", "/")).name
    return filename if len(filename) <= 255 else "unknown"


def _safe_finding_code(value: object) -> str:
    code = _safe_text(value, fallback="invalid_finding_code", max_length=100)
    if all(character.isalnum() or character in "_.-" for character in code):
        return code
    return "invalid_finding_code"


def _source_uri(outcome: dict[str, Any], *, included: bool) -> dict[str, str]:
    if not included:
        return {}
    uri = outcome.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        return {}
    return {"source_uri": " ".join(uri.split())}


def _processed_entry(
    root: Path,
    outcome: dict[str, Any],
    *,
    max_artifact_bytes: int,
    include_source_uri: bool,
) -> dict[str, Any]:
    document_index = outcome["index"]
    document_root = root / outcome["directory"]
    document = _load_json(
        document_root / "document.json",
        max_bytes=max_artifact_bytes,
        label=f"document {document_index}",
    )
    chunks = _load_json(
        document_root / "chunks.json",
        max_bytes=max_artifact_bytes,
        label=f"chunks {document_index}",
    )
    quality = _load_json(
        document_root / "quality.json",
        max_bytes=max_artifact_bytes,
        label=f"quality {document_index}",
    )
    blocks = document.get("blocks")
    chunk_items = chunks.get("chunks")
    chunk_count = chunks.get("count")
    findings = quality.get("findings")
    if not isinstance(blocks, list) or not all(
        isinstance(block, dict) for block in blocks
    ):
        raise DatasetValidationError(f"document {document_index} blocks must be an array")
    if not isinstance(chunk_items, list) or not all(
        isinstance(chunk, dict) for chunk in chunk_items
    ):
        raise DatasetValidationError(f"chunks {document_index} must contain an array")
    if (
        not isinstance(chunk_count, int)
        or isinstance(chunk_count, bool)
        or chunk_count != len(chunk_items)
    ):
        raise DatasetValidationError(f"chunks {document_index} count does not match array")
    if not isinstance(quality.get("passed"), bool):
        raise DatasetValidationError(f"quality {document_index} passed must be boolean")
    if not isinstance(findings, list) or not all(
        isinstance(finding, dict) for finding in findings
    ):
        raise DatasetValidationError(f"quality {document_index} findings must be an array")

    finding_codes = sorted({_safe_finding_code(finding.get("code")) for finding in findings})
    severity_counts = {severity: 0 for severity in sorted(_SAFE_FINDING_SEVERITIES)}
    for finding in findings:
        severity = finding.get("severity")
        if severity in _SAFE_FINDING_SEVERITIES:
            severity_counts[severity] += 1
    severity_counts = {key: value for key, value in severity_counts.items() if value}
    return {
        "index": document_index,
        "status": "processed",
        "filename": _safe_filename(document.get("filename")),
        "media_type": _safe_text(
            document.get("media_type"), fallback="unknown", max_length=200
        ),
        "extractor": _safe_text(
            document.get("extractor"), fallback="unknown", max_length=100
        ),
        "blocks": len(blocks),
        "chunks": len(chunk_items),
        "quality_passed": quality["passed"],
        "quality_findings": len(findings),
        "quality_finding_codes": finding_codes,
        "quality_severity_counts": severity_counts,
        **_source_uri(outcome, included=include_source_uri),
    }


def _non_processed_entry(
    outcome: dict[str, Any], *, include_source_uri: bool
) -> dict[str, Any]:
    status = outcome.get("status")
    if status not in {"skipped", "failed"}:
        raise DatasetValidationError(
            f"processing outcome {outcome['index']} has unsupported status"
        )
    entry: dict[str, Any] = {"index": outcome["index"], "status": status}
    if status == "skipped":
        reason = outcome.get("reason")
        entry.update(
            {
                "filename": _safe_filename(outcome.get("filename")),
                "media_type": _safe_text(
                    outcome.get("media_type"), fallback="unknown", max_length=200
                ),
                "reason": reason if reason in _SAFE_SKIP_REASONS else "unspecified",
            }
        )
    else:
        entry["reason"] = "processing_failed"
    entry.update(_source_uri(outcome, included=include_source_uri))
    return entry


def inspect_dataset(
    source: str | Path,
    *,
    include_source_uri: bool = False,
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES,
    max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    max_documents: int = DEFAULT_MAX_DOCUMENTS,
) -> dict[str, Any]:
    """Return a bounded inventory without document content or raw failure details."""
    if max_artifact_bytes < 1:
        raise ValueError("max artifact bytes must be at least 1")
    if max_documents < 1:
        raise ValueError("max documents must be at least 1")
    dataset_path = Path(source).expanduser()
    report = validate_dataset(dataset_path, max_report_bytes=max_report_bytes)
    outcomes = report["outcomes"]
    if len(outcomes) > max_documents:
        raise DatasetValidationError(f"dataset exceeds {max_documents} outcomes")
    root = dataset_path.resolve()
    documents = [
        _processed_entry(
            root,
            outcome,
            max_artifact_bytes=max_artifact_bytes,
            include_source_uri=include_source_uri,
        )
        if outcome.get("status") == "processed"
        else _non_processed_entry(outcome, include_source_uri=include_source_uri)
        for outcome in sorted(outcomes, key=lambda item: item["index"])
    ]
    counts = {
        status: sum(document["status"] == status for document in documents)
        for status in ("processed", "skipped", "failed")
    }
    report_status = report.get("status")
    return {
        "schema_version": 1,
        "status": report_status if report_status in _SAFE_REPORT_STATUSES else "unknown",
        "selected_count": len(documents),
        "processed_count": counts["processed"],
        "skipped_count": counts["skipped"],
        "failed_count": counts["failed"],
        "quality_failed_count": sum(
            document["status"] == "processed" and not document["quality_passed"]
            for document in documents
        ),
        "source_uris_included": include_source_uri,
        "documents": documents,
    }
