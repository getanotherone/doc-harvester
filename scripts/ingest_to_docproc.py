#!/usr/bin/env python3
"""Ingest raw files into DocProc microservice.

Reads files from local datasets directory or Yandex Disk,
uploads them to DocProc for parsing, chunking, and embedding,
then exports enriched chunks back to Yandex Disk.

Usage:
    # Ingest local files → process → upload chunks to Yandex Disk
    python scripts/ingest_to_docproc.py --source pulsal.ru --wait

    # Ingest from Yandex Disk → process → upload chunks back
    python scripts/ingest_to_docproc.py --source realelectro.com --from-disk --wait

    # Process only, don't upload results to disk (keep in DocProc DB)
    python scripts/ingest_to_docproc.py --source pulsal.ru --wait --no-export

    # Dry run (list files without uploading)
    python scripts/ingest_to_docproc.py --source pulsal.ru --dry-run

    # Limit number of files
    python scripts/ingest_to_docproc.py --source pulsal.ru --limit 10

    # Monitor all running tasks
    python scripts/ingest_to_docproc.py --status

    # Export already-processed documents to Yandex Disk
    python scripts/ingest_to_docproc.py --export-doc <document_id> --source pulsal.ru
"""

import argparse
import io
import json
import math
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
load_dotenv()

import httpx

# DocProc API settings
DOCPROC_URL = os.environ.get("DOCPROC_URL", "http://localhost:8001")
DOCPROC_API = f"{DOCPROC_URL}/api/v1"

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".pptx"}

# Local datasets path
DATASETS_DIR = str(PROJECT_ROOT / "datasets" / "electrical")

# Poll interval for status checks (seconds)
POLL_INTERVAL = 5

# PDFs larger than this get split into parts before upload
SPLIT_THRESHOLD_MB = 20
SPLIT_PAGES = 50  # pages per part


def split_large_pdf(filepath: str, filename: str, pages_per_part: int = SPLIT_PAGES) -> list[dict]:
    """Split a large PDF into smaller parts. Returns list of temp file dicts."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print("    pypdf not installed, uploading whole file (may be slow)")
        return []

    reader = PdfReader(filepath)
    total_pages = len(reader.pages)
    if total_pages <= pages_per_part:
        return []  # No need to split

    stem, ext = os.path.splitext(filename)
    num_parts = math.ceil(total_pages / pages_per_part)
    print(f"    Splitting {total_pages} pages into {num_parts} parts ({pages_per_part} pages each)")

    parts = []
    for i in range(num_parts):
        start = i * pages_per_part
        end = min(start + pages_per_part, total_pages)
        part_name = f"{stem}_part{i + 1:03d}of{num_parts:03d}{ext}"

        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        writer.write(tmp)
        tmp.close()
        size_mb = os.path.getsize(tmp.name) / (1024 * 1024)
        parts.append({"name": part_name, "path": tmp.name, "size_mb": round(size_mb, 1), "temp": True})

    return parts


def get_local_files(source: str = "", local_dir: str = "") -> list[dict]:
    """List files from local datasets directory."""
    if local_dir:
        base_dir = local_dir
    elif source:
        base_dir = os.path.join(DATASETS_DIR, source, "files")
    else:
        raise ValueError("Provide --source or --local-dir")

    if not os.path.isdir(base_dir):
        print(f"Directory not found: {base_dir}")
        sys.exit(1)

    files = []
    for name in sorted(os.listdir(base_dir)):
        if name.startswith("_") or name.startswith("."):
            continue
        _, ext = os.path.splitext(name.lower())
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        path = os.path.join(base_dir, name)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            files.append({"name": name, "path": path, "size_mb": round(size_mb, 1)})

    return files


def get_yandex_disk_files(source: str) -> list[dict]:
    """List files from Yandex Disk for a source (recurses into date subdirs)."""
    _init_yandex()

    from yandex import list_all

    disk_path = f"/datasets/specs/{source}"
    print(f"Listing files on Yandex Disk: {disk_path}")

    top_items = list_all(disk_path)
    files = []

    # Collect files at top level + recurse into subdirectories (date folders)
    for item in top_items:
        if item.get("type") == "file":
            _maybe_add_disk_file(item, files)
        elif item.get("type") == "dir":
            subpath = item.get("path", "").replace("disk:", "")
            for subitem in list_all(subpath):
                if subitem.get("type") == "file":
                    _maybe_add_disk_file(subitem, files)

    print(f"  Found {len(files)} supported files")
    return files


def _maybe_add_disk_file(item: dict, files: list[dict]) -> None:
    """Add a Yandex Disk file item if it has a supported extension."""
    name = item.get("name", "")
    _, ext = os.path.splitext(name.lower())
    if ext not in SUPPORTED_EXTENSIONS:
        return
    path = item.get("path", "").replace("disk:", "")
    size_mb = item.get("size", 0) / (1024 * 1024)
    files.append({"name": name, "path": path, "size_mb": round(size_mb, 1)})


def download_from_yandex(disk_path: str) -> str:
    """Download a file from Yandex Disk to a temp file. Returns local path."""
    src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from yandex import download_file

    _, ext = os.path.splitext(disk_path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.close()
    download_file(disk_path, tmp.name)
    return tmp.name


def check_docproc_health() -> bool:
    """Check if DocProc is running."""
    try:
        r = httpx.get(f"{DOCPROC_URL}/health", timeout=30)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


def upload_to_docproc(filepath: str, filename: str) -> dict:
    """Upload a file to DocProc. Returns task info."""
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    timeout = max(120, int(size_mb * 3))  # ~3s per MB, minimum 120s

    with open(filepath, "rb") as f:
        files = {"file": (filename, f, "application/octet-stream")}
        r = httpx.post(
            f"{DOCPROC_API}/documents/upload",
            files=files,
            timeout=timeout,
        )
    r.raise_for_status()
    return r.json()


def get_queue_stats() -> dict:
    """Get DocProc queue statistics."""
    r = httpx.get(f"{DOCPROC_API}/queue/stats", timeout=10)
    r.raise_for_status()
    return r.json()


def get_task_status(task_id: str) -> dict:
    """Get status of a specific task."""
    r = httpx.get(f"{DOCPROC_API}/queue/tasks/{task_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def get_all_tasks() -> list[dict]:
    """Get all tasks in the queue."""
    r = httpx.get(f"{DOCPROC_API}/queue/tasks", timeout=10)
    r.raise_for_status()
    return r.json()


def get_document_info(doc_id: str) -> dict:
    """Get document metadata."""
    r = httpx.get(f"{DOCPROC_API}/documents/{doc_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def get_document_chunks(doc_id: str, full_text: bool = True) -> list[dict]:
    """Fetch all chunks for a document, paginated."""
    chunks = []
    offset = 0
    limit = 500

    while True:
        r = httpx.get(
            f"{DOCPROC_API}/chunks",
            params={
                "document_id": doc_id,
                "full_text": str(full_text).lower(),
                "limit": limit,
                "offset": offset,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        batch = data.get("chunks", [])
        chunks.extend(batch)

        if len(batch) < limit:
            break
        offset += limit

    return chunks


def get_stage3_output(doc_id: str) -> list[dict]:
    """Fetch Stage 3 minimal model for a document."""
    r = httpx.get(f"{DOCPROC_API}/stage3/{doc_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def _init_yandex():
    """Lazy-init Yandex Disk module."""
    src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def export_to_yandex_disk(doc_id: str, source: str) -> bool:
    """Export enriched chunks for a document to Yandex Disk.

    Uploads two files per document:
    - chunks_enriched.json  — full chunks with metadata (no embeddings, too large)
    - chunks_minimal.json   — Stage 3 minimal model (12 fields)

    Path: /datasets/specs/{source}/{date}/_processed/{filename}/
    """
    _init_yandex()
    from yandex import ensure_tree, upload_bytes

    # Get document info
    try:
        doc = get_document_info(doc_id)
    except httpx.HTTPStatusError:
        print(f"    Document {doc_id} not found")
        return False

    filename = doc.get("filename", "unknown")
    status = doc.get("status", "")
    if status != "completed":
        print(f"    {filename}: status={status}, skipping (not completed)")
        return False

    # Fetch chunks
    chunks = get_document_chunks(doc_id)
    if not chunks:
        print(f"    {filename}: no chunks, skipping")
        return False

    # Fetch Stage 3 output
    try:
        stage3 = get_stage3_output(doc_id)
    except httpx.HTTPStatusError:
        stage3 = []

    # Build file stem from filename (no extension)
    stem, _ = os.path.splitext(filename)

    # Build Yandex Disk paths
    today = date.today().isoformat()
    base_path = f"/datasets/specs/{source}/{today}/_processed/{stem}"
    ensure_tree(base_path)

    # Upload enriched chunks (full metadata, no embeddings)
    enriched = []
    for c in chunks:
        enriched.append({
            "chunk_index": c.get("chunk_index", 0),
            "chunk_type": c.get("chunk_type", "text"),
            "text": c.get("text", ""),
            "section": c.get("section", ""),
            "page": c.get("page"),
            "context_header": c.get("context_header", ""),
            "token_count": c.get("token_count", 0),
            "strategy_used": c.get("strategy_used", ""),
            "vendor": c.get("vendor", ""),
            "standard_id": c.get("standard_id", ""),
            "doc_type": c.get("doc_type", ""),
            "lang": c.get("lang", ""),
            "block_types": c.get("block_types"),
        })

    enriched_json = json.dumps(enriched, ensure_ascii=False, indent=2).encode("utf-8")
    upload_bytes(enriched_json, f"{base_path}/chunks_enriched.json", overwrite=True)

    # Upload Stage 3 minimal model
    if stage3:
        minimal_json = json.dumps(stage3, ensure_ascii=False, indent=2).encode("utf-8")
        upload_bytes(minimal_json, f"{base_path}/chunks_minimal.json", overwrite=True)

    # Upload processing metadata
    meta = {
        "document_id": doc_id,
        "filename": filename,
        "source": source,
        "file_type": doc.get("file_type", ""),
        "page_count": doc.get("page_count"),
        "tables_count": doc.get("tables_count"),
        "has_ocr": doc.get("has_ocr", False),
        "total_chunks": len(chunks),
        "total_stage3": len(stage3),
        "parse_metadata": doc.get("parse_metadata"),
        "processed_at": doc.get("completed_at", ""),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    meta_json = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
    upload_bytes(meta_json, f"{base_path}/meta.json", overwrite=True)

    size_kb = (len(enriched_json) + len(minimal_json if stage3 else b"") + len(meta_json)) / 1024
    print(f"    Exported: {len(chunks)} chunks ({size_kb:.0f} KB) → {base_path}/")
    return True


def show_status():
    """Show current DocProc queue status."""
    if not check_docproc_health():
        print("DocProc is not running. Start it with: cd services/doc_proc && make up")
        return

    stats = get_queue_stats()
    print("\nQueue stats:")
    print(f"  Queue length:    {stats.get('queue_length', 0)}")
    print(f"  Processing:      {stats.get('processing', 0)}")
    print(f"  Total enqueued:  {stats.get('total_enqueued', 0)}")
    print(f"  Total completed: {stats.get('total_completed', 0)}")
    print(f"  Total failed:    {stats.get('total_failed', 0)}")

    tasks = get_all_tasks()
    if tasks:
        print(f"\nRecent tasks ({len(tasks)}):")
        for t in tasks[:20]:
            pct = t.get("progress_percent", 0)
            step = t.get("current_step", "")
            status = t.get("status", "")
            fname = t.get("filename", "?")
            error = t.get("error", "")
            line = f"  {fname[:50]:<50} {status:<12} {pct:>3}%  {step}"
            if error:
                line += f"  ERROR: {error[:60]}"
            print(line)


def ingest(
    source: str = "",
    local_dir: str = "",
    from_disk: bool = False,
    dry_run: bool = False,
    limit: int = 0,
    wait: bool = False,
    no_export: bool = False,
):
    """Main ingestion loop."""
    # Check DocProc health
    if not dry_run and not check_docproc_health():
        print("DocProc is not running. Start it with: cd services/doc_proc && make up")
        sys.exit(1)

    # Get file list
    if from_disk:
        if not source:
            print("--source is required with --from-disk")
            sys.exit(1)
        files = get_yandex_disk_files(source)
    else:
        files = get_local_files(source=source, local_dir=local_dir)

    if not files:
        print("No supported files found.")
        return

    if limit:
        files = files[:limit]

    total_size = sum(f["size_mb"] for f in files)
    print(f"\nFound {len(files)} files ({total_size:.1f} MB total)")
    print(f"Source: {'Yandex Disk' if from_disk else 'local'}")

    if dry_run:
        print("\nDry run — files that would be uploaded:")
        for f in files:
            print(f"  {f['name']:<60} {f['size_mb']:>8.1f} MB")
        return

    # Upload files
    tasks = []  # list of (task_id, doc_id) tuples
    uploaded = 0
    failed = 0

    for i, f in enumerate(files, 1):
        name = f["name"]
        print(f"\n[{i}/{len(files)}] {name} ({f['size_mb']:.1f} MB)")

        local_path = f["path"]
        tmp_path = None
        split_parts = []

        try:
            # Download from Yandex Disk if needed
            if from_disk:
                print("  Downloading from Yandex Disk...")
                tmp_path = download_from_yandex(f["path"])
                local_path = tmp_path

            # Split large PDFs into parts
            if f["size_mb"] > SPLIT_THRESHOLD_MB and name.lower().endswith(".pdf"):
                split_parts = split_large_pdf(local_path, name)

            if split_parts:
                # Upload each part
                for j, part in enumerate(split_parts, 1):
                    print(f"  Uploading part {j}/{len(split_parts)}: {part['name']} ({part['size_mb']:.1f} MB)")
                    result = upload_to_docproc(part["path"], part["name"])
                    task_id = result.get("task_id", "?")
                    doc_id = result.get("document_id", "?")
                    print(f"    Queued: task={task_id[:8]}...")
                    tasks.append((task_id, str(doc_id)))
                uploaded += 1
            else:
                # Upload whole file
                print("  Uploading to DocProc...")
                result = upload_to_docproc(local_path, name)
                task_id = result.get("task_id", "?")
                doc_id = result.get("document_id", "?")
                print(f"  Queued: task={task_id}, doc={doc_id}")
                tasks.append((task_id, str(doc_id)))
                uploaded += 1

        except httpx.HTTPStatusError as e:
            print(f"  FAILED: HTTP {e.response.status_code} — {e.response.text[:200]}")
            failed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1
        finally:
            # Clean up temp files
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            for part in split_parts:
                if part.get("temp") and os.path.exists(part["path"]):
                    os.unlink(part["path"])

    print(f"\n{'='*60}")
    print(f"Uploaded: {uploaded}/{len(files)}, Failed: {failed}")

    if not tasks:
        return

    task_ids = [t[0] for t in tasks]
    doc_ids = [t[1] for t in tasks]

    # Save task IDs for tracking
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")
    os.makedirs(log_dir, exist_ok=True)
    log_name = f"docproc_ingest_{source or 'custom'}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    log_path = os.path.join(log_dir, log_name)
    with open(log_path, "w") as f:
        json.dump({
            "source": source or local_dir,
            "from_disk": from_disk,
            "total_files": len(files),
            "uploaded": uploaded,
            "failed": failed,
            "task_ids": task_ids,
            "document_ids": doc_ids,
        }, f, indent=2)
    print(f"Task log saved: {log_path}")

    if wait:
        export_source = source or "custom"
        do_export = not no_export
        print(f"\nWaiting for {len(task_ids)} tasks to complete...")
        completed_doc_ids = monitor_tasks(task_ids)

        if do_export and completed_doc_ids:
            print(f"\nExporting {len(completed_doc_ids)} documents to Yandex Disk...")
            export_ok = 0
            export_fail = 0
            for doc_id in completed_doc_ids:
                try:
                    if export_to_yandex_disk(doc_id, export_source):
                        export_ok += 1
                    else:
                        export_fail += 1
                except Exception as e:
                    print(f"    Export failed for {doc_id}: {e}")
                    export_fail += 1
            print(f"\nExport done: {export_ok} OK, {export_fail} failed")


def monitor_tasks(task_ids: list[str]) -> list[str]:
    """Poll until all tasks are done. Returns list of completed document IDs."""
    pending = set(task_ids)
    completed_count = 0
    failed_count = 0
    completed_doc_ids = []

    while pending:
        done = set()
        for tid in pending:
            try:
                t = get_task_status(tid)
                status = t.get("status", "")
                pct = t.get("progress_percent", 0)
                step = t.get("current_step", "")
                fname = t.get("filename", "?")
                doc_id = t.get("document_id", "")

                if status == "completed":
                    print(f"  DONE: {fname}")
                    completed_count += 1
                    if doc_id:
                        completed_doc_ids.append(doc_id)
                    done.add(tid)
                elif status == "failed":
                    error = t.get("error", "unknown")
                    print(f"  FAIL: {fname} — {error[:100]}")
                    failed_count += 1
                    done.add(tid)
                else:
                    # Still processing — show inline progress
                    sys.stdout.write(f"\r  [{len(pending) - len(done)} remaining] {fname[:40]} {pct}% {step}    ")
                    sys.stdout.flush()
            except Exception:
                pass

        pending -= done
        if pending:
            time.sleep(POLL_INTERVAL)

    print(f"\n\nAll done: {completed_count} completed, {failed_count} failed")
    return completed_doc_ids


def main():
    parser = argparse.ArgumentParser(description="Ingest files into DocProc microservice")
    parser.add_argument("--source", type=str, default="", help="Source domain (e.g. pulsal.ru)")
    parser.add_argument("--local-dir", type=str, default="", help="Local directory with files")
    parser.add_argument("--from-disk", action="store_true", help="Download from Yandex Disk instead of local")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    parser.add_argument("--limit", type=int, default=0, help="Max files to ingest")
    parser.add_argument("--wait", action="store_true", help="Wait for all tasks to complete")
    parser.add_argument("--no-export", action="store_true", help="Don't export chunks to Yandex Disk after processing")
    parser.add_argument("--export-doc", type=str, default="", help="Export a single already-processed document to Yandex Disk")
    parser.add_argument("--status", action="store_true", help="Show DocProc queue status")
    parser.add_argument("--docproc-url", type=str, default="", help="DocProc URL (default: http://localhost:8001)")

    args = parser.parse_args()

    if args.docproc_url:
        global DOCPROC_URL, DOCPROC_API
        DOCPROC_URL = args.docproc_url
        DOCPROC_API = f"{DOCPROC_URL}/api/v1"

    if args.status:
        show_status()
        return

    if args.export_doc:
        if not args.source:
            parser.error("--source is required with --export-doc")
        if not check_docproc_health():
            print("DocProc is not running.")
            sys.exit(1)
        export_to_yandex_disk(args.export_doc, args.source)
        return

    if not args.source and not args.local_dir:
        parser.error("Provide --source or --local-dir (or --status to check queue)")

    ingest(
        source=args.source,
        local_dir=args.local_dir,
        from_disk=args.from_disk,
        dry_run=args.dry_run,
        limit=args.limit,
        wait=args.wait,
        no_export=args.no_export,
    )


if __name__ == "__main__":
    main()
