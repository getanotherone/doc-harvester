import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List
from uuid import UUID

import requests
from fastapi import APIRouter, HTTPException

from ..models import FetchRequest, FetchResult, FetchResults, Progress, TaskCreated
from ..models import TaskStatus as TaskStatusEnum
from ..tasks import registry

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _fetch_single_url(url: str, mode: str) -> FetchResult:
    src_path = str(PROJECT_ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    os.environ.setdefault("YANDEX_DISK_TOKEN", "__api_mode__")

    from extractors import extract_web_html_blocks
    from scraper import REQUEST_HEADERS, _fetch_page_html, _is_file_link

    is_file = _is_file_link(url)
    effective_mode = mode if mode != "auto" else ("files" if is_file else "web")

    if effective_mode == "web":
        try:
            html = _fetch_page_html(url)
            if html is None:
                return FetchResult(url=url, status="error", error="Fetch returned None")
            blocks = extract_web_html_blocks(html)
            cleaned = "\n\n".join(blocks)
            return FetchResult(
                url=url,
                status="ok",
                content_type="html",
                cleaned_html=cleaned,
                size_bytes=len(cleaned.encode("utf-8")),
            )
        except Exception as exc:
            return FetchResult(url=url, status="error", error=str(exc))
    else:
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=60, stream=True)
            resp.raise_for_status()
            ext = Path(url.split("?")[0]).suffix.lower().lstrip(".")
            content_type = ext if ext in ("pdf", "docx", "xlsx") else "other"
            suffix = f".{ext}" if ext else ""
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, dir=tempfile.gettempdir()
            ) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                file_path = f.name
            size_bytes = Path(file_path).stat().st_size
            return FetchResult(
                url=url,
                status="ok",
                content_type=content_type,
                file_path=file_path,
                size_bytes=size_bytes,
            )
        except Exception as exc:
            return FetchResult(url=url, status="error", error=str(exc))


def _run_fetch(task_id: str, request: FetchRequest):
    record = registry.get(task_id)
    results: List[FetchResult] = []
    total = len(request.urls)

    for idx, url in enumerate(request.urls):
        record.progress = {"processed": idx, "total": total}
        result = _fetch_single_url(url, request.mode)
        results.append(result)
        if idx < total - 1:
            time.sleep(request.delay_sec)

    record.progress = {"processed": total, "total": total}

    if request.callback_url:
        try:
            import requests as req

            req.post(
                request.callback_url,
                json={"task_id": task_id, "status": "completed", "urls_fetched": total},
                timeout=10,
            )
        except Exception:
            pass

    return [r.model_dump() for r in results]


@router.post("/fetch", response_model=TaskCreated, status_code=202)
def start_fetch(request: FetchRequest):
    record = registry.create()
    registry.submit(record.task_id, _run_fetch, record.task_id, request)
    return TaskCreated(task_id=UUID(record.task_id))


@router.get("/fetch/{task_id}/results", response_model=FetchResults)
def get_fetch_results(task_id: str):
    record = registry.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")

    p = record.progress or {}
    progress = Progress(processed=p.get("processed", 0), total=p.get("total", 0))

    results = []
    if record.result:
        results = [FetchResult(**r) for r in record.result]

    return FetchResults(
        task_id=UUID(task_id),
        status=TaskStatusEnum(record.status),
        progress=progress,
        results=results,
    )
