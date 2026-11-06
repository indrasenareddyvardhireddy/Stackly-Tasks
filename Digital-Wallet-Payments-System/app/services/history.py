from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models import EntryType, LedgerEntry, Transaction, TxnType, Wallet
from app.utils.common import mask_phone

SYSTEM_LABELS = {
    ("sender", TxnType.ADD_MONEY): "Bank (Add Money)",
    ("receiver", TxnType.WITHDRAWAL): "Bank Account",
    ("sender", TxnType.CASHBACK): "Cashback Pool",
    ("sender", TxnType.WITHDRAWAL_REVERSAL): "Bank (Withdrawal Reversal)",
    ("receiver", TxnType.WITHDRAWAL_REVERSAL): "Wallet",
}


def party(wallet: Optional[Wallet], txn: Transaction, side: str) -> dict:
    if wallet is None:
        return {"name": SYSTEM_LABELS.get((side, txn.type), "Platform"), "phone": None}
    owner = wallet.owner
    name = owner.merchant.business_name if owner.merchant else owner.full_name
    return {"name": name, "phone": mask_phone(owner.phone)}


def balances_after(db: Session, txn_ids: Iterable[int], account_id: Optional[int]) -> Dict[int, object]:
    """Balance after the LAST ledger entry of this wallet's account for each transaction."""
    out: Dict[int, object] = {}
    ids = list(txn_ids)
    if account_id is None or not ids:
        return out
    rows = (db.query(LedgerEntry.transaction_id, LedgerEntry.balance_after)
            .filter(LedgerEntry.account_id == account_id, LedgerEntry.transaction_id.in_(ids))
            .order_by(LedgerEntry.id).all())
    for tid, bal in rows:
        out[tid] = bal
    return out


def txn_dict(txn: Transaction, viewer_wallet_id: Optional[int], balance_after=None) -> dict:
    sender, receiver = party(txn.sender_wallet, txn, "sender"), party(txn.receiver_wallet, txn, "receiver")
    d = {"transaction_ref": txn.transaction_ref, "type": txn.type, "amount": txn.amount, "status": txn.status,
         "description": txn.description, "is_flagged": txn.is_flagged, "date": txn.created_at}
    if viewer_wallet_id is None:  # admin view
        d.update(sender=sender, receiver=receiver)
    else:
        outgoing = txn.sender_wallet_id == viewer_wallet_id
        d.update(direction="Debit" if outgoing else "Credit", other_party=receiver if outgoing else sender,
                 balance_after=balance_after)
    return d


def can_view(txn: Transaction, wallet: Optional[Wallet]) -> bool:
    return wallet is not None and wallet.id in (txn.sender_wallet_id, txn.receiver_wallet_id)
