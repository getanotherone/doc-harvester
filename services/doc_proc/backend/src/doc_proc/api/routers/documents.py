"""Document management endpoints — upload, list, detail, delete."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.api.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    TextInputRequest,
    TextInputResponse,
)
from doc_proc.config import settings
from doc_proc.db.enums import DocumentStatus, SourceType
from doc_proc.db.models import Chunk, Document
from doc_proc.db.session import get_db

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for async processing."""
    if not file.filename:
        raise HTTPException(400, "Filename required")

    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if ext not in ("pdf", "xlsx", "xls", "csv", "docx", "pptx"):
        raise HTTPException(400, f"Unsupported format: .{ext}")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            400,
            f"File too large: {size_mb:.1f} MB "
            f"(max {settings.max_upload_size_mb} MB)",
        )

    # Create document record
    doc_id = uuid.uuid4()
    file_path = f"docs/{doc_id}/{file.filename}"

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=file_path,
        file_type=ext,
        source_type=SourceType.upload,
    )
    db.add(doc)
    await db.flush()

    # Upload to MinIO
    from doc_proc.storage.minio import upload_file
    upload_file(file_path, content)

    # Enqueue for processing
    from doc_proc.queue.service import DocumentQueueService
    queue = DocumentQueueService()
    try:
        task = await queue.enqueue(
            document_id=str(doc_id),
            filename=file.filename,
            file_path=file_path,
        )
    finally:
        await queue.close()

    await db.commit()

    return DocumentUploadResponse(
        task_id=task.task_id,
        document_id=doc_id,
        filename=file.filename,
        status="queued",
    )


@router.post("/text", response_model=TextInputResponse)
async def create_from_text(
    request: TextInputRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a document from text/markdown content (sync processing)."""
    from doc_proc.embedding.factory import create_embedding_provider
    from doc_proc.models import ParsedElement, ParseResult, estimate_tokens
    from doc_proc.pipeline import Pipeline, PipelineConfig

    doc_id = uuid.uuid4()

    # Store in MinIO
    from doc_proc.storage.minio import upload_file
    file_path = f"docs/{doc_id}/{request.title}.md"
    upload_file(file_path, request.text.encode("utf-8"), "text/markdown")

    doc = Document(
        id=doc_id,
        filename=f"{request.title}.md",
        file_path=file_path,
        file_type="md",
        source_type=SourceType.text,
        status=DocumentStatus.processing,
    )
    db.add(doc)
    await db.flush()

    # Build ParseResult from text
    paragraphs = [p.strip() for p in request.text.split("\n\n") if p.strip()]
    elements = [
        ParsedElement(index=i, text=p, element_type="text")
        for i, p in enumerate(paragraphs)
    ]
    parse_result = ParseResult(elements=elements, format_hint="document")

    # Run pipeline (chunk only, then embed)
    config = PipelineConfig(strategy=request.strategy, embed=False, doc_title=request.title)
    pipeline = Pipeline(config)
    chunk_result = pipeline.chunk(parse_result)

    # Embed and save
    embedder = create_embedding_provider()
    texts = [c.text for c in chunk_result.chunks]
    embeddings = await embedder.embed_batch(texts) if texts else []

    for i, (chunk, emb) in enumerate(zip(chunk_result.chunks, embeddings)):
        db_chunk = Chunk(
            document_id=doc_id,
            chunk_index=i,
            chunk_type=chunk.chunk_type,
            text=chunk.text,
            context_header=chunk.context_header or None,
            section=chunk.section or None,
            embedding=emb,
            token_count=chunk.token_count or estimate_tokens(chunk.text),
            strategy_used=chunk_result.strategy_used,
        )
        db.add(db_chunk)

    doc.status = DocumentStatus.completed
    doc.completed_at = datetime.now(UTC)
    doc.total_rows = len(elements)
    await db.commit()

    return TextInputResponse(
        document_id=doc_id,
        title=request.title,
        chunk_count=len(chunk_result.chunks),
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.delete("/{doc_id}")
async def delete_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    await db.delete(doc)
    await db.commit()

    # Delete from MinIO
    try:
        from doc_proc.storage.minio import delete_file
        delete_file(doc.file_path)
    except Exception:
        pass  # Non-fatal

    return {"deleted": True}
