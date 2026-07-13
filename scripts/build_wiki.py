#!/usr/bin/env python3
import glob
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_CONTENT_DIR = os.path.join(ROOT, "wiki", "content")
WIKI_OUT_DIR = os.path.join(ROOT, "wiki", "out")
RUNS_DIR = os.path.join(ROOT, "runs")
DATASETS_DIR = os.path.join(ROOT, "datasets")


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content.rstrip() + "\n")


def find_latest_manifest() -> Optional[Dict]:
    manifest_paths = sorted(glob.glob(os.path.join(RUNS_DIR, "ingest_*.json")))
    if not manifest_paths:
        return None

    latest_path = manifest_paths[-1]
    with open(latest_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    data["_path"] = latest_path
    return data


def find_latest_auto_eval() -> Optional[Dict]:
    preferred_path = os.path.join(RUNS_DIR, "auto_eval_latest.json")
    if os.path.exists(preferred_path):
        with open(preferred_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        data["_path"] = preferred_path
        return data

    eval_paths = sorted(glob.glob(os.path.join(RUNS_DIR, "auto_eval_*.json")))
    if not eval_paths:
        return None

    latest_path = eval_paths[-1]
    with open(latest_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    data["_path"] = latest_path
    return data


METRICS_CACHE_PATH = os.path.join(ROOT, "runs", ".wiki_metrics_cache.json")


def _load_metrics_cache() -> Optional[Dict]:
    if not os.path.exists(METRICS_CACHE_PATH):
        return None
    with open(METRICS_CACHE_PATH, "r") as f:
        return json.load(f)


def _save_metrics_cache(extraction, chunking, quality):
    cache = {
        "extraction": extraction,
        "chunking": chunking,
        "quality": quality,
    }
    os.makedirs(os.path.dirname(METRICS_CACHE_PATH), exist_ok=True)
    with open(METRICS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _collect_logs(filename: str) -> List[Dict]:
    pattern = os.path.join(DATASETS_DIR, "**", filename)
    paths = glob.glob(pattern, recursive=True)

    logs = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            data["_path"] = path
            logs.append(data)
        except Exception:
            continue

    return logs


def collect_extraction_logs() -> List[Dict]:
    return _collect_logs("extraction_log.json")


def collect_chunking_logs() -> List[Dict]:
    return _collect_logs("chunking_log.json")


def collect_quality_logs() -> List[Dict]:
    return _collect_logs("quality_gate.json")


def summarize_extraction(logs: List[Dict]) -> Dict[str, int]:
    summary = {
        "documents": len(logs),
        "total_pages": 0,
        "processed_pages": 0,
        "ocr_pages": 0,
        "failed_pages": 0,
    }

    for log in logs:
        summary["total_pages"] += int(log.get("total_pages", 0))
        summary["processed_pages"] += int(log.get("processed_pages", log.get("processed", 0)))
        summary["ocr_pages"] += int(log.get("ocr_pages", 0))
        summary["failed_pages"] += int(log.get("failed_pages", log.get("failed", 0)))

    return summary


def summarize_chunking(logs: List[Dict]) -> Dict[str, int]:
    summary = {
        "documents": len(logs),
        "total_units": 0,
        "total_blocks": 0,
        "sectioned_blocks": 0,
        "total_chunks": 0,
        "protected_table_blocks": 0,
        "protected_normative_blocks": 0,
        "protected_table_normative_blocks": 0,
        "oversized_chunks": 0,
        "token_limit_violations": 0,
        "protected_split_violations": 0,
        "minimal_chunks_written": 0,
        "avg_chunk_tokens": 0,
        "max_chunk_tokens": 0,
    }

    avg_values = []

    for log in logs:
        summary["total_units"] += int(log.get("total_units", 0))
        summary["total_blocks"] += int(log.get("total_blocks", 0))
        summary["sectioned_blocks"] += int(log.get("sectioned_blocks", 0))
        summary["total_chunks"] += int(log.get("total_chunks", 0))
        summary["protected_table_blocks"] += int(log.get("protected_table_blocks", 0))
        summary["protected_normative_blocks"] += int(log.get("protected_normative_blocks", 0))
        summary["protected_table_normative_blocks"] += int(
            log.get("protected_table_normative_blocks", 0)
        )
        summary["oversized_chunks"] += int(log.get("oversized_chunks", 0))
        summary["token_limit_violations"] += int(log.get("token_limit_violations", 0))
        summary["protected_split_violations"] += int(log.get("protected_split_violations", 0))
        summary["minimal_chunks_written"] += int(log.get("minimal_chunks_written", 0))
        summary["max_chunk_tokens"] = max(
            summary["max_chunk_tokens"], int(log.get("max_chunk_tokens", 0))
        )

        avg_val = int(log.get("avg_chunk_tokens", 0))
        if avg_val > 0:
            avg_values.append(avg_val)

    if avg_values:
        summary["avg_chunk_tokens"] = int(sum(avg_values) / len(avg_values))

    return summary


def summarize_quality(logs: List[Dict]) -> Dict[str, int]:
    summary = {
        "documents": len(logs),
        "pass_count": 0,
        "warn_count": 0,
        "total_chunks": 0,
        "empty_chunks": 0,
        "tiny_chunks": 0,
        "duplicate_chunks": 0,
        "noisy_chunks": 0,
    }

    for log in logs:
        status = log.get("status", "")
        if status == "pass":
            summary["pass_count"] += 1
        elif status == "warn":
            summary["warn_count"] += 1

        metrics = log.get("metrics", {})
        summary["total_chunks"] += int(metrics.get("total_chunks", 0))
        summary["empty_chunks"] += int(metrics.get("empty_chunks", 0))
        summary["tiny_chunks"] += int(metrics.get("tiny_chunks", 0))
        summary["duplicate_chunks"] += int(metrics.get("duplicate_chunks", 0))
        summary["noisy_chunks"] += int(metrics.get("noisy_chunks", 0))

    return summary


def render_manifest_block(manifest: Optional[Dict]) -> str:
    if not manifest:
        return "- No ingest run manifests found yet."

    counts = manifest.get("status_counts", {})
    counts_line = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "n/a"

    return "\n".join(
        [
            f"- Latest run: `{os.path.basename(manifest.get('_path', 'unknown'))}`",
            f"- Source page: `{manifest.get('source_page', 'n/a')}`",
            f"- Started: `{manifest.get('started_at', 'n/a')}`",
            f"- Finished: `{manifest.get('finished_at', 'n/a')}`",
            f"- Links found: `{manifest.get('links_found', 0)}`",
            f"- Status counts: `{counts_line}`",
        ]
    )


def render_eval_block(eval_payload: Optional[Dict]) -> str:
    if not eval_payload:
        return "- No auto-eval report found yet."

    auto_eval = eval_payload.get("auto_eval", {})
    quality_summary = eval_payload.get("quality_summary", {})
    return "\n".join(
        [
            f"- Latest eval: `{os.path.basename(eval_payload.get('_path', 'unknown'))}`",
            f"- Questions: `{auto_eval.get('total_questions', 0)}`",
            f"- Hit@k: `{auto_eval.get('hit_count', 0)}`",
            f"- Hit rate: `{auto_eval.get('hit_rate', 0)}`",
            f"- Indexed chunks: `{auto_eval.get('total_chunks_indexed', 0)}`",
            f"- Quality pass/warn: `{quality_summary.get('pass_count', 0)}/{quality_summary.get('warn_count', 0)}`",
        ]
    )


def build_outputs() -> None:
    os.makedirs(WIKI_OUT_DIR, exist_ok=True)

    roadmap_template = read_file(os.path.join(WIKI_CONTENT_DIR, "roadmap.md"))
    stage1_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-1.md"))
    stage2_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-2.md"))
    stage3_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-3.md"))
    automation_template = read_file(os.path.join(WIKI_CONTENT_DIR, "automation.md"))
    stage_integration_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-integration.md"))
    stage5_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-5.md"))
    stage6_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-6.md"))
    stage7_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-7.md"))
    stage8_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-8.md"))
    stage9_template = read_file(os.path.join(WIKI_CONTENT_DIR, "stage-9.md"))
    user_guide_template = read_file(os.path.join(WIKI_CONTENT_DIR, "user-guide.md"))
    architecture_template = read_file(os.path.join(WIKI_CONTENT_DIR, "architecture.md"))
    operations_template = read_file(os.path.join(WIKI_CONTENT_DIR, "operations.md"))
    api_reference_template = read_file(os.path.join(WIKI_CONTENT_DIR, "api-reference.md"))
    doc_proc_template = read_file(os.path.join(WIKI_CONTENT_DIR, "doc-proc.md"))

    cached = _load_metrics_cache()
    if cached:
        extraction_summary = cached["extraction"]
        chunking_summary = cached["chunking"]
        quality_summary = cached["quality"]
    else:
        extraction_summary = summarize_extraction(collect_extraction_logs())
        chunking_summary = summarize_chunking(collect_chunking_logs())
        quality_summary = summarize_quality(collect_quality_logs())
        _save_metrics_cache(extraction_summary, chunking_summary, quality_summary)

    manifest = find_latest_manifest()
    latest_eval = find_latest_auto_eval()
    generated_at = datetime.now(timezone.utc).isoformat()

    extraction_block = "\n".join(
        [
            "## Auto Metrics - Extraction",
            "",
            f"- Generated at (UTC): `{generated_at}`",
            f"- Documents with extraction logs: `{extraction_summary['documents']}`",
            f"- Total pages: `{extraction_summary['total_pages']}`",
            f"- Processed pages: `{extraction_summary['processed_pages']}`",
            f"- OCR pages: `{extraction_summary['ocr_pages']}`",
            f"- Failed pages: `{extraction_summary['failed_pages']}`",
        ]
    )

    chunking_block = "\n".join(
        [
            "## Auto Metrics - Chunking v2",
            "",
            f"- Documents with chunking logs: `{chunking_summary['documents']}`",
            f"- Total units: `{chunking_summary['total_units']}`",
            f"- Total blocks: `{chunking_summary['total_blocks']}`",
            f"- Sectioned blocks: `{chunking_summary['sectioned_blocks']}`",
            f"- Total chunks: `{chunking_summary['total_chunks']}`",
            f"- Avg chunk tokens: `{chunking_summary['avg_chunk_tokens']}`",
            f"- Max chunk tokens: `{chunking_summary['max_chunk_tokens']}`",
            f"- Protected table blocks: `{chunking_summary['protected_table_blocks']}`",
            f"- Protected normative blocks: `{chunking_summary['protected_normative_blocks']}`",
            f"- Protected table+normative blocks: `{chunking_summary['protected_table_normative_blocks']}`",
            f"- Token limit violations: `{chunking_summary['token_limit_violations']}`",
            f"- Protected split violations: `{chunking_summary['protected_split_violations']}`",
            f"- Oversized chunks: `{chunking_summary['oversized_chunks']}`",
        ]
    )

    stage3_block = "\n".join(
        [
            "## Auto Metrics - Stage 3 Minimal Model",
            "",
            f"- Minimal chunks written: `{chunking_summary['minimal_chunks_written']}`",
            "- Minimal schema: `document, page, section, chunk_index, text, doc_type, vendor, standard_id, year, lang, source_type, quality_status`",
        ]
    )

    quality_block = "\n".join(
        [
            "## Auto Metrics - Quality Gate",
            "",
            f"- Documents with quality logs: `{quality_summary['documents']}`",
            f"- Pass: `{quality_summary['pass_count']}`",
            f"- Warn: `{quality_summary['warn_count']}`",
            f"- Total chunks checked: `{quality_summary['total_chunks']}`",
            f"- Empty chunks: `{quality_summary['empty_chunks']}`",
            f"- Tiny chunks: `{quality_summary['tiny_chunks']}`",
            f"- Duplicate chunks: `{quality_summary['duplicate_chunks']}`",
            f"- Noisy chunks: `{quality_summary['noisy_chunks']}`",
        ]
    )

    eval_block = "\n".join(
        [
            "## Auto Metrics - Retrieval Eval",
            "",
            render_eval_block(latest_eval),
        ]
    )

    manifest_block = "\n".join(
        [
            "## Latest Ingest Run",
            "",
            render_manifest_block(manifest),
        ]
    )

    status_page = "\n\n".join(
        [
            "# Scrapper v2 - Status Report",
            "This page is generated automatically from local run artifacts.",
            extraction_block,
            chunking_block,
            quality_block,
            eval_block,
            manifest_block,
        ]
    )

    stage1_page = "\n\n".join([stage1_template, extraction_block, manifest_block])
    stage2_page = "\n\n".join([stage2_template, chunking_block, quality_block, eval_block, manifest_block])
    stage3_page = "\n\n".join([stage3_template, stage3_block, manifest_block])
    automation_page = "\n\n".join([automation_template, eval_block, manifest_block])

    write_file(os.path.join(WIKI_OUT_DIR, "01-roadmap.md"), roadmap_template)
    write_file(os.path.join(WIKI_OUT_DIR, "02-stage-1.md"), stage1_page)
    write_file(os.path.join(WIKI_OUT_DIR, "03-stage-2.md"), stage2_page)
    write_file(os.path.join(WIKI_OUT_DIR, "04-stage-3.md"), stage3_page)
    write_file(os.path.join(WIKI_OUT_DIR, "05-status.md"), status_page)
    write_file(os.path.join(WIKI_OUT_DIR, "06-automation.md"), automation_page)

    # Stage 5-10 pages (static content, no metric injection)
    write_file(os.path.join(WIKI_OUT_DIR, "10-stage-5.md"), stage_integration_template)
    write_file(os.path.join(WIKI_OUT_DIR, "11-stage-6.md"), stage5_template)
    write_file(os.path.join(WIKI_OUT_DIR, "12-stage-7.md"), stage6_template)
    write_file(os.path.join(WIKI_OUT_DIR, "13-stage-8.md"), stage7_template)
    write_file(os.path.join(WIKI_OUT_DIR, "14-stage-9.md"), stage8_template)
    write_file(os.path.join(WIKI_OUT_DIR, "15-stage-10.md"), stage9_template)

    # User/product documentation pages
    operations_page = operations_template.replace("{{LATEST_MANIFEST_BLOCK}}", manifest_block)
    write_file(os.path.join(WIKI_OUT_DIR, "07-user-guide.md"), user_guide_template)
    write_file(os.path.join(WIKI_OUT_DIR, "08-architecture.md"), architecture_template)
    write_file(os.path.join(WIKI_OUT_DIR, "09-operations.md"), operations_page)
    write_file(os.path.join(WIKI_OUT_DIR, "16-api-reference.md"), api_reference_template)
    write_file(os.path.join(WIKI_OUT_DIR, "18-doc-proc.md"), doc_proc_template)

    print("Generated wiki pages:")
    for name in [
        "01-roadmap.md", "02-stage-1.md", "03-stage-2.md", "04-stage-3.md",
        "05-status.md", "06-automation.md", "07-user-guide.md",
        "08-architecture.md", "09-operations.md",
        "10-stage-5.md", "11-stage-6.md", "12-stage-7.md",
        "13-stage-8.md", "14-stage-9.md", "15-stage-10.md",
        "16-api-reference.md", "18-doc-proc.md",
    ]:
        print(f"- {os.path.join(WIKI_OUT_DIR, name)}")


if __name__ == "__main__":
    import sys
    if "--force" in sys.argv:
        # Delete cache to force full rescan
        if os.path.exists(METRICS_CACHE_PATH):
            os.remove(METRICS_CACHE_PATH)
            print("Metrics cache cleared.")
    build_outputs()
