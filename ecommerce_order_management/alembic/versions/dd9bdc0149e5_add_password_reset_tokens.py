"""add password reset tokens

Revision ID: dd9bdc0149e5
Revises: a277a040ce76
Create Date: 2026-10-06 11:17:47.110560
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dd9bdc0149e5"
down_revision: Union[str, None] = "a277a040ce76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",

        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "token_hash",
            sa.String(length=128),
            nullable=False
        ),

        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "used_at",
            sa.DateTime(),
            nullable=True
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"]
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "token_hash"
        )
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")