import json
import os
import sys
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models import DiscoverRequest, DiscoverStatus, Progress, TaskCreated
from ..models import TaskStatus as TaskStatusEnum
from ..sources_store import sources_store
from ..tasks import registry

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DISCOVERY_DIR = PROJECT_ROOT / "discovery"


def _run_discover(task_id: str, request: DiscoverRequest):
    record = registry.get(task_id)

    src_path = str(PROJECT_ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    os.environ.setdefault("YANDEX_DISK_TOKEN", "__api_mode__")

    from scripts.discover_sources import _load_profile, discover_sources

    profile = _load_profile(request.profile)
    queries = profile.get("queries", [])
    record.progress = {"processed": 0, "total": len(queries)}

    result = discover_sources(
        queries=queries,
        profile=profile,
        profile_name=request.profile,
        research_sources=[],
        limit_per_query=20,
        top_n=request.top_n,
        probe=request.probe,
        engine=request.engine,
    )

    record.progress = {"processed": len(queries), "total": len(queries)}

    sources_store.ingest_discovery_result(
        result.get("candidates", []),
        request.profile,
    )

    DISCOVERY_DIR.mkdir(exist_ok=True)
    out_path = DISCOVERY_DIR / f"sources_candidates_{request.profile}.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"candidates_found": result.get("total_candidates", 0)}


@router.post("/discover", response_model=TaskCreated, status_code=202)
def start_discovery(request: DiscoverRequest):
    record = registry.create()
    registry.submit(record.task_id, _run_discover, record.task_id, request)
    return TaskCreated(task_id=UUID(record.task_id))


@router.get("/discover/{task_id}/status", response_model=DiscoverStatus)
def get_discovery_status(task_id: str):
    record = registry.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")

    candidates_found = None
    if record.result:
        candidates_found = record.result.get("candidates_found")

    progress = None
    if record.progress:
        progress = Progress(**record.progress)

    return DiscoverStatus(
        task_id=UUID(task_id),
        status=TaskStatusEnum(record.status),
        progress=progress,
        candidates_found=candidates_found,
        error=record.error,
    )
