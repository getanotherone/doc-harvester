"""Stage 3 minimal model endpoint — returns chunks in the proven 12-field schema."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.api.schemas import Stage3ChunkResponse
from doc_proc.db.models import Chunk, Document
from doc_proc.db.session import get_db

router = APIRouter()


@router.get("/{document_id}", response_model=list[Stage3ChunkResponse])
async def get_stage3_output(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get Stage 3 minimal model output for all chunks of a document."""
    # Verify document exists
    doc = (
        await db.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Fetch chunks ordered by index
    stmt = (
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return [
        Stage3ChunkResponse(
            document=doc.filename,
            page=c.page or 0,
            section=c.section or "",
            chunk_index=c.chunk_index,
            text=c.text,
            doc_type=c.doc_type or "technical",
            vendor=c.vendor or "",
            standard_id=c.standard_id or "",
            year=None,  # Not stored in DB yet, extracted at runtime if needed
            lang=c.lang or "unknown",
            source_type=doc.file_type or "unknown",
            quality_status="pass" if c.embedding is not None else "unknown",
        )
        for c in chunks
    ]
