#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from dotenv import load_dotenv

from doc_harvester.publishers import YandexWikiPublisher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
WIKI_OUT_DIR = os.path.join(ROOT, "wiki", "out")
DEFAULT_MAP_PATH = os.path.join(ROOT, "config", "wiki_publish_map.json")
DEFAULT_REPORT_DIR = os.path.join(ROOT, "runs")
SNAPSHOT_ROOT = os.path.join(ROOT, "runs", "wiki_snapshots")
PUBLISH_HASHES_PATH = os.path.join(ROOT, "runs", "wiki_publish_hashes.json")


def _load_publish_hashes() -> Dict[str, str]:
    if os.path.exists(PUBLISH_HASHES_PATH):
        with open(PUBLISH_HASHES_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_publish_hashes(hashes: Dict[str, str]):
    with open(PUBLISH_HASHES_PATH, "w") as f:
        json.dump(hashes, f, indent=2)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: str, payload: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def publish_pages(
    client: YandexWikiPublisher,
    page_map: List[Dict],
    dry_run: bool = True,
    create_missing: bool = False,
) -> Dict:
    results: List[Dict] = []
    stats = {
        "published": 0,
        "updated": 0,
        "created": 0,
        "skipped": 0,
        "unchanged": 0,
        "failed": 0,
    }
    prev_hashes = _load_publish_hashes()
    new_hashes = dict(prev_hashes)

    for item in page_map:
        source = item.get("source", "").strip()
        slug = _normalize_slug(item.get("slug", ""))
        title = item.get("title", "").strip() or source
        source_path = os.path.join(WIKI_OUT_DIR, source)

        if not source:
            stats["skipped"] += 1
            results.append({"source": source, "status": "skipped", "reason": "empty source"})
            continue
        if not slug:
            stats["skipped"] += 1
            results.append({"source": source, "status": "skipped", "reason": "empty slug"})
            continue
        if not os.path.exists(source_path):
            stats["failed"] += 1
            results.append({"source": source, "slug": slug, "status": "failed", "reason": "source file not found"})
            continue

        with open(source_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Skip if content unchanged since last publish (avoids unnecessary API calls)
        content_h = _content_hash(content)
        if not dry_run and prev_hashes.get(slug) == content_h:
            stats["unchanged"] += 1
            results.append({"source": source, "slug": slug, "status": "unchanged"})
            continue

        try:
            page = client.get_page_by_slug(slug)
            page_id = str(page.get("id")) if page else None

            if dry_run:
                if page_id:
                    action = "would_update"
                elif create_missing:
                    action = "would_create"
                else:
                    action = "missing_skip"
                results.append(
                    {
                        "source": source,
                        "slug": slug,
                        "title": title,
                        "status": action,
                        "exists": bool(page_id),
                    }
                )
                stats["skipped"] += 1
                continue

            if page_id:
                client.update_page(page_id=page_id, title=title, content=content)
                new_hashes[slug] = content_h
                stats["published"] += 1
                stats["updated"] += 1
                results.append({"source": source, "slug": slug, "title": title, "status": "updated", "page_id": page_id})
            elif create_missing:
                created = client.create_page(slug=slug, title=title, content=content)
                created_id = created.get("id")
                new_hashes[slug] = content_h
                stats["published"] += 1
                stats["created"] += 1
                results.append({"source": source, "slug": slug, "title": title, "status": "created", "page_id": created_id})
            else:
                stats["skipped"] += 1
                results.append({"source": source, "slug": slug, "title": title, "status": "skipped_missing"})
        except Exception as error:
            stats["failed"] += 1
            results.append({"source": source, "slug": slug, "title": title, "status": "failed", "error": str(error)})

    if not dry_run:
        _save_publish_hashes(new_hashes)
    return {"stats": stats, "results": results}


def _normalize_slug(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""

    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        path = (parsed.path or "").strip("/")
        return path

    return value.strip("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish generated wiki markdown pages to Yandex Wiki")
    parser.add_argument("--map", default=DEFAULT_MAP_PATH, help="Path to wiki page map json")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--create-missing", action="store_true", help="Create missing pages")
    parser.add_argument("--report", default="", help="Optional report path")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("YANDEX_WIKI_API_BASE", "https://api.wiki.yandex.net"),
        help="Yandex Wiki API base URL",
    )
    parser.add_argument("--org-id", default=os.environ.get("YANDEX_WIKI_CLOUD_ORG_ID", ""))
    parser.add_argument("--token", default=os.environ.get("YANDEX_WIKI_TOKEN", ""))
    args = parser.parse_args()

    if not args.org_id:
        raise RuntimeError("YANDEX_WIKI_CLOUD_ORG_ID is not set")
    if not args.token:
        raise RuntimeError("YANDEX_WIKI_TOKEN is not set")

    page_map_payload = _load_json(args.map)
    pages = page_map_payload.get("pages", [])
    if not pages:
        raise RuntimeError(f"No pages in map: {args.map}")

    client = YandexWikiPublisher(token=args.token, cloud_org_id=args.org_id, base_url=args.base_url)
    publish_result = publish_pages(
        client=client,
        page_map=pages,
        dry_run=not args.apply,
        create_missing=args.create_missing,
    )

    mode = "apply" if args.apply else "dry_run"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = args.report or os.path.join(DEFAULT_REPORT_DIR, f"wiki_publish_{mode}_{timestamp}.json")
    snapshot_dir = ""
    if args.apply:
        snapshot_dir = os.path.join(SNAPSHOT_ROOT, timestamp)
        os.makedirs(SNAPSHOT_ROOT, exist_ok=True)
        shutil.copytree(WIKI_OUT_DIR, snapshot_dir, dirs_exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "map_path": args.map,
        "base_url": args.base_url,
        "org_id": args.org_id,
        "create_missing": args.create_missing,
        "local_snapshot": snapshot_dir,
        "result": publish_result,
    }
    _write_json(report_path, payload)

    stats = publish_result["stats"]
    print(f"Wiki publish report: {report_path}")
    print(
        "published={published} updated={updated} created={created} unchanged={unchanged} skipped={skipped} failed={failed}".format(
            published=stats["published"],
            updated=stats["updated"],
            created=stats["created"],
            unchanged=stats.get("unchanged", 0),
            skipped=stats["skipped"],
            failed=stats["failed"],
        )
    )
    if snapshot_dir:
        print(f"Local snapshot: {snapshot_dir}")


if __name__ == "__main__":
    main()
