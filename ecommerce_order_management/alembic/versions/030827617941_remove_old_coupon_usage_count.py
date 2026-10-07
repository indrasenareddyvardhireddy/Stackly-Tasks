"""remove old coupon usage count

Revision ID: 030827617941
Revises: 3c6bd6f45336
Create Date: 2026-10-07 11:39:35.635542
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "030827617941"
down_revision: Union[str, None] = "3c6bd6f45336"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove the old column that is no longer used by the application
    op.drop_column("coupons", "usage_count")


def downgrade() -> None:
    # Restore the old column if this migration is rolled back
    op.add_column(
        "coupons",
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default="0"
        )
    )