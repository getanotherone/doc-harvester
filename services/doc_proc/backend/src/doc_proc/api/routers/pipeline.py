"""Pipeline endpoints — run full pipeline, compare strategies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.api.schemas import (
    ComparisonResponse,
    PipelineCompareRequest,
    QualityReportResponse,
    StrategyInfo,
)
from doc_proc.db.models import Document
from doc_proc.db.session import get_db

router = APIRouter()


@router.get("/strategies", response_model=list[StrategyInfo])
async def list_strategies():
    """List all available chunking strategies."""
    from doc_proc.chunking.registry import list_strategies
    return list_strategies()


@router.post("/compare", response_model=ComparisonResponse)
async def compare_strategies(
    request: PipelineCompareRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run multiple strategies on the same document and compare results."""
    doc = (
        await db.execute(select(Document).where(Document.id == request.document_id))
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    from doc_proc.storage.minio import download_file
    content = download_file(doc.file_path)

    from doc_proc.pipeline import Pipeline, PipelineConfig
    config = PipelineConfig(embed=request.embed)
    pipeline = Pipeline(config)

    result = await pipeline.compare(content, doc.filename, request.strategies, embed=request.embed)

    strategies_response = {}
    for name, report in result.strategies.items():
        strategies_response[name] = QualityReportResponse(
            total_chunks=report.total_chunks,
            total_tokens=report.total_tokens,
            avg_tokens=report.avg_tokens,
            min_tokens=report.min_tokens,
            max_tokens=report.max_tokens,
            by_type=report.by_type,
            by_section=report.by_section,
        )

    return ComparisonResponse(
        document_id=str(request.document_id),
        strategies=strategies_response,
        sample_chunks=result.sample_chunks,
    )
