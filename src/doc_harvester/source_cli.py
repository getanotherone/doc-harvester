"""Credential-free discovery and fetch command orchestration."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from doc_harvester.core import DiscoveryRequest, ResourceRef
from doc_harvester.discovery import create_discovery_provider
from doc_harvester.fetchers import FetchError, create_fetcher


DEFAULT_DISCOVERY_LIMIT = 100
DEFAULT_MAX_SITEMAPS = 20
DEFAULT_MAX_XML_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FETCH_BYTES = 50 * 1024 * 1024
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_CHUNK_TOKENS = 800
DEFAULT_MAX_PDF_PAGES = 1000


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _environment_default(name: str, fallback: int | float | str) -> str:
    return os.environ.get(name, str(fallback))


def _add_manifest_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=_environment_default("DOC_HARVESTER_DISCOVERY_LIMIT", DEFAULT_DISCOVERY_LIMIT),
        help="Maximum resources to return (default: 100)",
    )
    parser.add_argument("--output", help="Write the JSON manifest to this file")


def add_source_commands(commands: argparse._SubParsersAction) -> None:
    """Attach the additive source command group to the public parser."""
    source = commands.add_parser(
        "source", help="Discover or fetch sources without provider credentials"
    )
    source_commands = source.add_subparsers(dest="source_command", required=True)

    discover = source_commands.add_parser(
        "discover", help="Create a universal resource manifest"
    )
    discovery_modes = discover.add_subparsers(dest="discovery_mode", required=True)

    manual = discovery_modes.add_parser(
        "manual", help="Discover explicit local paths or HTTP(S)/file URIs"
    )
    manual.add_argument("uri", nargs="+", help="Resource path or URI")
    _add_manifest_options(manual)
    manual.set_defaults(handler=_run_manual_discovery)

    sitemap = discovery_modes.add_parser(
        "sitemap", help="Discover HTTP(S) resources from sitemaps and robots.txt"
    )
    sitemap.add_argument("root_uri", help="Website root or explicit sitemap URI")
    _add_manifest_options(sitemap)
    sitemap.add_argument(
        "--max-sitemaps",
        type=_positive_int,
        default=_environment_default("DOC_HARVESTER_MAX_SITEMAPS", DEFAULT_MAX_SITEMAPS),
        help="Maximum sitemap files to process (default: 20)",
    )
    sitemap.add_argument(
        "--max-xml-bytes",
        type=_positive_int,
        default=_environment_default(
            "DOC_HARVESTER_MAX_SITEMAP_BYTES", DEFAULT_MAX_XML_BYTES
        ),
        help="Maximum compressed response and decoded XML bytes (default: 10485760)",
    )
    sitemap.add_argument(
        "--timeout",
        type=_positive_float,
        default=_environment_default(
            "DOC_HARVESTER_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT_SECONDS
        ),
        help="HTTP timeout in seconds (default: 30)",
    )
    sitemap.add_argument(
        "--no-robots",
        dest="include_robots",
        action="store_false",
        help="Do not inspect robots.txt for Sitemap declarations",
    )
    sitemap.add_argument(
        "--allow-cross-origin",
        dest="same_origin_only",
        action="store_false",
        help="Allow HTTP(S) sitemap/page locations on another origin",
    )
    sitemap.set_defaults(
        handler=_run_sitemap_discovery,
        include_robots=True,
        same_origin_only=True,
    )

    fetch = source_commands.add_parser(
        "fetch", help="Fetch one bounded HTTP or local resource into an explicit file"
    )
    fetch.add_argument("uri", help="HTTP(S) URL, local path, or local file URI")
    fetch.add_argument("--output", required=True, help="Destination file for fetched bytes")
    fetch.add_argument(
        "--fetcher",
        choices=("auto", "http", "local-file"),
        default="auto",
        help="Fetcher selection (default: infer safely from the URI)",
    )
    fetch.add_argument(
        "--root",
        default=os.environ.get("DOC_HARVESTER_FETCH_ROOT", "."),
        help="Configured root for local paths (default: current directory)",
    )
    fetch.add_argument(
        "--max-bytes",
        type=_positive_int,
        default=_environment_default(
            "DOC_HARVESTER_MAX_FETCH_BYTES", DEFAULT_MAX_FETCH_BYTES
        ),
        help="Maximum accepted resource bytes (default: 52428800)",
    )
    fetch.add_argument(
        "--timeout",
        type=_positive_float,
        default=_environment_default(
            "DOC_HARVESTER_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT_SECONDS
        ),
        help="HTTP timeout in seconds (default: 30)",
    )
    fetch.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output atomically"
    )
    fetch.set_defaults(handler=_run_fetch)

    process = source_commands.add_parser(
        "process", help="Process a version-1 manifest into a new local chunk dataset"
    )
    process.add_argument("manifest", help="Version-1 discovery manifest JSON file")
    process.add_argument("--output", required=True, help="New destination dataset directory")
    process.add_argument(
        "--root",
        default=os.environ.get("DOC_HARVESTER_FETCH_ROOT", "."),
        help="Configured root for local manifest resources",
    )
    process.add_argument(
        "--limit",
        type=_positive_int,
        default=_environment_default("DOC_HARVESTER_DISCOVERY_LIMIT", DEFAULT_DISCOVERY_LIMIT),
        help="Maximum manifest resources to process (default: 100)",
    )
    process.add_argument(
        "--max-manifest-bytes",
        type=_positive_int,
        default=_environment_default("DOC_HARVESTER_MAX_MANIFEST_BYTES", 5 * 1024 * 1024),
        help="Maximum manifest file bytes (default: 5242880)",
    )
    process.add_argument(
        "--max-bytes",
        type=_positive_int,
        default=_environment_default(
            "DOC_HARVESTER_MAX_FETCH_BYTES", DEFAULT_MAX_FETCH_BYTES
        ),
        help="Maximum bytes accepted for each resource (default: 52428800)",
    )
    process.add_argument(
        "--timeout",
        type=_positive_float,
        default=_environment_default(
            "DOC_HARVESTER_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT_SECONDS
        ),
        help="HTTP timeout in seconds (default: 30)",
    )
    process.add_argument(
        "--max-tokens",
        type=_positive_int,
        default=_environment_default(
            "DOC_HARVESTER_MAX_CHUNK_TOKENS", DEFAULT_MAX_CHUNK_TOKENS
        ),
        help="Absolute chunk token bound (default: 800)",
    )
    process.add_argument(
        "--max-pdf-pages",
        type=_positive_int,
        default=_environment_default(
            "DOC_HARVESTER_MAX_PDF_PAGES", DEFAULT_MAX_PDF_PAGES
        ),
        help="Maximum pages accepted from one PDF (default: 1000)",
    )
    process.set_defaults(handler=_run_process)


def _resource_payload(resource: ResourceRef) -> dict[str, object]:
    return {
        "uri": resource.uri,
        "source": resource.source,
        "media_type": resource.media_type,
        "metadata": dict(resource.metadata),
    }


def _manifest(provider_name: str, resources: list[ResourceRef]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": provider_name,
        "count": len(resources),
        "resources": [_resource_payload(resource) for resource in resources],
    }


def _emit_json(payload: dict[str, object], output: str | None = None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _run_manual_discovery(args: argparse.Namespace) -> int:
    try:
        provider = create_discovery_provider("manual")
        resources = list(
            provider.discover(
                DiscoveryRequest(manual_uris=tuple(args.uri), limit=args.limit)
            )
        )
        _emit_json(_manifest(provider.name, resources), args.output)
    except (FetchError, OSError, ValueError) as error:
        print(f"source discovery failed: {error}", file=sys.stderr)
        return 1
    return 0


def _run_sitemap_discovery(args: argparse.Namespace) -> int:
    try:
        fetcher = create_fetcher(
            "http", timeout_seconds=args.timeout, max_bytes=args.max_xml_bytes
        )
        provider = create_discovery_provider(
            "sitemap",
            fetcher=fetcher,
            max_sitemaps=args.max_sitemaps,
            max_xml_bytes=args.max_xml_bytes,
            include_robots=args.include_robots,
            same_origin_only=args.same_origin_only,
        )
        resources = list(
            provider.discover(DiscoveryRequest(root_uri=args.root_uri, limit=args.limit))
        )
        _emit_json(_manifest(provider.name, resources), args.output)
    except (FetchError, OSError, ValueError) as error:
        print(f"source discovery failed: {error}", file=sys.stderr)
        return 1
    return 0


def _infer_fetcher(uri: str) -> str:
    try:
        scheme = urlsplit(uri).scheme.lower()
    except ValueError:
        raise ValueError("cannot infer a fetcher from an invalid URI") from None
    if scheme in {"http", "https"}:
        return "http"
    if scheme in {"", "file"}:
        return "local-file"
    raise ValueError(f"cannot infer a fetcher for URI scheme: {scheme}")


def _atomic_write(destination: Path, content: bytes, *, overwrite: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {destination}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)


def _run_fetch(args: argparse.Namespace) -> int:
    destination = Path(args.output)
    if destination.exists() and not args.overwrite:
        print(f"source fetch failed: output already exists: {destination}", file=sys.stderr)
        return 1

    try:
        fetcher_name = _infer_fetcher(args.uri) if args.fetcher == "auto" else args.fetcher
        options: dict[str, object] = {"max_bytes": args.max_bytes}
        if fetcher_name == "http":
            options["timeout_seconds"] = args.timeout
        else:
            options["root"] = args.root
        fetcher = create_fetcher(fetcher_name, **options)
        artifact = fetcher.fetch(ResourceRef(args.uri, source="cli"))
        _atomic_write(destination, artifact.content, overwrite=args.overwrite)
        receipt = {
            "schema_version": 1,
            "fetcher": fetcher.name,
            "resource": artifact.resource.uri,
            "output": str(destination),
            "media_type": artifact.media_type,
            "filename": artifact.filename,
            "bytes": len(artifact.content),
            "metadata": dict(artifact.metadata),
        }
        _emit_json(receipt)
    except (FetchError, OSError, ValueError) as error:
        print(f"source fetch failed: {error}", file=sys.stderr)
        return 1
    return 0


def _run_process(args: argparse.Namespace) -> int:
    from doc_harvester.manifest_processing import (
        ManifestValidationError,
        process_manifest,
    )

    try:
        report = process_manifest(
            args.manifest,
            args.output,
            root=args.root,
            limit=args.limit,
            max_manifest_bytes=args.max_manifest_bytes,
            max_fetch_bytes=args.max_bytes,
            timeout_seconds=args.timeout,
            max_tokens=args.max_tokens,
            max_pdf_pages=args.max_pdf_pages,
        )
    except (ManifestValidationError, FetchError, OSError, ValueError) as error:
        print(f"source processing failed: {error}", file=sys.stderr)
        return 1
    summary = {
        key: report[key]
        for key in (
            "schema_version",
            "status",
            "selected_count",
            "processed_count",
            "skipped_count",
            "failed_count",
        )
    }
    summary["output"] = str(Path(args.output))
    _emit_json(summary)
    return 1 if report["failed_count"] or report["processed_count"] == 0 else 0
