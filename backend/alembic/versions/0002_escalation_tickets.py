"""escalation tickets table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "escalation_tickets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "resolved", name="ticket_status_enum"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("context_chunks", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_escalation_tickets_conversation_id", "escalation_tickets", ["conversation_id"])
    op.create_index("ix_escalation_tickets_session_id", "escalation_tickets", ["session_id"])
    op.create_index("ix_escalation_tickets_status", "escalation_tickets", ["status"])


def downgrade() -> None:
    op.drop_table("escalation_tickets")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
