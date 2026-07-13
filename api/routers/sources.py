from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models import ApproveRequest, Source, SourceMode, SourcesList, SourceStatus
from ..sources_store import sources_store

router = APIRouter()


def _to_source_model(s: dict) -> Source:
    return Source(
        id=UUID(s["id"]),
        url=s["url"],
        domain=s.get("domain", ""),
        score=s.get("score", 0.0),
        status=SourceStatus(s.get("status", "candidate")),
        mode=SourceMode(s.get("mode", "unknown")),
        profile=s.get("profile"),
        file_links_found=s.get("file_links_found"),
        product_links_found=s.get("product_links_found"),
    )


@router.get("/sources", response_model=SourcesList)
def list_sources(
    status: Optional[str] = Query(None),
    profile: Optional[str] = Query(None),
):
    raw = sources_store.list_sources(status_filter=status, profile_filter=profile)
    items = [_to_source_model(s) for s in raw]
    return SourcesList(sources=items, total=len(items))


@router.post("/sources/{source_id}/approve", response_model=Source)
def approve_source(source_id: str, body: ApproveRequest):
    if body.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=422, detail="status must be 'approved' or 'rejected'"
        )
    updated = sources_store.set_status(source_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return _to_source_model(updated)
