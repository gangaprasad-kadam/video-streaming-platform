"""create video_summaries table

Revision ID: 0001
Revises:
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table(
        "video_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("transcript", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column(
            "key_moments",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_summaries_video_id", "video_summaries", ["video_id"])


def downgrade() -> None:
    op.drop_index("idx_summaries_video_id", table_name="video_summaries")
    op.drop_table("video_summaries")
