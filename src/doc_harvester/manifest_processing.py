"""Manifest-driven, credential-free local processing orchestration."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from doc_harvester.chunkers import create_chunker
from doc_harvester.core import ChunkingOptions, FetchedArtifact, ResourceRef
from doc_harvester.extractors import select_extractor
from doc_harvester.fetchers import FetchError, create_fetcher


DEFAULT_MAX_MANIFEST_BYTES = 5 * 1024 * 1024


class ManifestValidationError(ValueError):
    """Raised when an input resource manifest violates schema version 1."""


def load_manifest(path: str | Path, *, max_bytes: int = DEFAULT_MAX_MANIFEST_BYTES) -> dict:
    manifest_path = Path(path)
    if max_bytes < 1:
        raise ValueError("max manifest bytes must be at least 1")
    if not manifest_path.is_file():
        raise ManifestValidationError(f"manifest is not a file: {manifest_path.name}")
    try:
        with manifest_path.open("rb") as source:
            raw_payload = source.read(max_bytes + 1)
        if len(raw_payload) > max_bytes:
            raise ManifestValidationError(f"manifest exceeds {max_bytes} bytes")
        payload = json.loads(raw_payload.decode("utf-8"))
    except ManifestValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            f"manifest could not be read: {type(error).__name__}"
        ) from None
    if not isinstance(payload, dict):
        raise ManifestValidationError("manifest must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ManifestValidationError("manifest schema_version must be 1")
    if not isinstance(payload.get("provider"), str) or not payload["provider"].strip():
        raise ManifestValidationError("manifest provider must be a non-empty string")
    resources = payload.get("resources")
    if not isinstance(resources, list):
        raise ManifestValidationError("manifest resources must be an array")
    count = payload.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count != len(resources):
        raise ManifestValidationError("manifest count must match resources length")
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise ManifestValidationError(f"manifest resource {index} must be an object")
        if not isinstance(resource.get("uri"), str) or not resource["uri"].strip():
            raise ManifestValidationError(
                f"manifest resource {index} uri must be a non-empty string"
            )
        for field in ("source", "media_type"):
            if field in resource and not isinstance(resource[field], str):
                raise ManifestValidationError(
                    f"manifest resource {index} {field} must be a string"
                )
        metadata = resource.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ManifestValidationError(
                f"manifest resource {index} metadata must be an object"
            )
    return payload


def _resource_from_payload(payload: dict) -> ResourceRef:
    return ResourceRef(
        payload["uri"],
        source=str(payload.get("source", "")),
        media_type=str(payload.get("media_type", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def _infer_fetcher(uri: str) -> str:
    try:
        scheme = urlsplit(uri).scheme.lower()
    except ValueError:
        raise FetchError("cannot infer a fetcher from an invalid URI") from None
    if scheme in {"http", "https"}:
        return "http"
    if scheme in {"", "file"}:
        return "local-file"
    raise FetchError(f"cannot infer a fetcher for URI scheme: {scheme}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _artifact_payload(artifact: FetchedArtifact, extractor_name: str, document) -> dict:
    return {
        "schema_version": 1,
        "resource": {
            "uri": artifact.resource.uri,
            "source": artifact.resource.source,
            "media_type": artifact.resource.media_type,
            "metadata": dict(artifact.resource.metadata),
        },
        "extractor": extractor_name,
        "filename": artifact.filename,
        "media_type": artifact.media_type,
        "metadata": dict(document.metadata),
        "blocks": [
            {
                "text": block.text,
                "kind": block.kind,
                "page": block.page,
                "section": block.section,
                "metadata": dict(block.metadata),
            }
            for block in document.blocks
        ],
    }


def _chunks_payload(document_uri: str, chunker_name: str, chunks) -> dict:
    return {
        "schema_version": 1,
        "document": document_uri,
        "chunker": chunker_name,
        "count": len(chunks),
        "chunks": [
            {
                "index": chunk.index,
                "text": chunk.text,
                "metadata": dict(chunk.metadata),
            }
            for chunk in chunks
        ],
    }


def process_manifest(
    manifest_path: str | Path,
    output: str | Path,
    *,
    root: str | Path = ".",
    limit: int = 100,
    max_manifest_bytes: int = DEFAULT_MAX_MANIFEST_BYTES,
    max_fetch_bytes: int = 50 * 1024 * 1024,
    timeout_seconds: float = 30.0,
    max_tokens: int = 800,
    fetcher_builder: Callable[..., Any] | None = None,
    extractor_selector: Callable[[FetchedArtifact], Any] | None = None,
) -> dict:
    """Process supported resources and atomically publish a local dataset directory."""
    if limit < 1:
        raise ValueError("processing limit must be at least 1")
    if max_fetch_bytes < 1:
        raise ValueError("max fetch bytes must be at least 1")
    if timeout_seconds <= 0:
        raise ValueError("HTTP timeout must be positive")
    if max_tokens < 1:
        raise ValueError("max tokens must be at least 1")

    destination = Path(output)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"output already exists: {destination}")
    manifest = load_manifest(manifest_path, max_bytes=max_manifest_bytes)
    resources = manifest["resources"][:limit]
    build_fetcher = fetcher_builder or create_fetcher
    choose_extractor = extractor_selector or select_extractor
    chunker = create_chunker("structure-aware")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    )
    outcomes: list[dict[str, Any]] = []
    try:
        for index, resource_payload in enumerate(resources):
            resource = _resource_from_payload(resource_payload)
            base_outcome: dict[str, Any] = {"index": index, "uri": resource.uri}
            document_directory: Path | None = None
            try:
                fetcher_name = _infer_fetcher(resource.uri)
                options: dict[str, Any] = {"max_bytes": max_fetch_bytes}
                if fetcher_name == "http":
                    options["timeout_seconds"] = timeout_seconds
                else:
                    options["root"] = root
                artifact = build_fetcher(fetcher_name, **options).fetch(resource)
                extractor = choose_extractor(artifact)
                if extractor is None:
                    outcomes.append(
                        {
                            **base_outcome,
                            "status": "skipped",
                            "reason": "unsupported_format",
                            "media_type": artifact.media_type,
                            "filename": artifact.filename,
                        }
                    )
                    continue
                document = extractor.extract(artifact)
                if not document.blocks:
                    raise ValueError("extraction produced no content blocks")
                chunks = list(
                    chunker.chunk(
                        document,
                        ChunkingOptions(
                            strategy=chunker.name,
                            max_tokens=max_tokens,
                            overlap_tokens=0,
                        ),
                    )
                )
                if not chunks:
                    raise ValueError("chunking produced no chunks")

                relative_directory = Path("documents") / f"{index:05d}"
                document_directory = staging / relative_directory
                _write_json(
                    document_directory / "document.json",
                    _artifact_payload(artifact, extractor.name, document),
                )
                _write_json(
                    document_directory / "chunks.json",
                    _chunks_payload(resource.uri, chunker.name, chunks),
                )
                outcomes.append(
                    {
                        **base_outcome,
                        "status": "processed",
                        "fetcher": fetcher_name,
                        "extractor": extractor.name,
                        "blocks": len(document.blocks),
                        "chunks": len(chunks),
                        "directory": relative_directory.as_posix(),
                    }
                )
            except FetchError as error:
                if document_directory is not None:
                    shutil.rmtree(document_directory, ignore_errors=True)
                outcomes.append({**base_outcome, "status": "failed", "error": str(error)})
            except Exception as error:
                if document_directory is not None:
                    shutil.rmtree(document_directory, ignore_errors=True)
                outcomes.append(
                    {
                        **base_outcome,
                        "status": "failed",
                        "error": f"processing failed: {type(error).__name__}",
                    }
                )

        processed_count = sum(item["status"] == "processed" for item in outcomes)
        skipped_count = sum(item["status"] == "skipped" for item in outcomes)
        failed_count = sum(item["status"] == "failed" for item in outcomes)
        report = {
            "schema_version": 1,
            "manifest": Path(manifest_path).name,
            "manifest_provider": manifest["provider"],
            "selected_count": len(resources),
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "status": (
                "failed"
                if processed_count == 0
                else "partial"
                if failed_count
                else "complete"
            ),
            "max_tokens": max_tokens,
            "outcomes": outcomes,
        }
        _write_json(staging / "processing-report.json", report)
        os.rename(staging, destination)
        return report
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
