"""Scheduled jobs. Each job opens its own DB session and handles its own errors."""
import logging
from datetime import timedelta

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.models import (Account, Cashback, CashbackStatus, EntryType, IdempotencyKey, LedgerEntry, MoneyRequest, OTP,
                        RequestStatus, Role, User, Wallet, Withdrawal, WithdrawalStatus)
from app.services.money import credit_cashback
from app.services.withdrawals import process_withdrawal
from app.utils.common import ZERO, q2, utcnow
from app.utils.email import Notifier, send_email

logger = logging.getLogger("wallet.jobs")


def cashback_job():
    db = SessionLocal()
    credited = 0
    try:
        ids = [r.id for r in db.query(Cashback.id).filter(Cashback.status == CashbackStatus.PENDING,
                                                          Cashback.credit_after <= utcnow()).all()]
        for cid in ids:
            notifier = Notifier()
            try:
                if credit_cashback(db, cid, notifier):
                    db.commit()
                    credited += 1
                    notifier.flush()
                else:
                    db.rollback()
            except Exception:
                db.rollback()
                logger.exception("cashback %s failed", cid)
        logger.info("cashback_job: credited %s cashbacks", credited)
    finally:
        db.close()
    return credited


def withdrawal_job():
    db = SessionLocal()
    done = {"completed": 0, "failed": 0}
    try:
        cutoff = utcnow() - timedelta(minutes=10)
        ids = [r.id for r in db.query(Withdrawal.id).filter(Withdrawal.status == WithdrawalStatus.PENDING,
                                                            Withdrawal.created_at <= cutoff).all()]
        for wid in ids:
            notifier = Notifier()
            try:
                res = process_withdrawal(db, wid, notifier)
                db.commit()
                if res in done:
                    done[res] += 1
                notifier.flush()
            except Exception:
                db.rollback()
                logger.exception("withdrawal %s failed to process", wid)
        logger.info("withdrawal_job: %s", done)
    finally:
        db.close()
    return done


def request_expiry_job():
    db = SessionLocal()
    try:
        n = (db.query(MoneyRequest).filter(MoneyRequest.status == RequestStatus.PENDING,
                                           MoneyRequest.expires_at <= utcnow())
             .update({"status": RequestStatus.EXPIRED}, synchronize_session=False))
        db.commit()
        logger.info("request_expiry_job: expired %s requests", n)
        return n
    finally:
        db.close()


def cleanup_job():
    db = SessionLocal()
    try:
        now = utcnow()
        otps = db.query(OTP).filter(OTP.expires_at < now).delete(synchronize_session=False)
        keys = db.query(IdempotencyKey).filter(IdempotencyKey.created_at < now - timedelta(hours=24)).delete(synchronize_session=False)
        db.commit()
        logger.info("cleanup_job: deleted %s OTPs and %s idempotency keys", otps, keys)
        return {"otps": otps, "idempotency_keys": keys}
    finally:
        db.close()


def reconcile(db) -> dict:
    """wallet balance == sum of its ledger entries, and total debits == total credits (whole ledger)."""
    sums = {}
    for acct_id, etype, total in (db.query(LedgerEntry.account_id, LedgerEntry.entry_type, func.sum(LedgerEntry.amount))
                                  .group_by(LedgerEntry.account_id, LedgerEntry.entry_type).all()):
        s = sums.setdefault(acct_id, {EntryType.DEBIT: ZERO, EntryType.CREDIT: ZERO})
        s[etype] = q2(total)
    mismatches = []
    total_d = total_c = ZERO
    for acct in db.query(Account).all():
        s = sums.get(acct.id, {EntryType.DEBIT: ZERO, EntryType.CREDIT: ZERO})
        total_d += s[EntryType.DEBIT]
        total_c += s[EntryType.CREDIT]
        expected = q2(s[EntryType.CREDIT] - s[EntryType.DEBIT])
        if q2(acct.balance) != expected:
            mismatches.append({"account_id": acct.id, "account": acct.account_type.value, "stored": str(acct.balance), "ledger_sum": str(expected)})
        if acct.wallet_id is not None:
            w = db.query(Wallet).filter(Wallet.id == acct.wallet_id).first()
            if q2(w.balance) != expected:
                mismatches.append({"wallet_id": w.id, "wallet_number": w.wallet_number, "wallet_balance": str(w.balance), "ledger_sum": str(expected)})
    if total_d != total_c:
        mismatches.append({"ledger": "GLOBAL", "total_debits": str(total_d), "total_credits": str(total_c)})
    return {"checked_at": utcnow(), "accounts_checked": db.query(func.count(Account.id)).scalar(),
            "total_debits": total_d, "total_credits": total_c, "ok": not mismatches, "mismatches": mismatches}


def reconciliation_job():
    db = SessionLocal()
    try:
        result = reconcile(db)
        if result["ok"]:
            logger.info("reconciliation_job: OK - %s accounts, debits=%s credits=%s",
                        result["accounts_checked"], result["total_debits"], result["total_credits"])
        else:
            logger.error("reconciliation_job: MISMATCH %s", result["mismatches"])
            admins = [u.email for u in db.query(User).filter(User.role == Role.ADMIN, User.is_active.is_(True)).all()]
            for to in (admins or [settings.ADMIN_EMAIL]):
                send_email(to, "ALERT: ledger reconciliation mismatch", f"Mismatches found:\n{result['mismatches']}")
        return result
    finally:
        db.close()
