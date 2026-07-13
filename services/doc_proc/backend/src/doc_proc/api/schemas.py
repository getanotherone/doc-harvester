"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Documents ---

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    source_type: str | None = None
    page_count: int | None = None
    tables_count: int | None = None
    has_ocr: bool = False
    total_rows: int | None = None
    parse_metadata: dict | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    task_id: str
    document_id: uuid.UUID
    filename: str
    status: str


class TextInputRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    title: str = Field(min_length=1, max_length=500)
    strategy: str = "auto"


class TextInputResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    chunk_count: int


# --- Chunks ---

class ChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    chunk_type: str
    text: str
    context_header: str | None = None
    section: str | None = None
    page: int | None = None
    token_count: int | None = None
    strategy_used: str | None = None
    has_embedding: bool = False
    # Domain metadata
    vendor: str | None = None
    standard_id: str | None = None
    doc_type: str | None = None
    lang: str | None = None
    block_types: list[str] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChunkUpdateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


class ChunkCreateRequest(BaseModel):
    document_id: uuid.UUID
    text: str = Field(min_length=1)
    chunk_type: str = "text"
    section: str | None = None
    page: int | None = None


class ChunkMergeRequest(BaseModel):
    chunk_ids: list[uuid.UUID] = Field(min_length=2, max_length=20)
    separator: str = "\n\n"


class ChunkSplitRequest(BaseModel):
    split_positions: list[int] | None = None
    split_pattern: str | None = None


class ChunkQualityResponse(BaseModel):
    chunk_id: str
    text_length: int = 0
    token_count: int = 0
    text_density: float = 0.0
    embedding_norm: float | None = None
    avg_neighbor_similarity: float | None = None


class Stage3ChunkResponse(BaseModel):
    """Stage 3 minimal model — 12-field schema for downstream pipelines."""

    document: str
    page: int = 0
    section: str = ""
    chunk_index: int = 0
    text: str
    doc_type: str = "technical"
    vendor: str = ""
    standard_id: str = ""
    year: int | None = None
    lang: str = "unknown"
    source_type: str = "unknown"
    quality_status: str = "unknown"


class ChunkListResponse(BaseModel):
    chunks: list[ChunkResponse]
    total: int
    limit: int
    offset: int


# --- Search ---

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    document_id: uuid.UUID | None = None
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    id: uuid.UUID
    text: str
    section: str | None = None
    chunk_type: str
    page: int | None = None
    document_id: uuid.UUID
    filename: str | None = None
    similarity: float


# --- Pipeline ---

class PipelineRunRequest(BaseModel):
    document_id: uuid.UUID
    strategy: str = "auto"
    embed: bool = True


class PipelineCompareRequest(BaseModel):
    document_id: uuid.UUID
    strategies: list[str] = Field(min_length=1, max_length=5)
    embed: bool = False


class StrategyInfo(BaseModel):
    name: str
    description: str


class QualityReportResponse(BaseModel):
    total_chunks: int = 0
    total_tokens: int = 0
    avg_tokens: float = 0.0
    min_tokens: int = 0
    max_tokens: int = 0
    by_type: dict[str, int] = {}
    by_section: dict[str, int] = {}


class ComparisonResponse(BaseModel):
    document_id: str
    strategies: dict[str, QualityReportResponse] = {}
    sample_chunks: dict[str, list[dict]] = {}


# --- Queue ---

class QueueTaskResponse(BaseModel):
    task_id: str
    document_id: str
    filename: str
    status: str
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    retry_count: int = 0
    progress_percent: int = 0
    current_step: str = ""
    steps_detail: dict = {}


class QueueStatsResponse(BaseModel):
    queue_length: int = 0
    processing: int = 0
    total_enqueued: int = 0
    total_completed: int = 0
    total_failed: int = 0


# --- Methodology ---

class MethodologyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    file_types: list[str] | None = None
    config: dict | None = None


class MethodologyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    file_types: list[str] | None = None
    config: dict | None = None
    is_default: bool | None = None


class MethodologyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    file_types: list | None = None
    is_default: bool = False
    config: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
