"""initial schema: users, wallets, ledger, payments, bank accounts, requests

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def ts():
    return [sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False)]


def pk():
    return sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True)


def upgrade() -> None:
    op.create_table(
        "users", pk(),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("pin_hash", sa.String(255), nullable=True),
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pin_locked_until", sa.DateTime(), nullable=True),
        *ts(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )

    op.create_table(
        "merchants", pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("business_name", sa.String(150), nullable=False),
        sa.Column("business_category", sa.String(80), nullable=False),
        sa.Column("merchant_code", sa.String(20), nullable=False),
        *ts(),
        sa.UniqueConstraint("user_id", name="uq_merchants_user"),
        sa.UniqueConstraint("merchant_code", name="uq_merchants_code"),
    )

    op.create_table(
        "wallets", pk(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("wallet_number", sa.String(20), nullable=False),
        sa.Column("balance", MONEY, nullable=False, server_default="0.00"),
        sa.Column("kyc_level", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("freeze_reason", sa.String(255), nullable=True),
        *ts(),
        sa.UniqueConstraint("owner_id", name="uq_wallets_owner"),
        sa.UniqueConstraint("wallet_number", name="uq_wallets_number"),
    )

    op.create_table(
        "accounts", pk(),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("balance", MONEY, nullable=False, server_default="0.00"),
        *ts(),
        sa.UniqueConstraint("wallet_id", name="uq_accounts_wallet"),
    )

    op.create_table(
        "kyc", pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pan_number", sa.String(10), nullable=False),
        sa.Column("aadhaar_last4", sa.String(4), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rejection_reason", sa.String(255), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        *ts(),
        sa.UniqueConstraint("user_id", name="uq_kyc_user"),
        sa.UniqueConstraint("pan_number", name="uq_kyc_pan"),
    )

    op.create_table(
        "otps", pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("otp_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        *ts(),
    )
    op.create_index("ix_otps_user_id", "otps", ["user_id"])

    op.create_table(
        "transactions", pk(),
        sa.Column("transaction_ref", sa.String(30), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sender_wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=True),
        sa.Column("receiver_wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        *ts(),
        sa.UniqueConstraint("transaction_ref", name="uq_txn_ref"),
    )
    op.create_index("ix_txn_sender_created", "transactions", ["sender_wallet_id", "created_at"])
    op.create_index("ix_txn_receiver_created", "transactions", ["receiver_wallet_id", "created_at"])

    op.create_table(
        "ledger_entries", pk(),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("balance_after", MONEY, nullable=False),
        *ts(),
    )
    op.create_index("ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])

    op.create_table(
        "idempotency_keys", pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        *ts(),
    )
    op.create_index("uq_idem_user_key", "idempotency_keys", ["user_id", "key"], unique=True)

    op.create_table(
        "bank_accounts", pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_holder_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(18), nullable=False),
        sa.Column("ifsc_code", sa.String(11), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *ts(),
    )
    op.create_index("ix_bank_accounts_user_id", "bank_accounts", ["user_id"])

    op.create_table(
        "withdrawals", pk(),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        *ts(),
        sa.UniqueConstraint("transaction_id", name="uq_withdrawals_txn"),
    )
    op.create_index("ix_withdrawals_user_id", "withdrawals", ["user_id"])

    op.create_table(
        "money_requests", pk(),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        *ts(),
    )
    op.create_index("ix_money_requests_requester_id", "money_requests", ["requester_id"])
    op.create_index("ix_money_requests_payer_id", "money_requests", ["payer_id"])

    op.create_table(
        "merchant_payments", pk(),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("fee_amount", MONEY, nullable=False),
        sa.Column("refunded_amount", MONEY, nullable=False, server_default="0.00"),
        *ts(),
        sa.UniqueConstraint("transaction_id", name="uq_mp_txn"),
    )
    op.create_index("ix_merchant_payments_user_id", "merchant_payments", ["user_id"])
    op.create_index("ix_merchant_payments_merchant_id", "merchant_payments", ["merchant_id"])

    op.create_table(
        "refunds", pk(),
        sa.Column("merchant_payment_id", sa.Integer(), sa.ForeignKey("merchant_payments.id"), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        *ts(),
        sa.UniqueConstraint("transaction_id", name="uq_refund_txn"),
    )
    op.create_index("ix_refunds_merchant_payment_id", "refunds", ["merchant_payment_id"])

    op.create_table(
        "cashbacks", pk(),
        sa.Column("merchant_payment_id", sa.Integer(), sa.ForeignKey("merchant_payments.id"), nullable=False),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("credit_after", sa.DateTime(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        *ts(),
        sa.UniqueConstraint("merchant_payment_id", name="uq_cashback_payment"),
    )

    op.create_table(
        "admin_decisions", pk(),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        *ts(),
    )
    op.create_index("ix_admin_decisions_transaction_id", "admin_decisions", ["transaction_id"])


def downgrade() -> None:
    for t in ["admin_decisions", "cashbacks", "refunds", "merchant_payments", "money_requests", "withdrawals",
              "bank_accounts", "idempotency_keys", "ledger_entries", "transactions", "otps", "kyc", "accounts",
              "wallets", "merchants", "users"]:
        op.drop_table(t)
