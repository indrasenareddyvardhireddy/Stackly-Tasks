from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.models.base import Base, Money, TimestampMixin, enum_col
from app.models.enums import (AccountType, CashbackStatus, DecisionType, EntryType, IdemStatus, KYCLevel,
                              RequestStatus, TxnStatus, TxnType, WalletStatus, WithdrawalStatus)
from sqlalchemy import Date, Numeric
from decimal import Decimal


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    wallet_number = Column(String(20), unique=True, nullable=False)
    balance = Column(Money, nullable=False, default=Decimal("0.00"))  # quick copy of the ledger sum
    kyc_level = Column(enum_col(KYCLevel), nullable=False, default=KYCLevel.MINIMUM)
    status = Column(enum_col(WalletStatus), nullable=False, default=WalletStatus.ACTIVE)
    freeze_reason = Column(String(255), nullable=True)

    owner = relationship("User", back_populates="wallet")
    account = relationship("Account", back_populates="wallet", uselist=False)


class Account(Base, TimestampMixin):
    """Ledger account. balance = total credits - total debits."""
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    account_type = Column(enum_col(AccountType), nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), unique=True, nullable=True)  # NULL for system accounts
    name = Column(String(100), nullable=False)
    balance = Column(Money, nullable=False, default=Decimal("0.00"))

    wallet = relationship("Wallet", back_populates="account")
    entries = relationship("LedgerEntry", back_populates="account")


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    transaction_ref = Column(String(30), unique=True, nullable=False)
    type = Column(enum_col(TxnType), nullable=False)
    amount = Column(Money, nullable=False)
    status = Column(enum_col(TxnStatus), nullable=False)
    initiated_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL for scheduled jobs
    description = Column(String(255), nullable=True)
    is_flagged = Column(Boolean, nullable=False, default=False)
    sender_wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=True)
    receiver_wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)  # reversal -> original

    sender_wallet = relationship("Wallet", foreign_keys=[sender_wallet_id])
    receiver_wallet = relationship("Wallet", foreign_keys=[receiver_wallet_id])
    entries = relationship("LedgerEntry", back_populates="transaction")

    __table_args__ = (
        Index("ix_txn_sender_created", "sender_wallet_id", "created_at"),
        Index("ix_txn_receiver_created", "receiver_wallet_id", "created_at"),
    )


class LedgerEntry(Base, TimestampMixin):
    """Append-only. Never updated or deleted."""
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    entry_type = Column(enum_col(EntryType), nullable=False)
    amount = Column(Money, nullable=False)
    balance_after = Column(Money, nullable=False)

    transaction = relationship("Transaction", back_populates="entries")
    account = relationship("Account", back_populates="entries")


class IdempotencyKey(Base, TimestampMixin):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(128), nullable=False)
    endpoint = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    status = Column(enum_col(IdemStatus), nullable=False, default=IdemStatus.PROCESSING)

    __table_args__ = (Index("uq_idem_user_key", "user_id", "key", unique=True),)


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_holder_name = Column(String(100), nullable=False)
    account_number = Column(String(18), nullable=False)
    ifsc_code = Column(String(11), nullable=False)
    bank_name = Column(String(100), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)  # soft delete (withdrawals keep referencing it)

    user = relationship("User", back_populates="bank_accounts")


class Withdrawal(Base, TimestampMixin):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, unique=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Money, nullable=False)
    status = Column(enum_col(WithdrawalStatus), nullable=False, default=WithdrawalStatus.PENDING)
    processed_at = Column(DateTime, nullable=True)
    failure_reason = Column(String(255), nullable=True)

    transaction = relationship("Transaction")
    bank_account = relationship("BankAccount")


class MoneyRequest(Base, TimestampMixin):
    __tablename__ = "money_requests"
    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Money, nullable=False)
    note = Column(String(255), nullable=True)
    status = Column(enum_col(RequestStatus), nullable=False, default=RequestStatus.PENDING)
    expires_at = Column(DateTime, nullable=False)
    paid_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    requester = relationship("User", back_populates="requests_sent", foreign_keys=[requester_id])
    payer = relationship("User", back_populates="requests_received", foreign_keys=[payer_id])


class MerchantPayment(Base, TimestampMixin):
    __tablename__ = "merchant_payments"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(Money, nullable=False)
    fee_amount = Column(Money, nullable=False)
    refunded_amount = Column(Money, nullable=False, default=Decimal("0.00"))

    transaction = relationship("Transaction")
    merchant = relationship("Merchant", back_populates="payments")
    user = relationship("User")
    refunds = relationship("Refund", back_populates="payment")


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    id = Column(Integer, primary_key=True)
    merchant_payment_id = Column(Integer, ForeignKey("merchant_payments.id"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), unique=True, nullable=False)
    amount = Column(Money, nullable=False)
    reason = Column(String(255), nullable=True)

    payment = relationship("MerchantPayment", back_populates="refunds")
    transaction = relationship("Transaction")


class Cashback(Base, TimestampMixin):
    __tablename__ = "cashbacks"
    id = Column(Integer, primary_key=True)
    merchant_payment_id = Column(Integer, ForeignKey("merchant_payments.id"), unique=True, nullable=False)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    amount = Column(Money, nullable=False)
    status = Column(enum_col(CashbackStatus), nullable=False, default=CashbackStatus.PENDING)
    credit_after = Column(DateTime, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)


class AdminDecision(Base, TimestampMixin):
    __tablename__ = "admin_decisions"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(enum_col(DecisionType), nullable=False)
    reason = Column(String(255), nullable=False)
    decided_at = Column(DateTime, nullable=False)
