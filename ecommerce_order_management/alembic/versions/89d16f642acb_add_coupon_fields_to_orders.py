"""add coupon fields to orders

Revision ID: 89d16f642acb
Revises: dd9bdc0149e5
Create Date: 2026-10-07 10:17:29.662709
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "89d16f642acb"
down_revision: Union[str, None] = "dd9bdc0149e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add coupon reference
    op.add_column(
        "orders",
        sa.Column(
            "coupon_id",
            sa.Integer(),
            nullable=True
        )
    )

    # Add discount amount.
    # Default 0.00 keeps existing orders valid.
    op.add_column(
        "orders",
        sa.Column(
            "discount_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0.00"
        )
    )

    # Create a named foreign key
    op.create_foreign_key(
        "fk_orders_coupon_id",
        "orders",
        "coupons",
        ["coupon_id"],
        ["id"]
    )


def downgrade() -> None:
    # Drop the named foreign key first
    op.drop_constraint(
        "fk_orders_coupon_id",
        "orders",
        type_="foreignkey"
    )

    # Remove the columns
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "coupon_id")