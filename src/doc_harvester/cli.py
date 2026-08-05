"""Command-line entrypoint for the standalone scraper."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from doc_harvester import __version__
from doc_harvester.demo import write_demo_result


def _disk_folder(url: str) -> str:
    domain = urlparse(url).netloc.removeprefix("www.").replace(":", "_")
    return f"/datasets/specs/{domain}/{date.today().isoformat()}"


def _configure_profile(scraper, name: str) -> None:
    from doc_harvester.profiles import load_profile

    scraper.configure_profile(load_profile(name))


def _run_crawl(args: argparse.Namespace) -> int:
    if args.spa:
        try:
            import playwright  # noqa: F401
        except ImportError:
            print(
                "crawl failed: SPA mode requires: pip install 'doc-harvester[browser]'",
                file=sys.stderr,
            )
            return 1
    import scraper

    _configure_profile(scraper, args.profile)
    scraper.UPLOAD_ENABLED = not args.no_upload
    scraper.STORAGE_PROVIDER = args.storage
    if args.local_root:
        os.environ["DOC_HARVESTER_LOCAL_STORAGE_ROOT"] = args.local_root
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

    _configure_profile(scraper, args.profile)
    scraper.UPLOAD_ENABLED = not args.no_upload
    scraper.STORAGE_PROVIDER = args.storage
    if args.local_root:
        os.environ["DOC_HARVESTER_LOCAL_STORAGE_ROOT"] = args.local_root
    scraper.ingest_page(args.url, _disk_folder(args.url))
    return 0


def _run_upload(args: argparse.Namespace) -> int:
    import scraper

    from doc_harvester.storage import create_storage

    source = Path(args.path)
    if not source.exists():
        source = Path(scraper.LOCAL_DATASET_ROOT) / args.path
    if not source.exists():
        raise FileNotFoundError(f"dataset not found: {args.path}")
    path_label = source.name if Path(args.path).is_absolute() else args.path.strip("/")
    destination = args.destination or "/".join(
        part
        for part in (args.disk_base.strip("/"), path_label, date.today().isoformat())
        if part
    )
    if source.is_file() and not args.destination:
        destination = f"{destination}/{source.name}"
    storage = create_storage(args.storage, root=args.local_root)
    if source.is_file():
        storage.put_file(source, destination, overwrite=args.overwrite)
        result = {
            "provider": storage.name,
            "destination": destination,
            "files_uploaded": 1,
            "bytes_uploaded": source.stat().st_size,
        }
    else:
        result = storage.upload_tree(source, destination, overwrite=args.overwrite).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _run_discover(args: argparse.Namespace) -> int:
    from yandex_search import discover_via_search

    search_terms = args.term
    if not search_terms and args.profile:
        from doc_harvester.profiles import load_profile

        search_terms = list(load_profile(args.profile).priority_terms)

    urls = discover_via_search(
        args.domain,
        search_terms=search_terms or None,
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


def _run_profile_list(args: argparse.Namespace) -> int:
    from doc_harvester.profiles import list_profiles

    profiles = list_profiles(args.directory)
    print(json.dumps({"profiles": profiles, "count": len(profiles)}, indent=2))
    return 0


def _run_profile_validate(args: argparse.Namespace) -> int:
    from doc_harvester.profiles import load_profile

    profile = load_profile(args.profile, profiles_dir=args.directory)
    print(json.dumps({"name": profile.name, "valid": True, "profile": profile.to_dict()}, ensure_ascii=False, indent=2))
    return 0


def _run_publish(args: argparse.Namespace) -> int:
    from doc_harvester.publishers import PublishRequest, create_publisher

    overrides = {"root": args.local_root} if args.local_root else {}
    publisher = create_publisher(args.publisher, **overrides)
    request = PublishRequest(Path(args.source), args.destination, args.title)
    result = publisher.publish(request, dry_run=True, create_missing=args.create_missing)
    if args.apply:
        if result.status == "would_update" and not args.update_existing:
            print(
                "publication failed: destination exists; use --update-existing intentionally",
                file=sys.stderr,
            )
            return 1
        if result.status != "missing" or args.create_missing:
            result = publisher.publish(
                request,
                dry_run=False,
                create_missing=args.create_missing,
            )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status not in {"failed", "missing"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-harvester",
        description="Build RAG-ready datasets from technical documents and websites.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    from doc_harvester.source_cli import add_source_commands

    add_source_commands(commands)

    discover = commands.add_parser("discover", help="Discover domain URLs with Yandex Search API")
    discover.add_argument("domain", help="Domain to search, for example example.com")
    discover.add_argument("--term", action="append", help="Search term; repeat for multiple terms")
    discover.add_argument("--profile", help="Use priority terms from a validated profile")
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
    crawl.add_argument(
        "--storage",
        choices=("local", "yandex", "s3"),
        default=os.environ.get("DOC_HARVESTER_STORAGE", "local"),
    )
    crawl.add_argument("--local-root", help="Override local storage root")
    crawl.add_argument("--min-score", type=int)
    crawl.add_argument(
        "--profile", default=os.environ.get("DOC_HARVESTER_PROFILE", "electrical")
    )
    crawl.set_defaults(handler=_run_crawl)

    files = commands.add_parser("files", help="Find and process linked documents")
    files.add_argument("url")
    files.add_argument("--no-upload", action="store_true", help="Keep output only in datasets/")
    files.add_argument(
        "--storage",
        choices=("local", "yandex", "s3"),
        default=os.environ.get("DOC_HARVESTER_STORAGE", "local"),
    )
    files.add_argument("--local-root", help="Override local storage root")
    files.add_argument(
        "--profile", default=os.environ.get("DOC_HARVESTER_PROFILE", "electrical")
    )
    files.set_defaults(handler=_run_files)

    upload = commands.add_parser("upload", help="Store an existing local dataset")
    upload.add_argument("path")
    upload.add_argument(
        "--storage",
        choices=("local", "yandex", "s3"),
        default=os.environ.get("DOC_HARVESTER_STORAGE", "local"),
    )
    upload.add_argument("--destination", help="Provider-relative destination")
    upload.add_argument("--disk-base", default="/datasets/specs")
    upload.add_argument("--local-root", help="Override local storage root")
    upload.add_argument("--no-overwrite", dest="overwrite", action="store_false")
    upload.set_defaults(overwrite=True)
    upload.set_defaults(handler=_run_upload)

    publish = commands.add_parser("publish", help="Publish a generated text artifact")
    publish.add_argument("source")
    publish.add_argument("destination")
    publish.add_argument(
        "--publisher",
        default=os.environ.get("DOC_HARVESTER_PUBLISHER", "local"),
        help="Publisher name (built-in or installed plugin)",
    )
    publish.add_argument("--title", default="")
    publish.add_argument("--local-root", help="Override local publisher root")
    publish.add_argument("--apply", action="store_true", help="Apply instead of dry-run")
    publish.add_argument(
        "--update-existing",
        action="store_true",
        help="Allow --apply to replace or update an existing destination",
    )
    publish.add_argument("--create-missing", action="store_true")
    publish.set_defaults(handler=_run_publish)

    profile = commands.add_parser("profile", help="List or validate discovery profiles")
    profile_commands = profile.add_subparsers(dest="profile_command", required=True)
    profile_list = profile_commands.add_parser("list")
    profile_list.add_argument("--directory", default="config/profiles")
    profile_list.set_defaults(handler=_run_profile_list)
    profile_validate = profile_commands.add_parser("validate")
    profile_validate.add_argument("profile", help="Profile name or JSON path")
    profile_validate.add_argument("--directory", default="config/profiles")
    profile_validate.set_defaults(handler=_run_profile_validate)

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
