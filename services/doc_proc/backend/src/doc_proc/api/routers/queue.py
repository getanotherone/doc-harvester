"""Queue management endpoints — stats, task status, cancel."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from doc_proc.api.schemas import QueueStatsResponse, QueueTaskResponse
from doc_proc.queue.service import DocumentQueueService

router = APIRouter()


def _get_queue() -> DocumentQueueService:
    return DocumentQueueService()


@router.get("/stats", response_model=QueueStatsResponse)
async def get_stats():
    queue = _get_queue()
    stats = await queue.get_stats()
    return QueueStatsResponse(**stats)


@router.get("/tasks/{task_id}", response_model=QueueTaskResponse)
async def get_task(task_id: str):
    queue = _get_queue()
    task = await queue.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return QueueTaskResponse(
        task_id=task.task_id,
        document_id=task.document_id,
        filename=task.filename,
        status=task.status,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error=task.error,
        retry_count=task.retry_count,
        progress_percent=task.progress_percent,
        current_step=task.current_step,
        steps_detail=task.steps_detail,
    )


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    queue = _get_queue()
    task = await queue.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await queue.cancel(task_id)
    return {"cancelled": True}
