"""Reviewable Markdown preparation for processed dataset documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from doc_harvester.dataset_storage import DatasetValidationError, validate_dataset


DEFAULT_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_PUBLICATION_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_BLOCKS = 10_000


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


def _safe_title(value: str, fallback: str) -> str:
    title = " ".join(value.split()) or fallback
    if len(title) > 200:
        raise ValueError("publication title cannot exceed 200 characters")
    return title


def _inline_code(value: str) -> str:
    longest_run = 0
    current_run = 0
    for character in value:
        if character == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    delimiter = "`" * (longest_run + 1)
    padding = " " if value.startswith(("`", " ")) or value.endswith(("`", " ")) else ""
    return f"{delimiter}{padding}{value}{padding}{delimiter}"


def _render_block(block: dict[str, Any], index: int) -> str:
    text = block.get("text")
    if not isinstance(text, str):
        raise DatasetValidationError(f"document block {index} text must be a string")
    text = text.strip()
    if not text:
        return ""
    kind = block.get("kind", "text")
    if not isinstance(kind, str):
        raise DatasetValidationError(f"document block {index} kind must be a string")
    if kind == "heading" and not text.startswith("#"):
        return f"## {text}"
    if kind == "list_item" and not text.startswith(("- ", "* ", "+ ")):
        return f"- {text}"
    return text


def render_dataset_document(
    source: str | Path,
    output: str | Path,
    *,
    document_index: int,
    title: str = "",
    include_source_uri: bool = False,
    overwrite: bool = False,
    max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
    max_publication_bytes: int = DEFAULT_MAX_PUBLICATION_BYTES,
    max_blocks: int = DEFAULT_MAX_BLOCKS,
) -> dict[str, Any]:
    """Render one validated processed document into an explicit Markdown artifact."""
    if isinstance(document_index, bool) or not isinstance(document_index, int):
        raise ValueError("document index must be an integer")
    if document_index < 0:
        raise ValueError("document index cannot be negative")
    for label, value in (
        ("max document bytes", max_document_bytes),
        ("max publication bytes", max_publication_bytes),
        ("max blocks", max_blocks),
    ):
        if value < 1:
            raise ValueError(f"{label} must be at least 1")

    dataset_path = Path(source).expanduser()
    report = validate_dataset(dataset_path)
    dataset_root = dataset_path.resolve()
    outcome = next(
        (
            item
            for item in report["outcomes"]
            if isinstance(item, dict)
            and item.get("status") == "processed"
            and item.get("index") == document_index
        ),
        None,
    )
    if outcome is None:
        raise DatasetValidationError(
            f"processed document index not found: {document_index}"
        )

    document_path = dataset_root / outcome["directory"] / "document.json"
    document = _load_json(
        document_path,
        max_bytes=max_document_bytes,
        label=f"document {document_index}",
    )
    blocks = document.get("blocks")
    if not isinstance(blocks, list):
        raise DatasetValidationError(f"document {document_index} blocks must be an array")
    if len(blocks) > max_blocks:
        raise DatasetValidationError(
            f"document {document_index} exceeds {max_blocks} blocks"
        )
    if not all(isinstance(block, dict) for block in blocks):
        raise DatasetValidationError(
            f"document {document_index} blocks must contain objects"
        )

    filename = document.get("filename")
    default_title = (
        Path(filename).stem
        if isinstance(filename, str) and filename.strip()
        else f"Document {document_index}"
    )
    rendered_title = _safe_title(title, default_title)
    metadata = document.get("metadata", {})
    raw_quality_status = (
        metadata.get("quality_status", "unknown")
        if isinstance(metadata, dict)
        else "unknown"
    )
    quality_status = (
        " ".join(raw_quality_status.split())
        if isinstance(raw_quality_status, str)
        else "unknown"
    ) or "unknown"
    if len(quality_status) > 100:
        raise DatasetValidationError("document quality status exceeds 100 characters")
    header = [
        "<!-- Generated by doc-harvester. Review before publishing. -->",
        "",
        f"# {rendered_title}",
        "",
        f"- Dataset document: `{document_index}`",
        f"- Quality: {_inline_code(quality_status)}",
    ]
    if include_source_uri:
        resource = document.get("resource", {})
        uri = resource.get("uri") if isinstance(resource, dict) else None
        if isinstance(uri, str) and uri:
            header.append(f"- Source URI: {_inline_code(' '.join(uri.split()))}")
    rendered_blocks = [
        rendered
        for index, block in enumerate(blocks)
        if (rendered := _render_block(block, index))
    ]
    markdown = "\n".join(header) + "\n\n---\n\n" + "\n\n".join(rendered_blocks) + "\n"
    encoded = markdown.encode("utf-8")
    if len(encoded) > max_publication_bytes:
        raise DatasetValidationError(
            f"publication exceeds {max_publication_bytes} bytes"
        )

    destination = Path(output).expanduser()
    if destination.is_symlink():
        raise ValueError(f"publication output is a symbolic link: {destination}")
    destination = destination.resolve()
    if dataset_root == destination or dataset_root in destination.parents:
        raise ValueError("publication output cannot modify the source dataset")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"publication output already exists: {destination}")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"publication output is not a file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(encoded)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "schema_version": 1,
        "document_index": document_index,
        "title": rendered_title,
        "quality_status": quality_status,
        "source_uri_included": include_source_uri,
        "output": str(destination),
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
