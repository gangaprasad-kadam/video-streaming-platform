"""create watch_history table

Revision ID: 001
Revises:
Create Date: 2024-04-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watch_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("video_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column(
            "watched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "video_id", name="uq_user_video"),
    )


def downgrade() -> None:
    op.drop_table("watch_history")
