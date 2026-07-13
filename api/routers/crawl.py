import os
import sys
from pathlib import Path
from uuid import UUID

import requests as req
from fastapi import APIRouter, HTTPException

from ..models import CrawlRequest, CrawlStatus, Progress, TaskCreated
from ..models import TaskStatus as TaskStatusEnum
from ..tasks import registry

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DISCOVERY_DIR = PROJECT_ROOT / "discovery"


def _run_crawl(task_id: str, request: CrawlRequest):
    record = registry.get(task_id)
    record.progress = {
        "pages_visited": 0,
        "product_urls_found": 0,
        "file_urls_found": 0,
        "errors": 0,
        "rate_limits": 0,
    }

    src_path = str(PROJECT_ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    os.environ.setdefault("YANDEX_DISK_TOKEN", "__api_mode__")
    os.environ["WEB_CRAWL_DELAY_SEC"] = str(request.delay_sec)

    from scripts.discover_catalogue import _discovery_filename, discover_catalogue

    DISCOVERY_DIR.mkdir(exist_ok=True)
    output_path = str(DISCOVERY_DIR / _discovery_filename(request.url))

    result = discover_catalogue(
        root_url=request.url,
        output_path=output_path,
        max_pages=request.max_pages,
        resume_state=None,
        skip_leaves=True,
    )

    record.progress.update(
        {
            "pages_visited": result.get("pages_visited", 0),
            "product_urls_found": result.get("urls_found", 0),
        }
    )

    if request.callback_url:
        try:
            req.post(
                request.callback_url,
                json={"task_id": task_id, "status": "completed", "result": result},
                timeout=10,
            )
        except Exception:
            pass

    return result


@router.post("/crawl", response_model=TaskCreated, status_code=202)
def start_crawl(request: CrawlRequest):
    record = registry.create()
    registry.submit(record.task_id, _run_crawl, record.task_id, request)
    return TaskCreated(task_id=UUID(record.task_id))


@router.get("/crawl/{task_id}/status", response_model=CrawlStatus)
def get_crawl_status(task_id: str):
    record = registry.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")

    p = record.progress or {}
    progress = Progress(processed=p.get("pages_visited", 0), total=0)

    return CrawlStatus(
        task_id=UUID(task_id),
        status=TaskStatusEnum(record.status),
        progress=progress,
        pages_visited=p.get("pages_visited", 0),
        product_urls_found=p.get("product_urls_found", 0),
        file_urls_found=p.get("file_urls_found", 0),
        errors=p.get("errors", 0),
        rate_limits=p.get("rate_limits", 0),
        started_at=record.started_at,
        error=record.error,
    )
