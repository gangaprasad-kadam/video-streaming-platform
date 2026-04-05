"""create videos table

Revision ID: 0001
Revises:
Create Date: 2026-04-05

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
    op.execute("CREATE TYPE video_status AS ENUM ('uploading', 'processing', 'ready', 'failed')")

    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("hls_path", sa.Text, nullable=True),
        sa.Column("thumbnail_path", sa.Text, nullable=True),
        sa.Column("duration", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.Enum("uploading", "processing", "ready", "failed",
                                    name="video_status"), nullable=False, server_default="uploading"),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_videos_creator", "videos", ["creator_id"])
    op.create_index("idx_videos_status", "videos", ["status"])
    op.create_index("idx_videos_created_at", "videos", ["created_at"], postgresql_ops={"created_at": "DESC"})


def downgrade() -> None:
    op.drop_index("idx_videos_created_at", table_name="videos")
    op.drop_index("idx_videos_status", table_name="videos")
    op.drop_index("idx_videos_creator", table_name="videos")
    op.drop_table("videos")
    op.execute("DROP TYPE video_status")
