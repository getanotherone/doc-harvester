"""Add domain metadata columns to chunks table.

Revision ID: 002
Revises: 001
Create Date: 2026-04-15
"""

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("vendor", sa.String(50), nullable=True))
    op.add_column("chunks", sa.Column("standard_id", sa.String(200), nullable=True))
    op.add_column("chunks", sa.Column("doc_type", sa.String(30), nullable=True))
    op.add_column("chunks", sa.Column("lang", sa.String(10), nullable=True))
    op.add_column("chunks", sa.Column("block_types", sa.JSON(), nullable=True))

    # Index for filtering by doc_type and vendor
    op.create_index("ix_chunks_doc_type", "chunks", ["doc_type"])
    op.create_index("ix_chunks_vendor", "chunks", ["vendor"])


def downgrade() -> None:
    op.drop_index("ix_chunks_vendor")
    op.drop_index("ix_chunks_doc_type")
    op.drop_column("chunks", "block_types")
    op.drop_column("chunks", "lang")
    op.drop_column("chunks", "doc_type")
    op.drop_column("chunks", "standard_id")
    op.drop_column("chunks", "vendor")
