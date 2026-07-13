#!/usr/bin/env python3
"""Re-chunk all documents with improved chunker v2.1.

Saves BEFORE metrics snapshot, re-chunks all docs, saves AFTER snapshot,
prints comparison report.

Usage:
    PYTHONPATH=src python3 scripts/rechunk_all.py
    PYTHONPATH=src python3 scripts/rechunk_all.py --dry-run   # just count, no changes
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chunker import chunk_units_v2

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets", "electrical")
RUNS_DIR = os.path.join(os.path.dirname(__file__), "..", "runs")
TARGET_TOKENS = 1000
MAX_TOKENS = 1200


def collect_metrics():
    """Aggregate metrics from all chunking_log.json files."""
    logs = glob.glob(os.path.join(DATASETS_DIR, "**", "chunking_log.json"), recursive=True)
    total_docs = 0
    total_chunks = 0
    total_tokens = 0
    total_oversized = 0
    total_violations = 0
    total_tiny = 0
    max_tokens_seen = 0

    for f in logs:
        try:
            d = json.load(open(f))
            tc = d.get("total_chunks", 0)
            avg = d.get("avg_chunk_tokens", 0)
            mx = d.get("max_chunk_tokens", 0)
            total_docs += 1
            total_chunks += tc
            total_tokens += avg * tc
            total_oversized += d.get("oversized_chunks", 0)
            total_violations += d.get("token_limit_violations", 0)
            if avg < 200 and tc > 0:
                total_tiny += 1
            if mx > max_tokens_seen:
                max_tokens_seen = mx
        except Exception:
            pass

    return {
        "documents": total_docs,
        "total_chunks": total_chunks,
        "avg_tokens_per_chunk": total_tokens // max(total_chunks, 1),
        "max_tokens_seen": max_tokens_seen,
        "oversized_chunks": total_oversized,
        "token_violations": total_violations,
        "tiny_docs": total_tiny,
    }


def find_doc_dirs():
    """Find all document directories with units/ subdirectory."""
    units_dirs = glob.glob(os.path.join(DATASETS_DIR, "**", "units"), recursive=True)
    doc_dirs = []
    for ud in units_dirs:
        doc_dir = os.path.dirname(ud)
        chunks_dir = os.path.join(doc_dir, "chunks")
        if os.path.isdir(chunks_dir):
            doc_dirs.append(doc_dir)
    return sorted(doc_dirs)


def main():
    dry_run = "--dry-run" in sys.argv

    # Collect BEFORE metrics
    print("Collecting BEFORE metrics...")
    before = collect_metrics()
    before_path = os.path.join(RUNS_DIR, "rechunk_before.json")
    os.makedirs(RUNS_DIR, exist_ok=True)
    json.dump(before, open(before_path, "w"), indent=2)
    print(f"  Saved to {before_path}")
    print(f"  Documents:    {before['documents']:,}")
    print(f"  Chunks:       {before['total_chunks']:,}")
    print(f"  Avg tok/chunk: {before['avg_tokens_per_chunk']}")
    print(f"  Max tokens:    {before['max_tokens_seen']}")
    print(f"  Oversized:     {before['oversized_chunks']:,}")
    print(f"  Violations:    {before['token_violations']:,}")
    print(f"  Tiny docs:     {before['tiny_docs']:,}")

    doc_dirs = find_doc_dirs()
    print(f"\nFound {len(doc_dirs):,} documents to re-chunk")

    if dry_run:
        print("DRY RUN — no changes made")
        return

    # Re-chunk all documents
    print("\nRe-chunking...")
    start = time.time()
    errors = []
    for i, doc_dir in enumerate(doc_dirs):
        units_dir = os.path.join(doc_dir, "units")
        chunks_dir = os.path.join(doc_dir, "chunks")
        minimal_dir = os.path.join(doc_dir, "chunks_minimal")
        minimal_arg = minimal_dir if os.path.isdir(minimal_dir) else None

        try:
            chunk_units_v2(
                units_dir=units_dir,
                chunks_dir=chunks_dir,
                target_tokens=TARGET_TOKENS,
                max_tokens=MAX_TOKENS,
                minimal_chunks_dir=minimal_arg,
            )
        except Exception as e:
            errors.append((doc_dir, str(e)))

        if (i + 1) % 1000 == 0 or (i + 1) == len(doc_dirs):
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (len(doc_dirs) - i - 1) / rate if rate > 0 else 0
            print(f"  {i + 1:,}/{len(doc_dirs):,} ({rate:.0f} docs/sec, ~{remaining:.0f}s remaining)")

    elapsed = time.time() - start
    print(f"\nRe-chunked {len(doc_dirs):,} documents in {elapsed:.1f}s ({len(doc_dirs)/elapsed:.0f} docs/sec)")

    if errors:
        print(f"\n{len(errors)} errors:")
        for doc_dir, err in errors[:10]:
            print(f"  {doc_dir}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    # Collect AFTER metrics
    print("\nCollecting AFTER metrics...")
    after = collect_metrics()
    after_path = os.path.join(RUNS_DIR, "rechunk_after.json")
    json.dump(after, open(after_path, "w"), indent=2)

    # Print comparison
    print("\n" + "=" * 60)
    print("BEFORE vs AFTER re-chunk comparison")
    print("=" * 60)
    fields = [
        ("Documents", "documents"),
        ("Total chunks", "total_chunks"),
        ("Avg tok/chunk", "avg_tokens_per_chunk"),
        ("Max tokens", "max_tokens_seen"),
        ("Oversized", "oversized_chunks"),
        ("Violations", "token_violations"),
        ("Tiny docs", "tiny_docs"),
    ]
    print(f"{'Metric':<20} {'BEFORE':>12} {'AFTER':>12} {'Delta':>12}")
    print("-" * 58)
    for label, key in fields:
        b = before[key]
        a = after[key]
        delta = a - b
        sign = "+" if delta > 0 else ""
        print(f"{label:<20} {b:>12,} {a:>12,} {sign}{delta:>11,}")

    # Save full report
    report = {
        "before": before,
        "after": after,
        "elapsed_seconds": round(elapsed, 1),
        "errors": len(errors),
        "doc_count": len(doc_dirs),
    }
    report_path = os.path.join(RUNS_DIR, "rechunk_report.json")
    json.dump(report, open(report_path, "w"), indent=2, ensure_ascii=False)
    print(f"\nFull report: {report_path}")


if __name__ == "__main__":
    main()
