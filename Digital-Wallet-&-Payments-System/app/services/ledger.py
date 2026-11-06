"""Double-entry ledger core: locking, transaction creation and balanced posting."""
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (Account, AccountType, EntryType, LedgerEntry, Transaction, TxnStatus, TxnType, Wallet)
from app.utils.common import ist_now, q2, random_token

SYSTEM_ACCOUNT_TYPES = [AccountType.BANK_SETTLEMENT, AccountType.CASHBACK_POOL, AccountType.FEES,
                        AccountType.WITHDRAWAL_CLEARING, AccountType.HOLD]


def ensure_system_accounts(db: Session) -> None:
    for t in SYSTEM_ACCOUNT_TYPES:
        exists = db.query(Account).filter(Account.account_type == t, Account.wallet_id.is_(None)).first()
        if not exists:
            db.add(Account(account_type=t, name=t.value, balance=Decimal("0.00")))
    db.commit()


# ---------------------------------------------------------------- locking
def lock_wallets(db: Session, wallet_ids: Iterable[int]) -> Dict[int, Wallet]:
    """SELECT ... FOR UPDATE, always lower wallet id first -> no deadlocks between opposite transfers."""
    out = {}
    for wid in sorted(set(wallet_ids)):
        w = (db.query(Wallet).filter(Wallet.id == wid).with_for_update().populate_existing().one())
        out[wid] = w
    return out


def lock_accounts(db: Session, wallet_ids: Iterable[int] = (), system_types: Iterable[AccountType] = ()):
    """Lock the ledger accounts of the given wallets plus system accounts (ascending account id).
    Returns (wallet_accounts {wallet_id: Account}, system {AccountType: Account})."""
    wallet_ids, system_types = list(set(wallet_ids)), list(set(system_types))
    ids = []
    if wallet_ids:
        ids += [r.id for r in db.query(Account.id).filter(Account.wallet_id.in_(wallet_ids)).all()]
    if system_types:
        ids += [r.id for r in db.query(Account.id).filter(Account.wallet_id.is_(None),
                                                         Account.account_type.in_(system_types)).all()]
    wallet_accts, system = {}, {}
    for aid in sorted(set(ids)):
        a = db.query(Account).filter(Account.id == aid).with_for_update().populate_existing().one()
        if a.wallet_id is not None:
            wallet_accts[a.wallet_id] = a
        else:
            system[a.account_type] = a
    return wallet_accts, system


# ---------------------------------------------------------------- transactions
def new_transaction_ref(db: Session) -> str:
    while True:
        ref = f"TXN-{ist_now().strftime('%Y%m%d')}-{random_token(6)}"
        if not db.query(Transaction.id).filter(Transaction.transaction_ref == ref).first():
            return ref


def create_transaction(db: Session, *, type: TxnType, amount, status: TxnStatus, initiated_by: Optional[int],
                       description: Optional[str] = None, sender_wallet_id: Optional[int] = None,
                       receiver_wallet_id: Optional[int] = None, parent_id: Optional[int] = None,
                       is_flagged: bool = False) -> Transaction:
    txn = Transaction(transaction_ref=new_transaction_ref(db), type=type, amount=q2(amount), status=status,
                      initiated_by=initiated_by, description=description, sender_wallet_id=sender_wallet_id,
                      receiver_wallet_id=receiver_wallet_id, parent_id=parent_id, is_flagged=is_flagged)
    db.add(txn)
    db.flush()
    return txn


Entry = Tuple[Account, EntryType, Decimal]


def post_entries(db: Session, txn: Transaction, entries: List[Entry]) -> None:
    """Append ledger entries. Total debits MUST equal total credits. Accounts must already be locked.
    The wallet.balance column is updated in the same DB transaction as the entries."""
    debit = sum((q2(a) for _, t, a in entries if t == EntryType.DEBIT), Decimal("0.00"))
    credit = sum((q2(a) for _, t, a in entries if t == EntryType.CREDIT), Decimal("0.00"))
    if debit != credit or debit <= 0:
        raise RuntimeError(f"Unbalanced ledger posting: debit={debit} credit={credit}")
    for acct, etype, amount in entries:
        amount = q2(amount)
        acct.balance = q2(acct.balance + amount) if etype == EntryType.CREDIT else q2(acct.balance - amount)
        if acct.wallet_id is not None:
            if acct.balance < 0:  # a wallet balance can never go below zero
                raise HTTPException(status_code=400, detail="Insufficient balance")
            acct.wallet.balance = acct.balance
        db.add(LedgerEntry(transaction_id=txn.id, account_id=acct.id, entry_type=etype, amount=amount,
                           balance_after=acct.balance))
    db.flush()
