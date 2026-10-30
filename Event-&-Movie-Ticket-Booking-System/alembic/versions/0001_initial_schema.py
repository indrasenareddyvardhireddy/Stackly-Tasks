"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-26 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _ts():
    """created_at / updated_at for every table."""
    return [
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_venues_city", "venues", ["city"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=True),
        *_ts(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "screens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("total_seats", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )

    op.create_table(
        "seats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("screen_id", sa.Integer(), sa.ForeignKey("screens.id"), nullable=False),
        sa.Column("row_label", sa.String(5), nullable=False),
        sa.Column("seat_number", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
        sa.UniqueConstraint("screen_id", "row_label", "seat_number", name="uq_seat_position"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organizer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("age_rating", sa.String(5), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        *_ts(),
    )
    op.create_index("ix_events_status", "events", ["status"])

    op.create_table(
        "shows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("screen_id", sa.Integer(), sa.ForeignKey("screens.id"), nullable=False),
        sa.Column("show_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("booking_closes_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Scheduled"),
        *_ts(),
    )
    op.create_index("ix_shows_show_date", "shows", ["show_date"])
    op.create_index("ix_shows_start_at", "shows", ["start_at"])

    op.create_table(
        "seat_category_prices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        *_ts(),
        sa.UniqueConstraint("show_id", "category", name="uq_show_category_price"),
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("booking_number", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("ticket_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("convenience_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("gst_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending Payment"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
        sa.UniqueConstraint("booking_number", name="uq_bookings_booking_number"),
    )
    op.create_index("ix_bookings_status", "bookings", ["status"])

    op.create_table(
        "booked_seats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False),
        sa.Column("seat_id", sa.Integer(), sa.ForeignKey("seats.id"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("confirmed_seat_id", sa.Integer(), nullable=True),
        *_ts(),
        # a seat can be confirmed only once per show (NULL = pending / cancelled, may repeat)
        sa.UniqueConstraint("show_id", "confirmed_seat_id", name="uq_confirmed_seat_per_show"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("transaction_id", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        *_ts(),
        sa.UniqueConstraint("transaction_id", name="uq_payments_transaction_id"),
    )

    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Processed"),
        sa.Column("refunded_at", sa.DateTime(), nullable=False),
        *_ts(),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("qr_value", sa.String(100), nullable=False),
        sa.Column("pdf_path", sa.String(255), nullable=True),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("scanned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        *_ts(),
        sa.UniqueConstraint("booking_id", name="uq_tickets_booking_id"),
    )

    op.create_table(
        "waitlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("show_id", sa.Integer(), sa.ForeignKey("shows.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("seats_requested", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Waiting"),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        *_ts(),
        sa.UniqueConstraint("show_id", "customer_id", name="uq_waitlist_show_customer"),
    )


def downgrade() -> None:
    for table in ("waitlist", "tickets", "refunds", "payments", "booked_seats", "bookings",
                  "seat_category_prices", "shows", "events", "seats", "screens", "users", "venues"):
        op.drop_table(table)
