"""SQLAlchemy ORM models for document processing."""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from doc_proc.config import settings
from doc_proc.db.base import Base
from doc_proc.db.enums import ChunkType, DocumentStatus, SourceType


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    """Uploaded document and its processing state."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(default=_uuid, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(Text, default="")
    file_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        SAEnum(DocumentStatus, native_enum=False, length=20),
        default=DocumentStatus.uploaded,
    )
    source_type: Mapped[str | None] = mapped_column(
        SAEnum(SourceType, native_enum=False, length=20),
        nullable=True,
        default=SourceType.upload,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tables_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Document chunk with embedding vector."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(default=_uuid, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_type: Mapped[str] = mapped_column(
        SAEnum(ChunkType, native_enum=False, length=20),
        default=ChunkType.text,
    )
    text: Mapped[str] = mapped_column(Text)
    context_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    section: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimension), nullable=True
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Domain metadata (electrical engineering)
    vendor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    standard_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    lang: Mapped[str | None] = mapped_column(String(10), nullable=True)
    block_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
    edit_history: Mapped[list["ChunkEditHistory"]] = relationship(
        back_populates="chunk",
    )


class ChunkEditHistory(Base):
    """Tracks chunk modifications for undo support."""

    __tablename__ = "chunk_edit_history"

    id: Mapped[uuid.UUID] = mapped_column(default=_uuid, primary_key=True)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(30))
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edit_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    chunk: Mapped["Chunk"] = relationship(back_populates="edit_history")


class Methodology(Base):
    """Reusable document processing configuration."""

    __tablename__ = "methodologies"

    id: Mapped[uuid.UUID] = mapped_column(default=_uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_now
    )
