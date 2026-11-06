from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (Account, AccountType, Cashback, EntryType, LedgerEntry, Merchant, MerchantPayment, Refund,
                        Transaction, TxnStatus, TxnType, User, Wallet)
from app.services.statements import parse_month
from app.utils.common import (ZERO, ist_date_start_utc, ist_now, month_start_utc, next_month, q2, to_ist,
                              today_start_utc)


def _range(from_date: Optional[date], to_date: Optional[date], default_days: int = 30):
    to_d = to_date or ist_now().date()
    from_d = from_date or (to_d - timedelta(days=default_days))
    return from_d, to_d, ist_date_start_utc(from_d), ist_date_start_utc(to_d + timedelta(days=1))


def admin_dashboard(db: Session) -> dict:
    total = db.query(func.coalesce(func.sum(Wallet.balance), 0)).scalar()
    since = today_start_utc()
    rows = (db.query(Transaction.type, Transaction.status, func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.created_at >= since).group_by(Transaction.type, Transaction.status).all())
    by_type = {t.value: {"count": 0, "volume": ZERO} for t in TxnType}
    failed_today = 0
    for ttype, status, cnt, vol in rows:
        by_type[ttype.value]["count"] += cnt
        if status == TxnStatus.SUCCESS:
            by_type[ttype.value]["volume"] += q2(vol)
        if status == TxnStatus.FAILED:
            failed_today += cnt
    cashback_all = (db.query(func.coalesce(func.sum(Transaction.amount), 0))
                    .filter(Transaction.type == TxnType.CASHBACK, Transaction.status == TxnStatus.SUCCESS).scalar())
    return {"total_money_in_wallets": q2(total), "today": {"by_type": by_type, "total_count": sum(v["count"] for v in by_type.values())},
            "failed_transactions": {"today": failed_today,
                                    "all_time": db.query(func.count(Transaction.id)).filter(Transaction.status == TxnStatus.FAILED).scalar()},
            "transactions_on_hold": db.query(func.count(Transaction.id)).filter(Transaction.status == TxnStatus.ON_HOLD).scalar(),
            "cashback_paid_total": q2(cashback_all)}


def ledger_summary(db: Session, from_date: Optional[date], to_date: Optional[date]) -> dict:
    accts = db.query(Account).filter(Account.wallet_id.is_(None)).order_by(Account.id).all()
    q = db.query(LedgerEntry.entry_type, func.coalesce(func.sum(LedgerEntry.amount), 0))
    if from_date:
        q = q.filter(LedgerEntry.created_at >= ist_date_start_utc(from_date))
    if to_date:
        q = q.filter(LedgerEntry.created_at < ist_date_start_utc(to_date + timedelta(days=1)))
    tot = {t: q2(v) for t, v in q.group_by(LedgerEntry.entry_type).all()}
    d, c = tot.get(EntryType.DEBIT, ZERO), tot.get(EntryType.CREDIT, ZERO)
    return {"system_accounts": [{"account": a.account_type.value, "balance": a.balance} for a in accts],
            "balance_convention": "balance = total credits - total debits",
            "range": {"from_date": from_date, "to_date": to_date},
            "total_debits": d, "total_credits": c, "balanced": d == c}


def merchant_sales(db: Session, user: User, from_date, to_date) -> dict:
    merchant = user.merchant
    f, t, start, end = _range(from_date, to_date)
    pays = (db.query(MerchantPayment).join(Transaction, Transaction.id == MerchantPayment.transaction_id)
            .filter(MerchantPayment.merchant_id == merchant.id, Transaction.status == TxnStatus.SUCCESS,
                    Transaction.created_at >= start, Transaction.created_at < end).all())
    daily = defaultdict(lambda: {"payments": 0, "sales": ZERO})
    sales = fees = ZERO
    for p in pays:
        day = to_ist(p.transaction.created_at).date().isoformat()
        daily[day]["payments"] += 1
        daily[day]["sales"] += p.amount
        sales += p.amount
        fees += p.fee_amount
    refunds = (db.query(func.count(Refund.id), func.coalesce(func.sum(Refund.amount), 0))
               .join(MerchantPayment, MerchantPayment.id == Refund.merchant_payment_id)
               .filter(MerchantPayment.merchant_id == merchant.id, Refund.created_at >= start, Refund.created_at < end).one())
    ref_amt = q2(refunds[1])
    return {"merchant_code": merchant.merchant_code, "from_date": f, "to_date": t,
            "daily_sales": [{"date": k, **v} for k, v in sorted(daily.items())],
            "number_of_payments": len(pays), "total_sales": q2(sales), "number_of_refunds": refunds[0],
            "total_refunds": ref_amt, "platform_fees_paid": q2(fees), "net_amount_received": q2(sales - fees - ref_amt)}


def my_spending(db: Session, user: User, month: Optional[str]) -> dict:
    y, m = parse_month(month) if month else (ist_now().year, ist_now().month)
    start, end = month_start_utc(y, m), month_start_utc(*next_month(y, m))
    wid = user.wallet.id
    base = [Transaction.sender_wallet_id == wid, Transaction.status == TxnStatus.SUCCESS,
            Transaction.created_at >= start, Transaction.created_at < end]

    def total(ttype):
        return q2(db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(*base, Transaction.type == ttype).scalar())

    cats = (db.query(Merchant.business_category, func.coalesce(func.sum(MerchantPayment.amount), 0))
            .join(MerchantPayment, MerchantPayment.merchant_id == Merchant.id)
            .join(Transaction, Transaction.id == MerchantPayment.transaction_id)
            .filter(*base, Transaction.type == TxnType.MERCHANT_PAYMENT).group_by(Merchant.business_category).all())
    cashback = (db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(Transaction.receiver_wallet_id == wid, Transaction.type == TxnType.CASHBACK,
                        Transaction.status == TxnStatus.SUCCESS, Transaction.created_at >= start, Transaction.created_at < end).scalar())
    transfers, withdrawals = total(TxnType.P2P_TRANSFER), total(TxnType.WITHDRAWAL)
    mp_total = sum((q2(v) for _, v in cats), ZERO)
    return {"month": f"{y}-{m:02d}", "transfers": transfers,
            "merchant_payments": {"total": mp_total, "by_business_category": {c: q2(v) for c, v in cats}},
            "withdrawals": withdrawals, "total_spent": transfers + mp_total + withdrawals, "cashback_earned": q2(cashback)}
