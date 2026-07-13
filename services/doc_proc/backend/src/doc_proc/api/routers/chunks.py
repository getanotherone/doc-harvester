"""Chunk CRUD endpoints — list, create, update, delete, merge, split, search."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.api.schemas import (
    ChunkCreateRequest,
    ChunkListResponse,
    ChunkMergeRequest,
    ChunkQualityResponse,
    ChunkResponse,
    ChunkSplitRequest,
    ChunkUpdateRequest,
    SearchRequest,
    SearchResult,
)
from doc_proc.db.models import Chunk, ChunkEditHistory
from doc_proc.db.session import get_db
from doc_proc.models import estimate_tokens

router = APIRouter()


def _chunk_to_response(chunk: Chunk) -> ChunkResponse:
    return ChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        chunk_type=chunk.chunk_type,
        text=chunk.text,
        context_header=chunk.context_header,
        section=chunk.section,
        page=chunk.page,
        token_count=chunk.token_count,
        strategy_used=chunk.strategy_used,
        has_embedding=chunk.embedding is not None,
        vendor=chunk.vendor,
        standard_id=chunk.standard_id,
        doc_type=chunk.doc_type,
        lang=chunk.lang,
        block_types=chunk.block_types,
        created_at=chunk.created_at,
    )


@router.get("", response_model=ChunkListResponse)
async def list_chunks(
    document_id: uuid.UUID | None = None,
    chunk_type: str | None = None,
    section: str | None = None,
    full_text: bool = False,
    limit: int = Query(default=50, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Chunk)
    count_stmt = select(func.count(Chunk.id))

    if document_id:
        stmt = stmt.where(Chunk.document_id == document_id)
        count_stmt = count_stmt.where(Chunk.document_id == document_id)
    if chunk_type:
        stmt = stmt.where(Chunk.chunk_type == chunk_type)
        count_stmt = count_stmt.where(Chunk.chunk_type == chunk_type)
    if section:
        stmt = stmt.where(Chunk.section == section)
        count_stmt = count_stmt.where(Chunk.section == section)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(Chunk.chunk_index).limit(limit).offset(offset)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    responses = []
    for c in chunks:
        resp = _chunk_to_response(c)
        if not full_text:
            resp.text = resp.text[:200]
        responses.append(resp)

    return ChunkListResponse(chunks=responses, total=total, limit=limit, offset=offset)


@router.post("", response_model=ChunkResponse)
async def create_chunk(
    request: ChunkCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    # Get next chunk_index
    stmt = select(func.coalesce(func.max(Chunk.chunk_index), -1)).where(
        Chunk.document_id == request.document_id
    )
    max_idx = (await db.execute(stmt)).scalar() or -1

    from doc_proc.embedding.factory import create_embedding_provider
    embedder = create_embedding_provider()
    embedding = await embedder.embed(request.text)

    chunk = Chunk(
        document_id=request.document_id,
        chunk_index=max_idx + 1,
        chunk_type=request.chunk_type,
        text=request.text,
        section=request.section,
        page=request.page,
        embedding=embedding,
        token_count=estimate_tokens(request.text),
    )
    db.add(chunk)

    history = ChunkEditHistory(
        chunk_id=chunk.id,
        action="create",
        new_text=request.text,
        new_token_count=chunk.token_count,
    )
    db.add(history)
    await db.flush()
    await db.refresh(chunk)
    return _chunk_to_response(chunk)


@router.get("/{chunk_id}", response_model=ChunkResponse)
async def get_chunk(chunk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    chunk = (await db.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    return _chunk_to_response(chunk)


@router.put("/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(
    chunk_id: uuid.UUID,
    request: ChunkUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    chunk = (await db.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "Chunk not found")

    old_text = chunk.text
    old_tokens = chunk.token_count

    from doc_proc.embedding.factory import create_embedding_provider
    embedder = create_embedding_provider()

    embed_text = (
        f"{chunk.context_header}\n\n{request.text}"
        if chunk.context_header
        else request.text
    )
    embedding = await embedder.embed(embed_text)

    chunk.text = request.text
    chunk.embedding = embedding
    chunk.token_count = estimate_tokens(request.text)

    history = ChunkEditHistory(
        chunk_id=chunk.id,
        action="edit",
        old_text=old_text,
        new_text=request.text,
        old_token_count=old_tokens,
        new_token_count=chunk.token_count,
    )
    db.add(history)
    await db.flush()
    await db.refresh(chunk)
    return _chunk_to_response(chunk)


@router.delete("/{chunk_id}")
async def delete_chunk(chunk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    chunk = (await db.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "Chunk not found")

    history = ChunkEditHistory(
        chunk_id=chunk.id,
        action="delete",
        old_text=chunk.text,
        old_token_count=chunk.token_count,
        edit_metadata={"section": chunk.section, "chunk_type": chunk.chunk_type},
    )
    db.add(history)
    await db.delete(chunk)
    return {"deleted": True}


@router.post("/merge", response_model=ChunkResponse)
async def merge_chunks(
    request: ChunkMergeRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Chunk).where(Chunk.id.in_(request.chunk_ids)).order_by(Chunk.chunk_index)
    result = await db.execute(stmt)
    chunks = list(result.scalars().all())

    if len(chunks) < 2:
        raise HTTPException(400, "Need at least 2 chunks to merge")

    doc_ids = {c.document_id for c in chunks}
    if len(doc_ids) > 1:
        raise HTTPException(400, "All chunks must belong to the same document")

    merged_text = request.separator.join(c.text for c in chunks)

    from doc_proc.embedding.factory import create_embedding_provider
    embedder = create_embedding_provider()
    embedding = await embedder.embed(merged_text)

    new_chunk = Chunk(
        document_id=chunks[0].document_id,
        chunk_index=chunks[0].chunk_index,
        chunk_type=chunks[0].chunk_type,
        text=merged_text,
        section=chunks[0].section,
        embedding=embedding,
        token_count=estimate_tokens(merged_text),
        strategy_used="merge",
    )
    db.add(new_chunk)

    for c in chunks:
        await db.delete(c)

    await db.flush()
    await db.refresh(new_chunk)
    return _chunk_to_response(new_chunk)


@router.post("/{chunk_id}/split", response_model=list[ChunkResponse])
async def split_chunk(
    chunk_id: uuid.UUID,
    request: ChunkSplitRequest,
    db: AsyncSession = Depends(get_db),
):
    chunk = (await db.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "Chunk not found")

    import re
    text_val = chunk.text

    if request.split_positions:
        parts = []
        prev = 0
        for pos in sorted(request.split_positions):
            if 0 < pos < len(text_val):
                parts.append(text_val[prev:pos])
                prev = pos
        parts.append(text_val[prev:])
        parts = [p.strip() for p in parts if p.strip()]
    elif request.split_pattern:
        parts = re.split(request.split_pattern, text_val)
        parts = [p.strip() for p in parts if p.strip()]
    else:
        raise HTTPException(400, "Provide split_positions or split_pattern")

    if len(parts) < 2:
        raise HTTPException(400, "Split produces fewer than 2 parts")

    from doc_proc.embedding.factory import create_embedding_provider
    embedder = create_embedding_provider()
    embeddings = await embedder.embed_batch(parts)

    # Shift subsequent chunk indices to make room for split parts
    extra_slots = len(parts) - 1
    if extra_slots > 0:
        shift_stmt = text(
            "UPDATE chunks SET chunk_index = chunk_index + :shift "
            "WHERE document_id = :doc_id AND chunk_index > :split_idx"
        )
        await db.execute(shift_stmt, {
            "shift": extra_slots,
            "doc_id": str(chunk.document_id),
            "split_idx": chunk.chunk_index,
        })

    new_chunks = []
    for i, (part, emb) in enumerate(zip(parts, embeddings)):
        new_chunk = Chunk(
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index + i,
            chunk_type=chunk.chunk_type,
            text=part,
            section=chunk.section,
            embedding=emb,
            token_count=estimate_tokens(part),
            strategy_used="split",
        )
        db.add(new_chunk)
        new_chunks.append(new_chunk)

    await db.delete(chunk)
    await db.flush()
    for c in new_chunks:
        await db.refresh(c)
    return [_chunk_to_response(c) for c in new_chunks]


@router.get("/{chunk_id}/quality", response_model=ChunkQualityResponse)
async def get_chunk_quality_endpoint(
    chunk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from doc_proc.evaluation.quality import get_chunk_quality
    result = await get_chunk_quality(db, str(chunk_id))
    if not result:
        raise HTTPException(404, "Chunk not found")
    return result


@router.post("/search", response_model=list[SearchResult])
async def search_chunks(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    from doc_proc.embedding.factory import create_embedding_provider
    embedder = create_embedding_provider()
    query_embedding = await embedder.embed(request.query)
    vector_literal = "[" + ",".join(str(float(v)) for v in query_embedding) + "]"

    sql = """
        SELECT c.id, c.text, c.section, c.chunk_type, c.page, c.document_id,
               d.filename,
               1 - (c.embedding <=> CAST(:vector AS vector)) AS similarity
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
          AND 1 - (c.embedding <=> CAST(:vector AS vector)) >= :min_sim
    """
    params: dict = {"vector": vector_literal, "min_sim": request.min_similarity}

    if request.document_id:
        sql += " AND c.document_id = :doc_id"
        params["doc_id"] = str(request.document_id)

    sql += " ORDER BY similarity DESC LIMIT :limit"
    params["limit"] = request.limit

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        SearchResult(
            id=row[0], text=row[1][:500], section=row[2], chunk_type=row[3],
            page=row[4], document_id=row[5], filename=row[6], similarity=round(row[7], 4),
        )
        for row in rows
    ]
