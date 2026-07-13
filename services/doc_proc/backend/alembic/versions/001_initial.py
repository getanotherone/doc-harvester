"""Initial schema — documents, chunks, methodologies, edit history.

Revision ID: 001
Create Date: 2026-04-14
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.Text(), server_default=""),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="uploaded"),
        sa.Column("source_type", sa.String(20), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("tables_count", sa.Integer(), nullable=True),
        sa.Column("has_ocr", sa.Boolean(), server_default="false"),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("parse_metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(20), server_default="text"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("context_header", sa.Text(), nullable=True),
        sa.Column("section", sa.String(1000), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("strategy_used", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 32, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "chunk_edit_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=True),
        sa.Column("new_text", sa.Text(), nullable=True),
        sa.Column("old_token_count", sa.Integer(), nullable=True),
        sa.Column("new_token_count", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_chunk_edit_history_chunk_id", "chunk_edit_history", ["chunk_id"]
    )

    op.create_table(
        "methodologies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_types", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("chunk_edit_history")
    op.drop_table("chunks")
    op.drop_table("methodologies")
    op.drop_table("documents")
