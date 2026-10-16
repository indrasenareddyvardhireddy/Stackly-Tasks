"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE = ("Admin", "Agent", "Customer")
AVAILABILITY = ("Online", "Offline")
PRIORITY = ("Low", "Medium", "High", "Urgent")  # order matters for sorting
STATUS = ("Open", "Assigned", "In Progress", "Waiting on Customer", "Resolved", "Closed")


def ts():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum(*ROLE, name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *ts(),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *ts(),
        sa.UniqueConstraint("category_name", name="uq_categories_category_name"),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("priority", sa.Enum(*PRIORITY, name="sla_priority"), nullable=False),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        *ts(),
        sa.UniqueConstraint("priority", name="uq_sla_policies_priority"),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "agent_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("availability", sa.Enum(*AVAILABILITY, name="availability"), nullable=False, server_default="Offline"),
        sa.Column("max_open_tickets", sa.Integer(), nullable=False, server_default="10"),
        *ts(),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "agent_categories",
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agent_profiles.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
        *ts(),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_number", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.Enum(*PRIORITY, name="ticket_priority"), nullable=False, server_default="Medium"),
        sa.Column("status", sa.Enum(*STATUS, name="ticket_status"), nullable=False, server_default="Open"),
        sa.Column("assigned_agent_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_response_due", sa.DateTime(), nullable=False),
        sa.Column("resolution_due", sa.DateTime(), nullable=False),
        sa.Column("first_response_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_response_breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution_breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_response_escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution_escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("waiting_since", sa.DateTime(), nullable=True),
        sa.Column("paused_seconds", sa.Integer(), nullable=False, server_default="0"),
        *ts(),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_tickets_ticket_number", "tickets", ["ticket_number"], unique=True)
    op.create_index("ix_tickets_status", "tickets", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_role", sa.Enum(*ROLE, name="user_role"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_internal_note", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        *ts(),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("old_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=True),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        *ts(),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        *ts(),
        sa.UniqueConstraint("ticket_id", name="uq_feedback_ticket_id"),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        *ts(),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])

    # default SLA policies (minutes)
    sla = sa.table(
        "sla_policies",
        sa.column("priority", sa.String),
        sa.column("first_response_minutes", sa.Integer),
        sa.column("resolution_minutes", sa.Integer),
    )
    op.bulk_insert(
        sla,
        [
            {"priority": "Low", "first_response_minutes": 24 * 60, "resolution_minutes": 72 * 60},
            {"priority": "Medium", "first_response_minutes": 8 * 60, "resolution_minutes": 48 * 60},
            {"priority": "High", "first_response_minutes": 2 * 60, "resolution_minutes": 24 * 60},
            {"priority": "Urgent", "first_response_minutes": 30, "resolution_minutes": 8 * 60},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    for table in (
        "notifications", "feedback", "ticket_status_history", "messages", "tickets",
        "agent_categories", "agent_profiles", "sla_policies", "categories", "users",
    ):
        op.drop_table(table)
