#!/usr/bin/env python3
"""Standalone BFS discovery of product URLs in a web catalogue.

Crawls a root URL, collects all product page URLs, and saves them
incrementally to a JSON file in discovery/. Output is directly
compatible with `src/scraper.py --resume-from`.

Usage:
    python scripts/discover_catalogue.py https://cable.ru/cable/
    python scripts/discover_catalogue.py https://cable.ru/cable/ --max-pages 5000
    python scripts/discover_catalogue.py https://cable.ru/cable/kabel-importnyj.php
"""
import argparse
import os
import re
import signal
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

# Avoid yandex.py RuntimeError on import (discovery doesn't need Yandex Disk)
os.environ.setdefault("YANDEX_DISK_TOKEN", "__discovery_mode__")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bs4 import BeautifulSoup
from doc_harvester.security import sanitize_url_for_logging
from scraper import (
    WEB_CRAWL_DELAY_SEC,
    _fetch_page_html,
    _is_file_link,
    _is_product_url,
    _is_same_domain,
    _is_under_root_path,
    _normalize_http_url,
    get_domain_name,
    load_json,
    save_json,
)

DISCOVERY_DIR = os.path.join(os.path.dirname(__file__), "..", "discovery")

_interrupted = False


def _handle_signal(signum, frame):
    global _interrupted
    _interrupted = True
    print("\nInterrupt received, saving progress...")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _discovery_filename(root_url: str) -> str:
    parsed = urlparse(root_url)
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/")
    if path:
        slug = re.sub(r"[^\w\-]", "_", path).strip("_")
        return f"{domain}__{slug}.json"
    return f"{domain}.json"


def _is_likely_listing(url: str, parent_child_count: int) -> bool:
    """Heuristic: should we visit this URL to find child links?

    Returns True for pages that are likely category/listing pages
    (containing links to other product pages). Returns False for
    pages that are likely leaf product pages (no useful child links).

    The heuristic looks at the URL structure. Pages that link to many
    children are worth visiting; final product pages are not.
    """
    path = urlparse(url).path.lower()
    fname = path.rstrip("/").rsplit("/", 1)[-1]

    # Paginated pages (?page=N) are always listings
    if "page=" in url:
        return True

    # Directory-style URLs (ending with /) are usually listings
    if path.endswith("/"):
        return True

    # Pages without file extension are usually listings
    if "." not in fname:
        return True

    # URLs with very long filenames (>60 chars) are usually specific products
    name_part = fname.rsplit(".", 1)[0] if "." in fname else fname
    if len(name_part) > 60:
        return False

    # Count underscores + digits as specificity indicator.
    # Product pages have detailed specs encoded: cable-vvgng_a_ls_5h2_5_1.php
    # Category pages are simpler: kabel-silovoj.php, group-avvg.php
    underscore_count = name_part.count("_")
    digit_groups = len(re.findall(r"\d+", name_part))

    # High specificity = likely a leaf product page
    if underscore_count >= 3 and digit_groups >= 2:
        return False

    return True


def _save_discovery(path, root_url, domain, started_at,
                    visited, queue, product_urls, enqueued, status,
                    skipped_leaves=0):
    data = {
        "root_url": root_url,
        "domain": domain,
        "started_at": started_at,
        "updated_at": datetime.utcnow().isoformat(),
        "status": status,
        "pages_visited": len(visited),
        "pages_queued": len(queue),
        "skipped_leaves": skipped_leaves,
        "discovered_urls": sorted(product_urls),
        "bfs_state": {
            "visited": sorted(visited),
            "queue": list(queue),
        },
    }
    save_json(path, data)


def discover_catalogue(root_url, output_path, max_pages=50000,
                       resume_state=None, skip_leaves=True):
    if resume_state:
        visited = set(resume_state.get("visited", []))
        to_visit = list(resume_state.get("queue", []))
        all_product_urls = set(resume_state.get("discovered_urls", []))
        enqueued = visited | set(to_visit)
        started_at = resume_state.get("started_at", datetime.utcnow().isoformat())
        skipped_leaves = resume_state.get("skipped_leaves", 0)
        print(f"Resuming: {len(visited)} visited, {len(to_visit)} queued, "
              f"{len(all_product_urls)} discovered")
    else:
        visited = set()
        to_visit = [root_url]
        all_product_urls = set()
        enqueued = {root_url}
        started_at = datetime.utcnow().isoformat()
        skipped_leaves = 0

    domain = get_domain_name(root_url)
    pages_since_save = 0
    SAVE_EVERY = 5

    while to_visit and len(visited) < max_pages and not _interrupted:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)

        # Skip non-product URLs but still mark visited
        if current != root_url and not _is_product_url(current):
            pages_since_save += 1
            if pages_since_save >= SAVE_EVERY:
                _save_discovery(output_path, root_url, domain, started_at,
                                visited, to_visit, all_product_urls, enqueued,
                                "in_progress", skipped_leaves)
                pages_since_save = 0
            continue

        html = _fetch_page_html(current)
        if html is None:
            pages_since_save += 1
            if pages_since_save >= SAVE_EVERY:
                _save_discovery(output_path, root_url, domain, started_at,
                                visited, to_visit, all_product_urls, enqueued,
                                "in_progress", skipped_leaves)
                pages_since_save = 0
            continue

        if current != root_url and _is_product_url(current):
            all_product_urls.add(current)

        soup = BeautifulSoup(html, "html.parser")
        new_links = 0
        new_leaves = 0
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = _normalize_http_url(current, href)
            if not absolute_url.startswith(("http://", "https://")):
                continue
            if not _is_same_domain(root_url, absolute_url):
                continue
            if _is_file_link(absolute_url):
                continue
            if not _is_product_url(absolute_url):
                continue
            if not _is_under_root_path(root_url, absolute_url):
                continue
            all_product_urls.add(absolute_url)
            if absolute_url not in enqueued:
                # Only queue pages likely to contain child links
                if skip_leaves and not _is_likely_listing(absolute_url, 0):
                    new_leaves += 1
                    skipped_leaves += 1
                else:
                    to_visit.append(absolute_url)
                    new_links += 1
                enqueued.add(absolute_url)

        pages_since_save += 1
        leaf_info = f" leaves={new_leaves}" if new_leaves else ""
        print(f"  [{len(visited):>5}/{max_pages}] queued={len(to_visit)} "
              f"found={len(all_product_urls)} new={new_links}{leaf_info}"
              f" <- {sanitize_url_for_logging(current)}")

        if pages_since_save >= SAVE_EVERY:
            _save_discovery(output_path, root_url, domain, started_at,
                            visited, to_visit, all_product_urls, enqueued,
                            "in_progress", skipped_leaves)
            pages_since_save = 0

        time.sleep(WEB_CRAWL_DELAY_SEC)

    if _interrupted:
        status = "interrupted"
    elif not to_visit:
        status = "completed"
    else:
        status = "max_pages_reached"

    _save_discovery(output_path, root_url, domain, started_at,
                    visited, to_visit, all_product_urls, enqueued, status,
                    skipped_leaves)

    return {
        "status": status,
        "pages_visited": len(visited),
        "urls_found": len(all_product_urls),
        "skipped_leaves": skipped_leaves,
        "output": output_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Discover all product URLs in a catalogue via BFS crawl"
    )
    parser.add_argument("url", help="Root catalogue URL to crawl")
    parser.add_argument("--max-pages", type=int, default=50000,
                        help="Max pages to visit (default: 50000)")
    parser.add_argument("--resume", metavar="FILE",
                        help="Resume from a previous discovery file")
    parser.add_argument("--output", metavar="FILE",
                        help="Output file path (default: auto in discovery/)")
    parser.add_argument("--no-skip-leaves", action="store_true",
                        help="Disable leaf-skipping optimization (visit all URLs)")
    args = parser.parse_args()

    output_path = args.output or os.path.join(
        os.path.abspath(DISCOVERY_DIR), _discovery_filename(args.url)
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Determine resume state
    resume_state = None
    resume_file = args.resume or output_path
    if os.path.exists(resume_file):
        existing = load_json(resume_file, {})
        if existing.get("status") != "completed":
            resume_state = {
                "visited": existing.get("bfs_state", {}).get("visited", []),
                "queue": existing.get("bfs_state", {}).get("queue", []),
                "discovered_urls": existing.get("discovered_urls", []),
                "started_at": existing.get("started_at"),
                "skipped_leaves": existing.get("skipped_leaves", 0),
            }
            print(f"Auto-resuming from {resume_file}")
        elif args.resume:
            print(f"WARNING: {resume_file} status is '{existing.get('status')}'. "
                  "Delete it or use --output to start fresh.")
            sys.exit(1)
        else:
            urls = existing.get("discovered_urls", [])
            print(f"Discovery already {existing.get('status')}: {output_path}")
            print(f"  {len(urls)} URLs found. Delete file to re-discover.")
            sys.exit(0)

    skip_leaves = not args.no_skip_leaves
    mode = "skip-leaves" if skip_leaves else "visit-all"
    print(f"Discovering: {sanitize_url_for_logging(args.url)}")
    print(f"Output: {output_path}")
    print(f"Max pages: {args.max_pages}, delay: {WEB_CRAWL_DELAY_SEC}s, mode: {mode}")
    print()

    result = discover_catalogue(
        args.url, output_path,
        max_pages=args.max_pages,
        resume_state=resume_state,
        skip_leaves=skip_leaves,
    )

    print(f"\nDone: {result['status']}")
    print(f"  Pages visited: {result['pages_visited']}")
    print(f"  Product URLs found: {result['urls_found']}")
    print(f"  Leaf pages skipped: {result['skipped_leaves']}")
    print(f"  Output: {result['output']}")


if __name__ == "__main__":
    main()
