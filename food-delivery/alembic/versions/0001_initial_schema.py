"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(10, 2)


def ts():
    return [sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False)]


def fk(col, target, nullable=False, index=False):
    return sa.Column(col, sa.Integer(), sa.ForeignKey(target), nullable=nullable, index=index)


def upgrade() -> None:
    op.create_table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("email", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False), sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False), *ts())
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "delivery_partners", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("vehicle_type", sa.String(20), nullable=False),
        sa.Column("vehicle_number", sa.String(30), nullable=False, unique=True),
        sa.Column("is_online", sa.Boolean(), nullable=False), sa.Column("current_latitude", sa.Float()),
        sa.Column("current_longitude", sa.Float()), sa.Column("last_location_at", sa.DateTime()),
        sa.Column("is_approved", sa.Boolean(), nullable=False), *ts())

    op.create_table(
        "restaurants", sa.Column("id", sa.Integer(), primary_key=True), fk("owner_id", "users.id", index=True),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("cuisine_type", sa.String(80), nullable=False),
        sa.Column("address", sa.String(255), nullable=False), sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False), sa.Column("opening_time", sa.Time(), nullable=False),
        sa.Column("closing_time", sa.Time(), nullable=False),
        sa.Column("is_temporarily_closed", sa.Boolean(), nullable=False),
        sa.Column("delivery_radius_km", sa.Float(), nullable=False), sa.Column("min_order_value", MONEY, nullable=False),
        sa.Column("avg_preparation_minutes", sa.Integer(), nullable=False),
        sa.Column("average_rating", sa.Float(), nullable=False), sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False), *ts())

    op.create_table(
        "menu_categories", sa.Column("id", sa.Integer(), primary_key=True),
        fk("restaurant_id", "restaurants.id", index=True), sa.Column("name", sa.String(100), nullable=False), *ts())

    op.create_table(
        "menu_items", sa.Column("id", sa.Integer(), primary_key=True),
        fk("restaurant_id", "restaurants.id", index=True), fk("category_id", "menu_categories.id"),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("price", MONEY, nullable=False), sa.Column("is_veg", sa.Boolean(), nullable=False),
        sa.Column("packaging_charge", MONEY, nullable=False), sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False), *ts())

    op.create_table(
        "addresses", sa.Column("id", sa.Integer(), primary_key=True), fk("customer_id", "users.id", index=True),
        sa.Column("label", sa.String(20), nullable=False), sa.Column("address_line", sa.String(255), nullable=False),
        sa.Column("city", sa.String(80), nullable=False), sa.Column("pincode", sa.String(6), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False), sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False), *ts())

    op.create_table(
        "coupons", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(40), nullable=False),
        sa.Column("description", sa.String(255)), sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("discount_value", sa.Float(), nullable=False), sa.Column("max_discount", MONEY),
        sa.Column("min_order_value", MONEY, nullable=False), fk("restaurant_id", "restaurants.id", nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=False), sa.Column("valid_to", sa.DateTime(), nullable=False),
        sa.Column("total_usage_limit", sa.Integer()), sa.Column("per_user_limit", sa.Integer()),
        sa.Column("first_order_only", sa.Boolean(), nullable=False), fk("created_by", "users.id"),
        sa.Column("is_active", sa.Boolean(), nullable=False), *ts())
    op.create_index("ix_coupons_code", "coupons", ["code"], unique=True)

    op.create_table(
        "carts", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        fk("restaurant_id", "restaurants.id", nullable=True), fk("coupon_id", "coupons.id", nullable=True), *ts())

    op.create_table(
        "cart_items", sa.Column("id", sa.Integer(), primary_key=True), fk("cart_id", "carts.id", index=True),
        fk("menu_item_id", "menu_items.id"), sa.Column("quantity", sa.Integer(), nullable=False), *ts(),
        sa.UniqueConstraint("cart_id", "menu_item_id", name="uq_cart_item"))

    op.create_table(
        "orders", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_number", sa.String(30), nullable=False), fk("customer_id", "users.id", index=True),
        fk("restaurant_id", "restaurants.id", index=True), fk("address_id", "addresses.id"),
        fk("delivery_partner_id", "delivery_partners.id", nullable=True),
        sa.Column("item_total", MONEY, nullable=False), sa.Column("coupon_code", sa.String(40)),
        sa.Column("discount_amount", MONEY, nullable=False), sa.Column("packaging_charges", MONEY, nullable=False),
        sa.Column("delivery_fee", MONEY, nullable=False), sa.Column("platform_fee", MONEY, nullable=False),
        sa.Column("gst_amount", MONEY, nullable=False), sa.Column("tip_amount", MONEY, nullable=False),
        sa.Column("grand_total", MONEY, nullable=False), sa.Column("payment_method", sa.String(10), nullable=False),
        sa.Column("payment_status", sa.String(10), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False), sa.Column("delivery_otp", sa.String(4), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False), sa.Column("delivery_locked", sa.Boolean(), nullable=False),
        sa.Column("estimated_prep_minutes", sa.Integer()), sa.Column("rejection_reason", sa.String(255)),
        sa.Column("admin_notified_unassigned", sa.Boolean(), nullable=False),
        sa.Column("placed_at", sa.DateTime(), nullable=False), sa.Column("accepted_at", sa.DateTime()),
        sa.Column("ready_at", sa.DateTime()), sa.Column("delivered_at", sa.DateTime()), *ts())
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items", sa.Column("id", sa.Integer(), primary_key=True), fk("order_id", "orders.id", index=True),
        fk("menu_item_id", "menu_items.id"), sa.Column("item_name", sa.String(150), nullable=False),
        sa.Column("price", MONEY, nullable=False), sa.Column("packaging_charge", MONEY, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("line_total", MONEY, nullable=False), *ts())

    op.create_table(
        "order_status_history", sa.Column("id", sa.Integer(), primary_key=True), fk("order_id", "orders.id", index=True),
        sa.Column("old_status", sa.String(30)), sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("changed_by", sa.String(100), nullable=False), sa.Column("note", sa.String(255)),
        sa.Column("changed_at", sa.DateTime(), nullable=False), *ts())

    op.create_table(
        "coupon_usages", sa.Column("id", sa.Integer(), primary_key=True), fk("coupon_id", "coupons.id", index=True),
        fk("user_id", "users.id", index=True), fk("order_id", "orders.id"),
        sa.Column("discount_amount", MONEY, nullable=False), sa.Column("is_released", sa.Boolean(), nullable=False),
        sa.Column("released_at", sa.DateTime()), *ts())

    op.create_table(
        "delivery_offers", sa.Column("id", sa.Integer(), primary_key=True), fk("order_id", "orders.id", index=True),
        fk("partner_id", "delivery_partners.id", index=True), sa.Column("status", sa.String(10), nullable=False),
        sa.Column("offered_at", sa.DateTime(), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False),
        *ts())

    op.create_table(
        "deliveries", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        fk("partner_id", "delivery_partners.id", index=True), sa.Column("status", sa.String(10), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False), sa.Column("earnings", MONEY, nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime()), *ts())

    op.create_table(
        "ratings", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        fk("customer_id", "users.id"), fk("restaurant_id", "restaurants.id", index=True),
        fk("partner_id", "delivery_partners.id", nullable=True),
        sa.Column("restaurant_rating", sa.Integer(), nullable=False),
        sa.Column("partner_rating", sa.Integer(), nullable=False), sa.Column("comment", sa.Text()), *ts())

    op.create_table(
        "notifications", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_role", sa.String(30), nullable=False), fk("user_id", "users.id", nullable=True),
        fk("order_id", "orders.id", nullable=True), sa.Column("message", sa.String(255), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False), *ts())


def downgrade() -> None:
    for table in ("notifications", "ratings", "deliveries", "delivery_offers", "coupon_usages",
                  "order_status_history", "order_items", "orders", "cart_items", "carts", "coupons", "addresses",
                  "menu_items", "menu_categories", "restaurants", "delivery_partners", "users"):
        op.drop_table(table)
