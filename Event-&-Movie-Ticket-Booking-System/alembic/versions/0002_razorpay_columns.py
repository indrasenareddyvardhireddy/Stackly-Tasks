"""razorpay columns

Revision ID: 0002_razorpay
Revises: 0001_initial
Create Date: 2026-10-27 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_razorpay"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("razorpay_order_id", sa.String(40), nullable=True))
    op.create_index("ix_bookings_razorpay_order_id", "bookings", ["razorpay_order_id"])
    op.add_column("payments", sa.Column("razorpay_order_id", sa.String(40), nullable=True))
    op.add_column("payments", sa.Column("razorpay_payment_id", sa.String(40), nullable=True))
    op.add_column("payments", sa.Column("razorpay_signature", sa.String(200), nullable=True))
    op.create_unique_constraint("uq_payments_razorpay_payment_id", "payments", ["razorpay_payment_id"])


def downgrade() -> None:
    op.drop_constraint("uq_payments_razorpay_payment_id", "payments", type_="unique")
    op.drop_column("payments", "razorpay_signature")
    op.drop_column("payments", "razorpay_payment_id")
    op.drop_column("payments", "razorpay_order_id")
    op.drop_index("ix_bookings_razorpay_order_id", table_name="bookings")
    op.drop_column("bookings", "razorpay_order_id")
