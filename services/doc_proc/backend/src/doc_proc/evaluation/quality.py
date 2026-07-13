"""Chunk quality evaluation — density, embedding norm, neighbor similarity."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.db.models import Chunk


async def get_chunk_quality(db: AsyncSession, chunk_id: str) -> dict:
    """Compute quality metrics for a single chunk."""
    stmt = select(Chunk).where(Chunk.id == chunk_id)
    result = await db.execute(stmt)
    chunk = result.scalar_one_or_none()
    if not chunk:
        return {}

    text_content = chunk.text or ""
    non_ws = sum(1 for c in text_content if not c.isspace())
    text_density = non_ws / max(len(text_content), 1)

    embedding_norm = None
    if chunk.embedding is not None:
        embedding_norm = float(np.linalg.norm(chunk.embedding))

    # Neighbor similarity (±2 adjacent chunks)
    avg_neighbor_sim = await _avg_neighbor_similarity(db, chunk)

    return {
        "chunk_id": str(chunk.id),
        "text_length": len(text_content),
        "token_count": chunk.token_count or 0,
        "text_density": round(text_density, 3),
        "embedding_norm": round(embedding_norm, 3) if embedding_norm else None,
        "avg_neighbor_similarity": round(avg_neighbor_sim, 3) if avg_neighbor_sim else None,
    }


async def _avg_neighbor_similarity(db: AsyncSession, chunk: Chunk) -> float | None:
    """Compute average cosine similarity to ±2 adjacent chunks."""
    if chunk.embedding is None:
        return None

    vector_literal = "[" + ",".join(str(float(v)) for v in chunk.embedding) + "]"

    sql = text("""
        SELECT 1 - (embedding <=> CAST(:vector AS vector)) AS similarity
        FROM chunks
        WHERE document_id = :doc_id
          AND id != :chunk_id
          AND chunk_index BETWEEN :min_idx AND :max_idx
          AND embedding IS NOT NULL
        ORDER BY chunk_index
        LIMIT 4
    """)

    result = await db.execute(sql, {
        "vector": vector_literal,
        "doc_id": str(chunk.document_id),
        "chunk_id": str(chunk.id),
        "min_idx": chunk.chunk_index - 2,
        "max_idx": chunk.chunk_index + 2,
    })
    rows = result.fetchall()
    if not rows:
        return None
    return sum(r[0] for r in rows) / len(rows)
