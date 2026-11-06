from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func

from app.database import SessionLocal
from app.jobs import tasks
from app.models import BankAccount, Cashback, LedgerEntry, Withdrawal
from app.utils.common import ist_now, utcnow
from tests.conftest import make_actor, upgrade_kyc


def D(x):
    return Decimal(str(x))


def assert_ledger_ok(admin):
    r = admin.post("/admin/reconciliation/run")
    assert r.json()["ok"] is True, r.json()
    s = admin.get("/reports/ledger-summary").json()
    assert s["balanced"] is True


def test_register_rules(client):
    base = {"full_name": "Eve Admin", "email": "eve@test.com", "phone": "9111111111", "password": "Passw0rd1"}
    assert client.post("/auth/register", json={**base, "role": "Admin"}).status_code == 403
    assert client.post("/auth/register", json={**base, "role": "Merchant"}).status_code == 422
    r = client.post("/auth/register", json={**base, "role": "User"})
    assert r.status_code == 201 and r.json()["wallet_number"].startswith("WAL-")
    assert client.post("/auth/register", json={**base, "role": "User"}).status_code == 409
    assert client.get("/auth/me").status_code == 401


def test_roles_are_enforced(client, admin):
    u = make_actor(client)
    assert u.get("/reports/admin-dashboard").status_code == 403
    assert u.get("/merchants/me/qr").status_code == 403
    assert admin.get("/reports/admin-dashboard").status_code == 200


def test_add_money_and_failed_attempt(client, admin):
    u = make_actor(client)
    assert u.post("/wallet/add-money", {"amount": "5", "source": "UPI"}).status_code == 400
    assert u.post("/wallet/add-money", {"amount": "10.555", "source": "UPI"}).status_code == 422
    r = u.post("/wallet/add-money", {"amount": "500", "source": "Card", "simulate_status": "Failed"})
    assert r.json()["status"] == "Failed" and D(u.balance) == 0
    ref = r.json()["transaction_ref"]
    assert admin.get(f"/transactions/{ref}").json()["ledger_entries"] == []
    assert u.post("/wallet/add-money", {"amount": "1000", "source": "UPI"}).status_code == 201
    assert D(u.balance) == D("1000")
    # Minimum KYC cap = 10,000
    assert u.post("/wallet/add-money", {"amount": "9500", "source": "UPI"}).status_code == 400
    assert_ledger_ok(admin)


def test_transfer_balances_and_ledger(client, admin):
    a, b = make_actor(client, funds=2000), make_actor(client)
    r = a.post("/transfers", {"receiver_phone": b.phone, "amount": "750.50", "pin": "2846"})
    assert r.status_code == 201, r.text
    assert D(a.balance) == D("1249.50") and D(b.balance) == D("750.50")
    assert a.post("/transfers", {"receiver_phone": a.phone, "amount": "10", "pin": "2846"}).status_code == 400
    assert a.post("/transfers", {"receiver_phone": b.phone, "amount": "99999", "pin": "2846"}).status_code == 400
    detail = admin.get(f"/transactions/{r.json()['transaction_ref']}").json()
    d = sum(D(e["amount"]) for e in detail["ledger_entries"] if e["entry_type"] == "Debit")
    c = sum(D(e["amount"]) for e in detail["ledger_entries"] if e["entry_type"] == "Credit")
    assert d == c == D("750.50")
    assert_ledger_ok(admin)


def test_idempotency(client):
    a, b = make_actor(client, funds=2000), make_actor(client)
    body = {"receiver_phone": b.phone, "amount": "100", "pin": "2846"}
    r1 = a.post("/transfers", body, key="key-1")
    r2 = a.post("/transfers", body, key="key-1")
    assert r1.status_code == r2.status_code == 201
    assert r2.headers.get("Idempotent-Replayed") == "true" and r1.json() == r2.json()
    assert D(a.balance) == D("1900")  # processed once
    assert a.post("/transfers", {**body, "amount": "200"}, key="key-1").status_code == 422
    r = client.post("/transfers", json=body, headers=a.h)  # no key
    assert r.status_code == 400


def test_pin_lock_after_three_wrong_attempts(client):
    a, b = make_actor(client, funds=500), make_actor(client)
    body = {"receiver_phone": b.phone, "amount": "10", "pin": "9999"}
    assert a.post("/transfers", body).status_code == 400
    assert a.post("/transfers", body).status_code == 400
    assert a.post("/transfers", body).status_code == 423
    assert a.post("/transfers", {**body, "pin": "2846"}).status_code == 423  # even the right PIN is locked
    assert a.post("/wallet/pin", {"pin": "1234"}).status_code in (409, 422)


def test_weak_pin_rejected(client):
    u = make_actor(client)
    assert u.c.post("/wallet/pin", json={"pin": "1234"}, headers=u.h).status_code in (409, 422)


def test_otp_required_above_5000_and_single_use(client):
    a, b = make_actor(client, funds=9000), make_actor(client)
    body = {"receiver_phone": b.phone, "amount": "6000", "pin": "2846"}
    assert a.post("/transfers", body).status_code == 400
    code = a.send_otp("High Value Transfer")
    assert a.c.post("/otp/send", json={"purpose": "High Value Transfer"}, headers=a.h).status_code == 429  # 60s rule
    assert a.post("/transfers", {**body, "otp": "000000" if code != "000000" else "111111"}).status_code == 400
    assert a.post("/transfers", {**body, "otp": code}).status_code == 201
    assert a.post("/transfers", {**body, "amount": "6001", "otp": code}).status_code == 400  # already used


def test_otp_purpose_must_match(client):
    a = make_actor(client)
    code = a.send_otp("PIN Reset")
    r = a.c.post("/otp/verify", json={"purpose": "High Value Transfer", "otp": code}, headers=a.h)
    assert r.status_code == 400


def test_daily_limit_message(client):
    a, b = make_actor(client, funds=9000), make_actor(client)
    for _ in range(2):
        assert a.post("/transfers", {"receiver_phone": b.phone, "amount": "4000", "pin": "2846"}).status_code == 201
    # b is Minimum KYC (cap 10,000) so move funds back and forth is not needed; top up a
    assert a.post("/wallet/add-money", {"amount": "5000", "source": "UPI"}).status_code == 201
    r = a.post("/transfers", {"receiver_phone": b.phone, "amount": "3000", "pin": "2846"})
    assert r.status_code == 400
    assert "Daily limit of \u20b910,000 reached. You can send \u20b92,000 more today" in r.json()["detail"]


def test_frozen_wallet_can_receive_but_not_send(client, admin):
    a, b = make_actor(client, funds=1000), make_actor(client, funds=1000)
    wid = a.get("/wallet").json()
    db = SessionLocal()
    from app.models import Wallet
    w = db.query(Wallet).filter(Wallet.wallet_number == wid["wallet_number"]).one()
    wallet_id = w.id
    db.close()
    assert admin.put(f"/admin/wallets/{wallet_id}/freeze", {"reason": "suspicious"}).status_code == 200
    assert a.post("/transfers", {"receiver_phone": b.phone, "amount": "10", "pin": "2846"}).status_code == 403
    assert a.post("/wallet/add-money", {"amount": "100", "source": "UPI"}).status_code == 201  # can receive money
    assert admin.put(f"/admin/wallets/{wallet_id}/unfreeze").status_code == 200


def test_merchant_payment_fee_cashback_and_refund(client, admin):
    user, m = make_actor(client, funds=5000), make_actor(client, role="Merchant")
    code = client.get("/auth/me", headers=m.h).json()["merchant"]["merchant_code"]
    r = user.post("/payments/merchant", {"merchant_code": code, "amount": "1000", "pin": "2846"})
    assert r.status_code == 201, r.text
    ref = r.json()["transaction_ref"]
    assert D(m.balance) == D("990") and D(user.balance) == D("4000")
    assert D(r.json()["pending_cashback"]) == D("20")
    fees = [a for a in admin.get("/reports/ledger-summary").json()["system_accounts"] if a["account"] == "Fees"][0]
    assert D(fees["balance"]) == D("10")
    # only the receiving merchant may refund; cannot exceed the original amount
    other = make_actor(client, role="Merchant")
    assert other.post(f"/payments/{ref}/refund", {"amount": "10"}).status_code == 403
    assert m.post(f"/payments/{ref}/refund", {"amount": "400"}).status_code == 201
    assert m.post(f"/payments/{ref}/refund", {"amount": "700"}).status_code == 400
    assert m.post(f"/payments/{ref}/refund", {"amount": "500"}).status_code == 201
    assert D(user.balance) == D("4900")
    # pending cashback was cancelled by the refund -> job credits nothing
    db = SessionLocal()
    db.query(Cashback).update({"credit_after": utcnow() - timedelta(hours=1)})
    db.commit()
    db.close()
    assert tasks.cashback_job() == 0
    assert_ledger_ok(admin)


def test_cashback_job_credits_after_24h(client, admin):
    user, m = make_actor(client, funds=5000), make_actor(client, role="Merchant")
    code = client.get("/auth/me", headers=m.h).json()["merchant"]["merchant_code"]
    assert user.post("/payments/merchant", {"merchant_code": code, "amount": "3000", "pin": "2846"}).status_code == 201
    assert tasks.cashback_job() == 0  # not yet 24h
    db = SessionLocal()
    db.query(Cashback).update({"credit_after": utcnow() - timedelta(minutes=1)})
    db.commit()
    db.close()
    assert tasks.cashback_job() == 1
    assert D(user.balance) == D("2050")  # 5000 - 3000 + 50 (cashback capped at 50)
    assert_ledger_ok(admin)


def test_fraud_hold_approve_and_reject(client, admin):
    a, b = make_actor(client), make_actor(client)
    upgrade_kyc(admin, a, "ABCDE1234F")
    upgrade_kyc(admin, b, "ABCDE1235F")
    assert a.post("/wallet/add-money", {"amount": "25000", "source": "UPI"}).status_code == 201
    body = {"receiver_phone": b.phone, "amount": "21000", "pin": "2846", "otp": a.send_otp("High Value Transfer")}
    r = a.post("/transfers", body)
    assert r.status_code == 201 and r.json()["status"] == "On Hold"
    ref = r.json()["transaction_ref"]
    assert D(a.balance) == D("4000") and D(b.balance) == D("0")
    assert any(t["transaction_ref"] == ref for t in admin.get("/admin/flagged-transactions").json()["items"])
    assert admin.put(f"/admin/transactions/{ref}/approve", {"reason": "verified with user"}).status_code == 200
    assert D(b.balance) == D("21000")
    assert admin.put(f"/admin/transactions/{ref}/approve", {"reason": "again"}).status_code == 400
    assert_ledger_ok(admin)


def test_fraud_reject_returns_money(client, admin):
    a, b = make_actor(client), make_actor(client)
    upgrade_kyc(admin, a, "ABCDE1234G")
    upgrade_kyc(admin, b, "ABCDE1235G")
    assert a.post("/wallet/add-money", {"amount": "25000", "source": "UPI"}).status_code == 201
    otp = a.send_otp("High Value Transfer")
    r = a.post("/transfers", {"receiver_phone": b.phone, "amount": "21000", "pin": "2846", "otp": otp})
    ref = r.json()["transaction_ref"]
    assert admin.put(f"/admin/transactions/{ref}/reject", {"reason": "fraud suspected"}).status_code == 200
    assert D(a.balance) == D("25000") and D(b.balance) == D("0")
    assert_ledger_ok(admin)


def test_velocity_rule_holds_sixth_transfer(client, admin):
    a, b = make_actor(client, funds=9000), make_actor(client)
    statuses = [a.post("/transfers", {"receiver_phone": b.phone, "amount": "10", "pin": "2846"}).json()["status"] for _ in range(6)]
    assert statuses[:5] == ["Success"] * 5 and statuses[5] == "On Hold"


def test_withdrawal_complete_and_failure_reversal(client, admin):
    u = make_actor(client, funds=5000)
    assert u.post("/withdrawals", {"bank_account_id": 1, "amount": "500", "pin": "2846"}).status_code == 403  # Minimum KYC
    upgrade_kyc(admin, u, "ABCDE1234H")
    for number in ("123456789012", "123456780000"):
        code = u.send_otp("Add Bank Account")
        db = SessionLocal()
        from app.models import OTP
        db.query(OTP).update({"created_at": utcnow() - timedelta(minutes=2)})
        db.commit()
        db.close()
        r = u.post("/bank-accounts", {"account_holder_name": "Test", "account_number": number, "ifsc_code": "SBIN0001234",
                                      "bank_name": "SBI", "otp": code})
        assert r.status_code == 201, r.text
        assert r.json()["account_number"].endswith(number[-4:]) and "X" in r.json()["account_number"]
    banks = u.get("/bank-accounts").json()
    ok_id = [b for b in banks if b["account_number"].endswith("9012")][0]["id"]
    bad_id = [b for b in banks if b["account_number"].endswith("0000")][0]["id"]
    assert u.post("/withdrawals", {"bank_account_id": ok_id, "amount": "50", "pin": "2846"}).status_code == 400  # < 100
    assert u.post("/withdrawals", {"bank_account_id": ok_id, "amount": "500", "pin": "2846"}).status_code == 201
    assert u.post("/withdrawals", {"bank_account_id": bad_id, "amount": "700", "pin": "2846"}).status_code == 201
    assert D(u.balance) == D("3800")
    db = SessionLocal()
    db.query(Withdrawal).update({"created_at": utcnow() - timedelta(minutes=11)})
    db.commit()
    db.close()
    assert tasks.withdrawal_job() == {"completed": 1, "failed": 1}
    assert D(u.balance) == D("4500")  # failed 700 returned via Withdrawal Reversal
    statuses = sorted(w["status"] for w in u.get("/withdrawals").json()["items"])
    assert statuses == ["Completed", "Failed"]
    assert_ledger_ok(admin)


def test_money_request_flow(client, admin):
    a, b = make_actor(client), make_actor(client, funds=1000)
    r = a.post("/money-requests", {"payer_phone": b.phone, "amount": "300", "note": "lunch"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert a.put(f"/money-requests/{rid}/pay", {"pin": "2846"}).status_code in (400, 422)  # needs key + only payer pays
    pay = b.c.put(f"/money-requests/{rid}/pay", json={"pin": "2846"}, headers={**b.h, "Idempotency-Key": "pay-1"})
    assert pay.status_code == 200, pay.text
    assert D(a.balance) == D("300") and D(b.balance) == D("700")
    for _ in range(5):
        assert a.post("/money-requests", {"payer_phone": b.phone, "amount": "10"}).status_code == 201
    assert a.post("/money-requests", {"payer_phone": b.phone, "amount": "10"}).status_code == 409


def test_statement_closing_balance_and_files(client):
    import csv, io
    a, b = make_actor(client, funds=2000), make_actor(client)
    a.post("/transfers", {"receiver_phone": b.phone, "amount": "500", "pin": "2846"})
    month = ist_now().strftime("%Y-%m")
    r = a.get(f"/statements?month={month}&format=csv")
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text)))
    flat = {row[0]: row[1] for row in rows if len(row) == 2}
    assert D(flat["Closing balance"]) == D(flat["Opening balance"]) + D(flat["Total credits"]) - D(flat["Total debits"]) == D("1500")
    pdf = a.get(f"/statements?month={month}&format=pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert a.get("/statements?month=2026-13&format=pdf").status_code == 422


def test_wallets_are_locked_lowest_id_first():
    """Opposite transfers (A->B, B->A) lock wallets in the same order, so they cannot deadlock."""
    from sqlalchemy import event
    from app.database import engine
    from app.services.ledger import lock_wallets
    from app.models import Account, AccountType, Wallet, User, Role
    db = SessionLocal()
    ids = []
    for i in range(2):
        u = User(full_name="x", email=f"x{i}@t.com", phone=f"97000000{i}0", password_hash="x", role=Role.USER)
        db.add(u); db.flush()
        w = Wallet(owner_id=u.id, wallet_number=f"WAL-T{i}"); db.add(w); db.flush(); ids.append(w.id)
    db.commit()
    seen = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, params, context, executemany):
        if "FROM wallets" in statement:
            seen.append(params[0] if isinstance(params, (tuple, list)) else list(params.values())[0])

    lock_wallets(db, [ids[1], ids[0]])  # requested "backwards"
    event.remove(engine, "before_cursor_execute", capture)
    db.close()
    assert seen == sorted(ids)
