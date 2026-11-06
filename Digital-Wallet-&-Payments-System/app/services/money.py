"""All money movements. Each function runs inside ONE database transaction (the caller commits).
Lock order everywhere: wallets (lower id first) -> ledger accounts (lower id first)."""
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (Cashback, CashbackStatus, EntryType, Merchant, MerchantPayment, OTPPurpose, Refund, Role,
                        SimulateStatus, Transaction, TxnStatus, TxnType, User, Wallet, WalletStatus, AccountType)
from app.services.ledger import create_transaction, lock_accounts, lock_wallets, post_entries
from app.services.limits import check_balance_cap, check_sending_limits
from app.services.otp import check_otp
from app.services.pin import verify_pin
from app.utils.common import inr, q2, utcnow
from app.utils.email import Notifier

OTP_THRESHOLD = Decimal("5000")
HIGH_VALUE = Decimal("20000")
FEE_RATE = Decimal("0.01")
CASHBACK_RATE = Decimal("0.02")
CASHBACK_CAP = Decimal("50")
LOW_BALANCE = Decimal("100")
REFUND_WINDOW = timedelta(days=7)
D, C = EntryType.DEBIT, EntryType.CREDIT


def own_wallet(user: User) -> Wallet:
    if user.wallet is None:
        raise HTTPException(status_code=400, detail="Wallet not found")
    return user.wallet


def _low_balance(wallet: Wallet, notifier: Notifier):
    if wallet.balance < LOW_BALANCE:
        notifier.add(wallet.owner.email, "Low balance alert",
                     f"Your wallet {wallet.wallet_number} balance is {inr(wallet.balance)}, below {inr(LOW_BALANCE)}. Add money to keep paying.")


def txn_summary(txn: Transaction, **extra) -> dict:
    d = {"transaction_ref": txn.transaction_ref, "type": txn.type, "amount": txn.amount, "status": txn.status,
         "is_flagged": txn.is_flagged, "description": txn.description, "created_at": txn.created_at}
    d.update(extra)
    return d


# ------------------------------------------------------------------ add money
def add_money(db: Session, user: User, req, notifier: Notifier):
    amount = q2(req.amount)
    if amount < Decimal("10") or amount > Decimal("50000"):
        raise HTTPException(400, "Amount must be between \u20b910 and \u20b950,000 per request")
    wallet = own_wallet(user)
    if req.simulate_status == SimulateStatus.FAILED:  # failed attempt: saved, but NO ledger entries
        txn = create_transaction(db, type=TxnType.ADD_MONEY, amount=amount, status=TxnStatus.FAILED,
                                 initiated_by=user.id, description=f"Add money via {req.source.value} failed",
                                 receiver_wallet_id=wallet.id)
        notifier.add(user.email, "Add money failed", f"Your attempt to add {inr(amount)} via {req.source.value} failed.")
        return txn_summary(txn, balance=wallet.balance, message="Payment failed. No money was added"), 200
    w = lock_wallets(db, [wallet.id])[wallet.id]
    check_balance_cap(w, amount)
    waccts, sysaccts = lock_accounts(db, [w.id], [AccountType.BANK_SETTLEMENT])
    txn = create_transaction(db, type=TxnType.ADD_MONEY, amount=amount, status=TxnStatus.SUCCESS,
                             initiated_by=user.id, description=f"Add money via {req.source.value}",
                             receiver_wallet_id=w.id)
    post_entries(db, txn, [(sysaccts[AccountType.BANK_SETTLEMENT], D, amount), (waccts[w.id], C, amount)])
    notifier.add(user.email, "Money added", f"{inr(amount)} was added to your wallet. New balance: {inr(w.balance)}.")
    return txn_summary(txn, balance=w.balance, message="Money added successfully"), 201


# ------------------------------------------------------------------ P2P transfer
def find_receiver(db: Session, phone: str) -> User:
    r = db.query(User).filter(User.phone == phone).first()
    if r is None or r.wallet is None or r.role != Role.USER or not r.is_active:
        raise HTTPException(404, "Receiver not found")
    return r


def fraud_reason(db: Session, sender_wallet_id: int, amount: Decimal):
    since = utcnow() - timedelta(minutes=1)
    recent = (db.query(func.count(Transaction.id))
              .filter(Transaction.sender_wallet_id == sender_wallet_id, Transaction.type == TxnType.P2P_TRANSFER,
                      Transaction.status != TxnStatus.FAILED, Transaction.created_at >= since).scalar())
    if recent >= 5:  # this transfer would be the 6th within a minute
        return "More than 5 outgoing transfers within 1 minute"
    if amount > HIGH_VALUE:
        return f"Single transfer above {inr(HIGH_VALUE)}"
    return None


def execute_transfer(db: Session, sender: User, receiver: User, amount, note, pin, otp, notifier: Notifier,
                     description_prefix: str = "Transfer"):
    amount = q2(amount)
    if receiver.id == sender.id:
        raise HTTPException(400, "You cannot send money to yourself")
    swallet, rwallet = own_wallet(sender), own_wallet(receiver)
    verify_pin(db, sender, pin)
    if amount > OTP_THRESHOLD:
        check_otp(db, sender, OTPPurpose.HIGH_VALUE_TRANSFER, otp, consume=True)

    wallets = lock_wallets(db, [swallet.id, rwallet.id])
    sw, rw = wallets[swallet.id], wallets[rwallet.id]
    if sw.status == WalletStatus.FROZEN:
        raise HTTPException(403, "Your wallet is frozen. You cannot send money")
    if rw.status != WalletStatus.ACTIVE:
        raise HTTPException(400, "Receiver wallet is not active")
    if sw.balance < amount:
        raise HTTPException(400, f"Insufficient balance. Available: {inr(sw.balance)}")
    check_sending_limits(db, sw, amount)
    check_balance_cap(rw, amount, who="Receiver's wallet")
    reason = fraud_reason(db, sw.id, amount)

    sys_types = [AccountType.HOLD] if reason else []
    waccts, sysaccts = lock_accounts(db, [sw.id, rw.id], sys_types)
    desc = f"{description_prefix}: {note}" if note else description_prefix
    txn = create_transaction(db, type=TxnType.P2P_TRANSFER, amount=amount, initiated_by=sender.id, description=desc,
                             status=TxnStatus.ON_HOLD if reason else TxnStatus.SUCCESS, is_flagged=bool(reason),
                             sender_wallet_id=sw.id, receiver_wallet_id=rw.id)
    if reason:  # money goes to the Hold account; receiver does not get it yet
        post_entries(db, txn, [(waccts[sw.id], D, amount), (sysaccts[AccountType.HOLD], C, amount)])
        notifier.add(sender.email, "Transfer put on hold",
                     f"Your transfer {txn.transaction_ref} of {inr(amount)} to {receiver.full_name} is on hold for review ({reason}).")
        msg = "Transfer is on hold for admin review"
    else:
        post_entries(db, txn, [(waccts[sw.id], D, amount), (waccts[rw.id], C, amount)])
        notifier.add(sender.email, "Money sent", f"You sent {inr(amount)} to {receiver.full_name}. Ref: {txn.transaction_ref}. Balance: {inr(sw.balance)}")
        notifier.add(receiver.email, "Money received", f"You received {inr(amount)} from {sender.full_name}. Ref: {txn.transaction_ref}. Balance: {inr(rw.balance)}")
        msg = "Transfer successful"
    _low_balance(sw, notifier)
    return txn_summary(txn, receiver_name=receiver.full_name, balance=sw.balance, message=msg), 201, txn


# ------------------------------------------------------------------ merchant payment
def merchant_payment(db: Session, user: User, req, notifier: Notifier):
    amount = q2(req.amount)
    merchant = db.query(Merchant).filter(Merchant.merchant_code == req.merchant_code).first()
    if merchant is None:
        raise HTTPException(404, "Merchant not found")
    muser = merchant.user
    if not muser.is_active or muser.wallet is None:
        raise HTTPException(400, "Merchant is not accepting payments")
    uwallet, mwallet = own_wallet(user), muser.wallet
    verify_pin(db, user, req.pin)

    wallets = lock_wallets(db, [uwallet.id, mwallet.id])
    uw, mw = wallets[uwallet.id], wallets[mwallet.id]
    if uw.status == WalletStatus.FROZEN:
        raise HTTPException(403, "Your wallet is frozen. You cannot make payments")
    if mw.status != WalletStatus.ACTIVE:
        raise HTTPException(400, "Merchant wallet is not active")
    if uw.balance < amount:
        raise HTTPException(400, f"Insufficient balance. Available: {inr(uw.balance)}")
    check_sending_limits(db, uw, amount)

    fee = q2(amount * FEE_RATE)
    net = amount - fee
    cashback = min(q2(amount * CASHBACK_RATE), CASHBACK_CAP)
    waccts, sysaccts = lock_accounts(db, [uw.id, mw.id], [AccountType.FEES] if fee > 0 else [])
    txn = create_transaction(db, type=TxnType.MERCHANT_PAYMENT, amount=amount, status=TxnStatus.SUCCESS,
                             initiated_by=user.id, description=req.note or f"Payment to {merchant.business_name}",
                             sender_wallet_id=uw.id, receiver_wallet_id=mw.id)
    entries = [(waccts[uw.id], D, amount), (waccts[mw.id], C, net)]
    if fee > 0:
        entries.append((sysaccts[AccountType.FEES], C, fee))
    post_entries(db, txn, entries)
    mp = MerchantPayment(transaction_id=txn.id, user_id=user.id, merchant_id=merchant.id, amount=amount,
                         fee_amount=fee, refunded_amount=Decimal("0.00"))
    db.add(mp)
    db.flush()
    if cashback > 0:
        db.add(Cashback(merchant_payment_id=mp.id, wallet_id=uw.id, amount=cashback,
                        status=CashbackStatus.PENDING, credit_after=utcnow() + timedelta(hours=24)))
    notifier.add(user.email, "Payment successful", f"You paid {inr(amount)} to {merchant.business_name}. Ref: {txn.transaction_ref}. "
                 + (f"Cashback of {inr(cashback)} will be credited within 24 hours." if cashback > 0 else ""))
    notifier.add(muser.email, "Payment received", f"{inr(net)} received from {user.full_name} (fee {inr(fee)}). Ref: {txn.transaction_ref}")
    _low_balance(uw, notifier)
    return txn_summary(txn, merchant_name=merchant.business_name, platform_fee=fee, merchant_receives=net,
                       pending_cashback=cashback, balance=uw.balance, message="Payment successful"), 201


# ------------------------------------------------------------------ refund
def refund_payment(db: Session, merchant_user: User, ref: str, req, notifier: Notifier):
    amount = q2(req.amount)
    ptxn = db.query(Transaction).filter(Transaction.transaction_ref == ref,
                                        Transaction.type == TxnType.MERCHANT_PAYMENT).first()
    if ptxn is None:
        raise HTTPException(404, "Merchant payment not found")
    mp = (db.query(MerchantPayment).filter(MerchantPayment.transaction_id == ptxn.id)
          .with_for_update().populate_existing().one())
    if mp.merchant.user_id != merchant_user.id:
        raise HTTPException(403, "Only the merchant who received this payment can refund it")
    if ptxn.status != TxnStatus.SUCCESS:
        raise HTTPException(400, "Only successful payments can be refunded")
    if utcnow() - ptxn.created_at > REFUND_WINDOW:
        raise HTTPException(400, "Refunds are allowed only within 7 days of the payment")
    remaining = mp.amount - mp.refunded_amount
    if amount > remaining:
        raise HTTPException(400, f"Refund exceeds the original amount. You can refund at most {inr(remaining)} more")

    mwallet, uwallet = own_wallet(merchant_user), ptxn.sender_wallet
    wallets = lock_wallets(db, [mwallet.id, uwallet.id])
    mw, uw = wallets[mwallet.id], wallets[uwallet.id]
    if mw.status == WalletStatus.FROZEN:
        raise HTTPException(403, "Your wallet is frozen")
    if mw.balance < amount:
        raise HTTPException(400, f"Insufficient balance to issue refund. Available: {inr(mw.balance)}")
    waccts, _ = lock_accounts(db, [mw.id, uw.id])
    rtxn = create_transaction(db, type=TxnType.MERCHANT_REFUND, amount=amount, status=TxnStatus.SUCCESS,
                              initiated_by=merchant_user.id, description=req.reason or f"Refund for {ref}",
                              sender_wallet_id=mw.id, receiver_wallet_id=uw.id, parent_id=ptxn.id)
    post_entries(db, rtxn, [(waccts[mw.id], D, amount), (waccts[uw.id], C, amount)])
    mp.refunded_amount = q2(mp.refunded_amount + amount)
    db.add(Refund(merchant_payment_id=mp.id, transaction_id=rtxn.id, amount=amount, reason=req.reason))
    cb = (db.query(Cashback).filter(Cashback.merchant_payment_id == mp.id, Cashback.status == CashbackStatus.PENDING)
          .with_for_update().populate_existing().first())
    if cb:  # refunded before cashback credited -> cancel it
        cb.status = CashbackStatus.CANCELLED
    notifier.add(uw.owner.email, "Refund received", f"{inr(amount)} refunded by {mp.merchant.business_name}. Ref: {rtxn.transaction_ref}")
    notifier.add(merchant_user.email, "Refund issued", f"You refunded {inr(amount)} for {ref}. Ref: {rtxn.transaction_ref}")
    _low_balance(mw, notifier)
    return txn_summary(rtxn, original_transaction_ref=ref, total_refunded=mp.refunded_amount,
                       cashback_cancelled=bool(cb), message="Refund successful"), 201


# ------------------------------------------------------------------ cashback (scheduled job)
def credit_cashback(db: Session, cashback_id: int, notifier: Notifier) -> bool:
    cb0 = db.query(Cashback).filter(Cashback.id == cashback_id).first()
    if cb0 is None:
        return False
    wallets = lock_wallets(db, [cb0.wallet_id])
    cb = db.query(Cashback).filter(Cashback.id == cashback_id).with_for_update().populate_existing().one()
    if cb.status != CashbackStatus.PENDING or cb.credit_after > utcnow():
        return False
    w = wallets[cb.wallet_id]
    waccts, sysaccts = lock_accounts(db, [w.id], [AccountType.CASHBACK_POOL])
    txn = create_transaction(db, type=TxnType.CASHBACK, amount=cb.amount, status=TxnStatus.SUCCESS, initiated_by=None,
                             description="Cashback on merchant payment", receiver_wallet_id=w.id)
    post_entries(db, txn, [(sysaccts[AccountType.CASHBACK_POOL], D, cb.amount), (waccts[w.id], C, cb.amount)])
    cb.status = CashbackStatus.CREDITED
    cb.transaction_id = txn.id
    notifier.add(w.owner.email, "Cashback credited", f"{inr(cb.amount)} cashback was credited to your wallet. Ref: {txn.transaction_ref}")
    return True
