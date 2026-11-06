from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (AccountType, AdminDecision, DecisionType, EntryType, Transaction, TxnStatus, TxnType, User)
from app.services.ledger import create_transaction, lock_accounts, lock_wallets, post_entries
from app.services.limits import check_balance_cap
from app.services.money import txn_summary
from app.utils.common import inr, utcnow
from app.utils.email import Notifier

D, C = EntryType.DEBIT, EntryType.CREDIT


def _get_held(db: Session, ref: str) -> Transaction:
    t = db.query(Transaction).filter(Transaction.transaction_ref == ref).with_for_update().populate_existing().first()
    if t is None:
        raise HTTPException(404, "Transaction not found")
    if t.status != TxnStatus.ON_HOLD:
        raise HTTPException(400, f"Transaction is not On Hold (current status: {t.status.value})")
    return t


def decide(db: Session, admin: User, ref: str, approve: bool, reason: str, notifier: Notifier) -> dict:
    t0 = db.query(Transaction).filter(Transaction.transaction_ref == ref).first()
    if t0 is None:
        raise HTTPException(404, "Transaction not found")
    wallet_ids = [t0.sender_wallet_id, t0.receiver_wallet_id]
    wallets = lock_wallets(db, [i for i in wallet_ids if i])
    t = _get_held(db, ref)
    sender, receiver = wallets[t.sender_wallet_id], wallets[t.receiver_wallet_id]
    waccts, sysaccts = lock_accounts(db, [sender.id, receiver.id], [AccountType.HOLD])
    hold = sysaccts[AccountType.HOLD]
    now = utcnow()
    if approve:
        check_balance_cap(receiver, t.amount, who="Receiver's wallet")
        post_entries(db, t, [(hold, D, t.amount), (waccts[receiver.id], C, t.amount)])
        t.status = TxnStatus.SUCCESS
        result = t
        notifier.add(sender.owner.email, "Transfer approved", f"Your transfer {ref} of {inr(t.amount)} was approved. Reason: {reason}")
        notifier.add(receiver.owner.email, "Money received", f"You received {inr(t.amount)} from {sender.owner.full_name}. Ref: {ref}")
    else:
        rev = create_transaction(db, type=TxnType.REVERSAL, amount=t.amount, status=TxnStatus.SUCCESS, initiated_by=admin.id,
                                 description=f"Reversal of held transfer {ref}", receiver_wallet_id=sender.id, parent_id=t.id)
        post_entries(db, rev, [(hold, D, t.amount), (waccts[sender.id], C, t.amount)])
        t.status = TxnStatus.REVERSED
        result = rev
        notifier.add(sender.owner.email, "Transfer rejected", f"Your transfer {ref} of {inr(t.amount)} was rejected and refunded to your wallet. Reason: {reason}")
    db.add(AdminDecision(transaction_id=t.id, admin_id=admin.id, reason=reason, decided_at=now,
                         decision=DecisionType.APPROVED if approve else DecisionType.REJECTED))
    db.flush()
    return txn_summary(t, decision="Approved" if approve else "Rejected", admin_id=admin.id, decision_reason=reason,
                       reversal_ref=result.transaction_ref if not approve else None)
