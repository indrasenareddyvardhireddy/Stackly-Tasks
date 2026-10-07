"""add coupon used count

Revision ID: 3c6bd6f45336
Revises: 89d16f642acb
Create Date: 2026-10-07 11:31:41.530384
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c6bd6f45336"
down_revision: Union[str, None] = "89d16f642acb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "coupons",
        sa.Column(
            "used_count",
            sa.Integer(),
            nullable=False,
            server_default="0"
        )
    )


def downgrade() -> None:
    op.drop_column(
        "coupons",
        "used_count"
    )