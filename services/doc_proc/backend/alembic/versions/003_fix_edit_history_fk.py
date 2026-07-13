"""Fix ChunkEditHistory FK: SET NULL instead of CASCADE to preserve audit trail.

Revision ID: 003
Revises: 002
Create Date: 2026-04-15
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old FK and recreate with SET NULL
    op.drop_constraint(
        "chunk_edit_history_chunk_id_fkey", "chunk_edit_history", type_="foreignkey"
    )
    op.alter_column("chunk_edit_history", "chunk_id", nullable=True)
    op.create_foreign_key(
        "chunk_edit_history_chunk_id_fkey",
        "chunk_edit_history",
        "chunks",
        ["chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "chunk_edit_history_chunk_id_fkey", "chunk_edit_history", type_="foreignkey"
    )
    op.alter_column("chunk_edit_history", "chunk_id", nullable=False)
    op.create_foreign_key(
        "chunk_edit_history_chunk_id_fkey",
        "chunk_edit_history",
        "chunks",
        ["chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
