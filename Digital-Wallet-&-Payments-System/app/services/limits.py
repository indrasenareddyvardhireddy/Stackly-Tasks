from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import KYCLevel, Transaction, TxnStatus, TxnType, Wallet
from app.utils.common import ZERO, inr, ist_now, month_start_utc, today_start_utc

LIMITS = {
    KYCLevel.MINIMUM: {"balance": Decimal("10000"), "daily": Decimal("10000"), "monthly": Decimal("25000")},
    KYCLevel.FULL: {"balance": Decimal("200000"), "daily": Decimal("25000"), "monthly": Decimal("100000")},
}
SENDING_TYPES = [TxnType.P2P_TRANSFER, TxnType.MERCHANT_PAYMENT, TxnType.WITHDRAWAL]
COUNTED_STATUSES = [TxnStatus.SUCCESS, TxnStatus.PENDING, TxnStatus.ON_HOLD]


def limits_for(wallet: Wallet, is_merchant: bool = False):
    # Assumption: merchant wallets use the Full-KYC sending/withdrawal limits.
    return LIMITS[KYCLevel.FULL if is_merchant else wallet.kyc_level]


def sent_since(db: Session, wallet_id: int, since) -> Decimal:
    total = (db.query(func.coalesce(func.sum(Transaction.amount), 0))
             .filter(Transaction.sender_wallet_id == wallet_id, Transaction.type.in_(SENDING_TYPES),
                     Transaction.status.in_(COUNTED_STATUSES), Transaction.created_at >= since).scalar())
    return Decimal(total or 0)


def check_sending_limits(db: Session, wallet: Wallet, amount: Decimal, is_merchant: bool = False) -> None:
    lim = limits_for(wallet, is_merchant)
    now = ist_now()
    daily_used = sent_since(db, wallet.id, today_start_utc())
    if daily_used + amount > lim["daily"]:
        remaining = max(lim["daily"] - daily_used, ZERO)
        raise HTTPException(400, f"Daily limit of {inr(lim['daily'])} reached. You can send {inr(remaining)} more today")
    monthly_used = sent_since(db, wallet.id, month_start_utc(now.year, now.month))
    if monthly_used + amount > lim["monthly"]:
        remaining = max(lim["monthly"] - monthly_used, ZERO)
        raise HTTPException(400, f"Monthly limit of {inr(lim['monthly'])} reached. You can send {inr(remaining)} more this month")


def check_balance_cap(wallet: Wallet, amount: Decimal, is_merchant: bool = False, who: str = "Wallet") -> None:
    """Max wallet balance by KYC level. Merchant wallets are exempt when receiving customer payments."""
    if is_merchant:
        return
    cap = LIMITS[wallet.kyc_level]["balance"]
    if wallet.balance + amount > cap:
        raise HTTPException(400, f"{who} balance limit of {inr(cap)} would be exceeded "
                                 f"({wallet.kyc_level.value} KYC). Room left: {inr(max(cap - wallet.balance, ZERO))}")
