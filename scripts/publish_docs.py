#!/usr/bin/env python3
"""Batch-publish generated Markdown through any configured publisher.

The historical filename remains for compatibility with existing automation.
"""

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from doc_harvester.publishers import PublishRequest, Publisher, create_publisher

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
WIKI_OUT_DIR = ROOT / "wiki" / "out"
DEFAULT_MAP_PATH = ROOT / "config" / "wiki_publish_map.json"
DEFAULT_REPORT_DIR = ROOT / "runs"
SNAPSHOT_ROOT = ROOT / "runs" / "wiki_snapshots"
PUBLISH_HASHES_PATH = ROOT / "runs" / "wiki_publish_hashes.json"


def _load_publish_hashes() -> dict[str, str]:
    if PUBLISH_HASHES_PATH.exists():
        return json.loads(PUBLISH_HASHES_PATH.read_text(encoding="utf-8"))
    return {}


def _save_publish_hashes(hashes: dict[str, str]) -> None:
    PUBLISH_HASHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISH_HASHES_PATH.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_legacy_slug(raw: str) -> str:
    value = (raw or "").strip()
    if value.startswith(("http://", "https://")):
        return urlparse(value).path.strip("/")
    return value.strip("/")


def _destination(item: dict[str, Any]) -> str:
    destination = str(item.get("destination", "")).strip()
    return destination or _normalize_legacy_slug(str(item.get("slug", "")))


def _source_path(source: str) -> Path:
    candidate = Path(source)
    if candidate.is_absolute():
        return candidate
    root_relative = ROOT / candidate
    return root_relative if root_relative.exists() else WIKI_OUT_DIR / candidate


def publish_pages(
    client: Publisher,
    page_map: list[dict[str, Any]],
    dry_run: bool = True,
    create_missing: bool = False,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    stats = {"published": 0, "updated": 0, "created": 0, "skipped": 0, "unchanged": 0, "failed": 0}
    previous_hashes = _load_publish_hashes()
    new_hashes = dict(previous_hashes)

    for item in page_map:
        source = str(item.get("source", "")).strip()
        destination = _destination(item)
        title = str(item.get("title", "")).strip()
        source_path = _source_path(source)
        base_result = {"source": source, "destination": destination, "title": title}

        if not source or not destination:
            stats["skipped"] += 1
            reason = "empty source" if not source else "empty destination"
            results.append({**base_result, "status": "skipped", "reason": reason})
            continue
        if not source_path.is_file():
            stats["failed"] += 1
            results.append({**base_result, "status": "failed", "reason": "source file not found"})
            continue

        content_hash = _content_hash(source_path.read_text(encoding="utf-8"))
        hash_key = f"{client.name}:{destination}"
        if not dry_run and previous_hashes.get(hash_key) == content_hash:
            stats["unchanged"] += 1
            results.append({**base_result, "status": "unchanged"})
            continue

        try:
            result = client.publish(
                PublishRequest(source_path, destination, title),
                dry_run=dry_run,
                create_missing=create_missing,
            )
            results.append({**base_result, **result.to_dict()})
            if result.status in {"published", "updated", "created"}:
                stats["published"] += 1
                if result.status in {"updated", "created"}:
                    stats[result.status] += 1
                new_hashes[hash_key] = content_hash
            else:
                stats["skipped"] += 1
        except Exception as error:
            stats["failed"] += 1
            results.append({**base_result, "status": "failed", "error": str(error)})

    if not dry_run:
        _save_publish_hashes(new_hashes)
    return {"stats": stats, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish generated Markdown documentation")
    parser.add_argument("--map", default=str(DEFAULT_MAP_PATH), help="Path to page map JSON")
    parser.add_argument(
        "--publisher",
        default=os.environ.get("DOC_HARVESTER_PUBLISHER", "yandex-wiki"),
        help="Publisher name (built-in or installed plugin)",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--create-missing", action="store_true", help="Create missing pages")
    parser.add_argument("--report", default="", help="Optional report path")
    args = parser.parse_args()

    page_map_payload = _load_json(args.map)
    pages = page_map_payload.get("pages", [])
    if not pages:
        raise RuntimeError(f"No pages in map: {args.map}")
    publisher_name = page_map_payload.get("publisher") or args.publisher
    client = create_publisher(publisher_name)
    publish_result = publish_pages(
        client=client,
        page_map=pages,
        dry_run=not args.apply,
        create_missing=args.create_missing,
    )

    mode = "apply" if args.apply else "dry_run"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = args.report or DEFAULT_REPORT_DIR / f"publish_{mode}_{timestamp}.json"
    snapshot_dir = ""
    if args.apply:
        snapshot = SNAPSHOT_ROOT / timestamp
        SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(WIKI_OUT_DIR, snapshot, dirs_exist_ok=True)
        snapshot_dir = str(snapshot)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "publisher": client.name,
        "map_path": args.map,
        "create_missing": args.create_missing,
        "local_snapshot": snapshot_dir,
        "result": publish_result,
    }
    _write_json(report_path, payload)
    stats = publish_result["stats"]
    print(f"Publish report: {report_path}")
    print(" ".join(f"{key}={value}" for key, value in stats.items()))


if __name__ == "__main__":
    main()
