"""Command-line entrypoint for the standalone scraper."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from doc_harvester import __version__
from doc_harvester.demo import write_demo_result


def _disk_folder(url: str) -> str:
    domain = urlparse(url).netloc.removeprefix("www.").replace(":", "_")
    return f"/datasets/specs/{domain}/{date.today().isoformat()}"


def _run_crawl(args: argparse.Namespace) -> int:
    import scraper

    scraper.UPLOAD_ENABLED = not args.no_upload
    scraper.BFS_ENABLED = not args.no_bfs
    if args.min_score is not None:
        scraper.WEB_MIN_PRODUCT_SCORE = args.min_score
    scraper.ingest_web(
        args.url,
        _disk_folder(args.url),
        batch_size=args.batch_size,
        spa_mode=args.spa,
    )
    return 0


def _run_files(args: argparse.Namespace) -> int:
    import scraper

    scraper.ingest_page(args.url, _disk_folder(args.url))
    return 0


def _run_upload(args: argparse.Namespace) -> int:
    import scraper

    result = scraper.batch_upload_to_yandex(args.path, disk_base=args.disk_base)
    return 0 if result.get("failed", 0) == 0 else 1


def _run_discover(args: argparse.Namespace) -> int:
    from yandex_search import discover_via_search

    urls = discover_via_search(
        args.domain,
        search_terms=args.term or None,
        max_queries=args.max_queries,
        pages_per_term=args.pages_per_term,
    )
    payload = {"domain": args.domain, "urls": urls, "count": len(urls)}
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _run_api(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError as error:
        raise SystemExit("Install API dependencies with: pip install 'doc-harvester[api]'") from error
    uvicorn.run("api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _run_demo(args: argparse.Namespace) -> int:
    output = Path(args.output)
    result = write_demo_result(output)
    print(f"Demo wrote {len(result['chunks'])} chunks to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-harvester",
        description="Build RAG-ready datasets from technical documents and websites.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    discover = commands.add_parser("discover", help="Discover domain URLs with Yandex Search API")
    discover.add_argument("domain", help="Domain to search, for example example.com")
    discover.add_argument("--term", action="append", help="Search term; repeat for multiple terms")
    discover.add_argument("--max-queries", type=int, default=20)
    discover.add_argument("--pages-per-term", type=int, default=2)
    discover.add_argument("--output", help="Write discovery JSON to this path")
    discover.set_defaults(handler=_run_discover)

    crawl = commands.add_parser("crawl", help="Crawl and process technical web pages")
    crawl.add_argument("url")
    crawl.add_argument("--batch-size", type=int, default=0)
    crawl.add_argument("--spa", action="store_true", help="Render JavaScript-heavy pages")
    crawl.add_argument("--no-bfs", action="store_true")
    crawl.add_argument("--no-upload", action="store_true", help="Keep output local")
    crawl.add_argument("--min-score", type=int)
    crawl.set_defaults(handler=_run_crawl)

    files = commands.add_parser("files", help="Find and process linked documents")
    files.add_argument("url")
    files.set_defaults(handler=_run_files)

    upload = commands.add_parser("upload", help="Upload an existing local dataset")
    upload.add_argument("path")
    upload.add_argument("--disk-base", default="/datasets/specs")
    upload.set_defaults(handler=_run_upload)

    api = commands.add_parser("api", help="Run the optional HTTP API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--reload", action="store_true")
    api.set_defaults(handler=_run_api)

    demo = commands.add_parser("demo", help="Run an offline extraction and chunking demo")
    demo.add_argument("--output", default="demo-output/chunks.json")
    demo.set_defaults(handler=_run_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and dispatch the selected command."""
    os.environ.setdefault("PYTHONUTF8", "1")
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
