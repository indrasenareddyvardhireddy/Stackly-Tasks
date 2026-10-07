"""remove old coupon is active

Revision ID: 6c04292b6cf3
Revises: 030827617941
Create Date: 2026-10-07 11:45:57.381813
"""
"""remove old coupon is active

Revision ID: YOUR_NEW_REVISION_ID
Revises: 030827617941
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "YOUR_NEW_REVISION_ID"
down_revision: Union[str, None] = "030827617941"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("coupons", "is_active")


def downgrade() -> None:
    op.add_column(
        "coupons",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="1"
        )
    )