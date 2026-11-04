"""Persistent auth state: revoked refresh tokens, WebSocket tickets, rate-limit events.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("at", sa.Float(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("rate_limit_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rate_limit_events_at"), ["at"], unique=False)
        batch_op.create_index(batch_op.f("ix_rate_limit_events_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_rate_limit_events_key"), ["key"], unique=False)

    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("revoked_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_revoked_tokens_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_revoked_tokens_jti"), ["jti"], unique=True)

    op.create_table(
        "ws_tickets",
        sa.Column("ticket", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("used_at", sa.Float(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ws_tickets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ws_tickets_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ws_tickets_ticket"), ["ticket"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("rate_limit_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rate_limit_events_key"))
        batch_op.drop_index(batch_op.f("ix_rate_limit_events_id"))
        batch_op.drop_index(batch_op.f("ix_rate_limit_events_at"))

    op.drop_table("rate_limit_events")
    with op.batch_alter_table("revoked_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revoked_tokens_jti"))
        batch_op.drop_index(batch_op.f("ix_revoked_tokens_id"))

    op.drop_table("revoked_tokens")
    with op.batch_alter_table("ws_tickets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ws_tickets_ticket"))
        batch_op.drop_index(batch_op.f("ix_ws_tickets_id"))

    op.drop_table("ws_tickets")
