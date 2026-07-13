"""Stage 3 minimal model output — proven 12-field schema for downstream pipelines.

This schema is used for fast ingestion into vector storage, unified format
for evaluation, and simple transmission to RAG/ETL without internal fields.
"""

from __future__ import annotations

from typing import Any


def to_stage3_minimal(
    *,
    text: str,
    document: str = "",
    page: int = 0,
    section: str = "",
    chunk_index: int = 0,
    doc_type: str = "technical",
    vendor: str = "",
    standard_id: str = "",
    year: int | None = None,
    lang: str = "unknown",
    source_type: str = "unknown",
    quality_status: str = "unknown",
) -> dict[str, Any]:
    """Build Stage 3 minimal model dict.

    Returns the proven 12-field minimal schema used by downstream pipelines.
    """
    return {
        "document": document,
        "page": page,
        "section": section,
        "chunk_index": chunk_index,
        "text": text,
        "doc_type": doc_type,
        "vendor": vendor,
        "standard_id": standard_id,
        "year": year,
        "lang": lang,
        "source_type": source_type,
        "quality_status": quality_status,
    }
