from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (AccountType, BankAccount, EntryType, KYCLevel, Role, Transaction, TxnStatus, TxnType, User,
                        Wallet, WalletStatus, Withdrawal, WithdrawalStatus)
from app.services.ledger import create_transaction, lock_accounts, lock_wallets, post_entries
from app.services.limits import check_sending_limits
from app.services.money import _low_balance, own_wallet, txn_summary
from app.services.pin import verify_pin
from app.utils.common import inr, mask_account, q2, utcnow
from app.utils.email import Notifier

D, C = EntryType.DEBIT, EntryType.CREDIT
MIN_WITHDRAWAL = Decimal("100")


def request_withdrawal(db: Session, user: User, req, notifier: Notifier):
    amount = q2(req.amount)
    wallet = own_wallet(user)
    if user.role == Role.USER and wallet.kyc_level != KYCLevel.FULL:
        raise HTTPException(403, "Withdrawals to bank need Full KYC")
    if amount < MIN_WITHDRAWAL:
        raise HTTPException(400, f"Minimum withdrawal is {inr(MIN_WITHDRAWAL)}")
    bank = db.query(BankAccount).filter(BankAccount.id == req.bank_account_id, BankAccount.user_id == user.id,
                                        BankAccount.is_active.is_(True)).first()
    if bank is None:
        raise HTTPException(404, "Bank account not found")
    verify_pin(db, user, req.pin)

    w = lock_wallets(db, [wallet.id])[wallet.id]
    if w.status == WalletStatus.FROZEN:
        raise HTTPException(403, "Your wallet is frozen. You cannot withdraw")
    if w.balance < amount:
        raise HTTPException(400, f"Insufficient balance. Available: {inr(w.balance)}")
    check_sending_limits(db, w, amount, is_merchant=user.role == Role.MERCHANT)
    waccts, sysaccts = lock_accounts(db, [w.id], [AccountType.WITHDRAWAL_CLEARING])
    txn = create_transaction(db, type=TxnType.WITHDRAWAL, amount=amount, status=TxnStatus.PENDING, initiated_by=user.id,
                             description=f"Withdrawal to {bank.bank_name} {mask_account(bank.account_number)}",
                             sender_wallet_id=w.id)
    post_entries(db, txn, [(waccts[w.id], D, amount), (sysaccts[AccountType.WITHDRAWAL_CLEARING], C, amount)])
    wd = Withdrawal(transaction_id=txn.id, bank_account_id=bank.id, user_id=user.id, amount=amount,
                    status=WithdrawalStatus.PENDING)
    db.add(wd)
    db.flush()
    _low_balance(w, notifier)
    return txn_summary(txn, withdrawal_id=wd.id, withdrawal_status=wd.status, balance=w.balance,
                       message="Withdrawal requested. It will be processed shortly"), 201


def process_withdrawal(db: Session, withdrawal_id: int, notifier: Notifier) -> str:
    """Scheduled job step: complete (Clearing -> Bank Settlement) or fail (return money as Withdrawal Reversal)."""
    wd0 = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    txn0 = wd0.transaction
    w = lock_wallets(db, [txn0.sender_wallet_id])[txn0.sender_wallet_id]
    wd = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).with_for_update().populate_existing().one()
    if wd.status != WithdrawalStatus.PENDING:
        return "skipped"
    txn = wd.transaction
    bank = wd.bank_account
    owner = w.owner
    waccts, sysaccts = lock_accounts(db, [w.id], [AccountType.WITHDRAWAL_CLEARING, AccountType.BANK_SETTLEMENT])
    clearing = sysaccts[AccountType.WITHDRAWAL_CLEARING]
    now = utcnow()
    if bank.account_number.endswith("0000"):  # simulated bank failure
        rev = create_transaction(db, type=TxnType.WITHDRAWAL_REVERSAL, amount=wd.amount, status=TxnStatus.SUCCESS,
                                 initiated_by=None, description=f"Reversal of {txn.transaction_ref}",
                                 receiver_wallet_id=w.id, parent_id=txn.id)
        post_entries(db, rev, [(clearing, D, wd.amount), (waccts[w.id], C, wd.amount)])
        txn.status = TxnStatus.FAILED
        wd.status = WithdrawalStatus.FAILED
        wd.failure_reason = "Bank rejected the transfer (simulated failure)"
        wd.processed_at = now
        notifier.add(owner.email, "Withdrawal failed", f"Your withdrawal of {inr(wd.amount)} failed. The money was returned to your wallet.")
        return "failed"
    post_entries(db, txn, [(clearing, D, wd.amount), (sysaccts[AccountType.BANK_SETTLEMENT], C, wd.amount)])
    txn.status = TxnStatus.SUCCESS
    wd.status = WithdrawalStatus.COMPLETED
    wd.processed_at = now
    notifier.add(owner.email, "Withdrawal completed", f"Your withdrawal of {inr(wd.amount)} to {bank.bank_name} {mask_account(bank.account_number)} is complete.")
    return "completed"
