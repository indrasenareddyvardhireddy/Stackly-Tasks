# Digital Wallet & Payments System (FastAPI)

A Paytm / PhonePe-style backend. Users add money, send money to each other, pay merchants through QR codes and
withdraw to bank accounts. **Every rupee is tracked in a double-entry ledger.**

**Status:** the automated suite (`pytest`, 20 tests) passes. The Alembic migration on MySQL and real concurrent
locking on MySQL are the two things to verify on your machine (see [Verification](#13-verification-on-mysql)).

---

## Table of contents
1. [Features](#1-features) · 
2. [Tech stack](#2-tech-stack) · 
3. [Project structure](#3-project-structure) ·
4. [Setup](#4-setup) · 
5. [Roles & access](#5-roles--access) · 
6. [Quick walkthrough](#6-quick-walkthrough) ·
7. [API reference](#7-api-reference) · 
8. [Business rules](#8-business-rules) · 
9. [Ledger design](#9-ledger-design) ·
10. [Idempotency & concurrency](#10-idempotency--concurrency) · 
11. [Scheduled jobs](#11-scheduled-jobs) ·
12. [Tests](#12-tests) · 
13. [Verification on MySQL](#13-verification-on-mysql) · 
14. [Troubleshooting](#14-troubleshooting) ·
15. [Assumptions](#15-assumptions) · 
16. [Not implemented](#16-not-implemented-bonus-items) · 
17. [Submission checklist](#17-submission-checklist)

---

## 1. Features
- JWT authentication (30-minute tokens), bcrypt-hashed passwords, role-based access (Admin / User / Merchant)
- Wallets with KYC levels (Minimum / Full), balance caps, daily and monthly sending limits
- 4-digit transaction PIN (3 wrong attempts lock payments for 30 minutes) and email OTPs
- Double-entry ledger with append-only entries, system accounts, reversals and a reconciliation job
- Idempotency keys on every money API, row-locked concurrent transfers (deadlock-safe ordering)
- P2P transfers, money requests, merchant QR payments with 1% fee, 2% cashback, partial refunds
- Bank accounts and withdrawals (with simulated failure and automatic reversal)
- Fraud checks: velocity rule and high-value rule put transfers On Hold for Admin review
- PDF and CSV statements, transaction history with filters/sorting/pagination, four reports
- Email notifications via BackgroundTasks + SMTP, APScheduler jobs, Alembic migrations

## 2. Tech stack
Python 3.9+ · FastAPI · Pydantic v2 · SQLAlchemy 2 · MySQL · Alembic · PyJWT · Passlib (bcrypt) · qrcode ·
ReportLab + csv · APScheduler · smtplib · Uvicorn · pytest

## 3. Project structure
```
wallet-system/
├── app/
│   ├── main.py            # app, lifespan: system accounts, admin seed, scheduler
│   ├── config.py          # settings from .env
│   ├── database.py        # engine (READ COMMITTED on MySQL), session
│   ├── models/            # SQLAlchemy models + enums
│   ├── schemas/           # Pydantic request schemas / validation
│   ├── routers/           # auth, wallet(+PIN/OTP/KYC), admin, transfers, payments,
│   │                      # money_requests, bank (+withdrawals), transactions, reports
│   ├── services/          # ledger, money, withdrawals, fraud, limits, pin, otp,
│   │                      # idempotency, history, statements, reports
│   ├── auth/              # JWT + role dependencies
│   ├── jobs/              # APScheduler jobs + reconciliation
│   └── utils/             # money/IST helpers, email + Notifier
├── alembic/               # env.py + versions/0001_initial_schema.py
├── scripts/concurrency_check.py
├── tests/                 # pytest suite (SQLite)
├── statements/            # generated statements (git-ignored)
├── Dockerfile, docker-compose.yml, alembic.ini, pytest.ini
├── .env.example, .gitignore, requirements.txt, README.md
```

## 4. Setup

### 4.1 Install
```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env   (then edit it)
```

### 4.2 Create the database (MySQL)
```sql
CREATE DATABASE wallet_db CHARACTER SET utf8mb4;
```
Set `DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/wallet_db` in `.env`.
Special characters in the password must be URL-encoded (for example `@` becomes `%40`).

### 4.3 Run migrations (tables are never created with `create_all`)
```bash
alembic upgrade head
```
| Command | Purpose |
|---|---|
| `alembic upgrade head` | apply all migrations |
| `alembic downgrade -1` / `downgrade base` | roll back one / everything |
| `alembic current` / `alembic history` | inspect state |
| `alembic revision --autogenerate -m "msg"` | create a migration after changing models |

### 4.4 Start the server
```bash
uvicorn app.main:app --reload
```
Open Swagger UI at **http://127.0.0.1:8000/docs**. Log in via `POST /auth/login`, copy `access_token`, click
**Authorize** and paste it.

On startup the app (a) creates the five system ledger accounts if missing, (b) seeds the Admin user, (c) starts the jobs.

### 4.5 Environment variables (`.env`)
| Variable | Meaning |
|---|---|
| `DATABASE_URL` | MySQL connection string |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT settings (default 30 min) |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM/USE_TLS` | email settings; **empty `SMTP_HOST` = emails are only logged** |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_PHONE`, `ADMIN_NAME` | seeded Admin account |
| `STATEMENTS_DIR` | where PDF/CSV statements are written (git-ignored) |
| `DEBUG_RETURN_OTP` | `true` returns the OTP in `/otp/send` (dev only, turn off in production) |
| `ENABLE_SCHEDULER` | `false` when running several workers so jobs run in one process |

### 4.6 SMTP (Gmail example)
Enable 2-step verification, create an **App Password**, then set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_USE_TLS=true`, `SMTP_USER=<your gmail>`, `SMTP_PASSWORD=<app password>`.
Emails are sent in the background, so APIs respond immediately; an email failure is logged and never fails a payment.

### 4.7 Docker (optional)
```bash
docker compose up --build        # MySQL + API, migrations run automatically
```

## 5. Roles & access
| Role | How created | Can do |
|---|---|---|
| **Admin** | seeded from `.env` (`admin@wallet.local` / `Admin@12345`); public registration as Admin returns 403 | approve/reject KYC, freeze/unfreeze wallets, review flagged transactions, view all transactions and reports, run reconciliation. Has no wallet |
| **User** | `POST /auth/register` with `"role": "User"` | add money, send/request money, pay merchants, link banks, withdraw (Full KYC), statements, spending report |
| **Merchant** | `POST /auth/register` with `"role": "Merchant"` + `business_name`, `business_category` | receive payments via QR/merchant code, issue refunds, withdraw (no Full KYC needed), sales report |

A missing/expired token returns **401**; a valid token with the wrong role returns **403**; inactive users cannot log in.

## 6. Quick walkthrough
1. **Register** a user and a merchant (`POST /auth/register`); log in as each and authorize.
   ```json
   {"full_name":"Asha User","email":"asha@test.com","phone":"9876543210","password":"Passw0rd1","role":"User"}
   ```
   ```json
   {"full_name":"Ravi Shop","email":"ravi@test.com","phone":"9876543211","password":"Passw0rd1","role":"Merchant",
    "business_name":"Ravi Groceries","business_category":"Groceries"}
   ```
2. **Set a PIN** (user and merchant): `POST /wallet/pin` `{"pin":"2846"}` (simple PINs such as 1234/1111/0000 are rejected).
3. **Add money** (user): `POST /wallet/add-money` with header `Idempotency-Key: add-001`
   `{"amount":"1000","source":"UPI","simulate_status":"Success"}`.
4. **Send to another user**: `POST /transfers` with header `Idempotency-Key: t-001`
   `{"receiver_phone":"9876543299","amount":"500","note":"Lunch","pin":"2846"}`. Above ₹5,000 first call
   `POST /otp/send {"purpose":"High Value Transfer"}` and add `"otp"` to the body.
5. **Pay a merchant** (use the merchant *code*, not the phone): get it from `GET /auth/me` (merchant) then
   `POST /payments/merchant` `{"merchant_code":"MER-10001","amount":"1000","pin":"2846"}`.
6. **Refund** (merchant): `POST /payments/{transaction_ref}/refund` `{"amount":"400","reason":"Returned item"}`.
7. **KYC**: user `POST /kyc` → Admin `GET /admin/kyc` then `PUT /admin/kyc/{id}/approve` → wallet becomes Full KYC.
8. **Withdraw**: `POST /otp/send {"purpose":"Add Bank Account"}` → `POST /bank-accounts` (with `otp`) →
   `GET /bank-accounts` (note the **`id`**) → `POST /withdrawals` `{"bank_account_id":1,"amount":"500","pin":"2846"}`.
9. **Statements**: `GET /statements?month=2026-11&format=pdf` or `format=csv`.

`Idempotency-Key` is any unique string (a UUID is typical, e.g. `3f9c2b6e-8a41-4d7e-b1c5-92e7a0d4f6a8`). Use a **new** key for
every new payment.

## 7. API reference
✓ = allowed. "own" = only their own records. 🔑 = `Idempotency-Key` header required.

| Endpoint | Admin | User | Merchant | Notes |
|---|:-:|:-:|:-:|---|
| `POST /auth/register`, `POST /auth/login` | public | public | public | |
| `GET /auth/me` | ✓ | ✓ | ✓ | shows `merchant_code` for merchants |
| `GET /wallet` | – | ✓ | ✓ | balance, KYC level, limits |
| `POST /wallet/add-money` 🔑 | – | ✓ | – | ₹10 – ₹50,000 per request |
| `POST /wallet/pin`, `PUT /wallet/pin/change`, `POST /wallet/pin/reset` | – | ✓ | ✓ | reset needs OTP |
| `POST /otp/send`, `POST /otp/verify` | – | ✓ | ✓ | `verify` checks without using the OTP up |
| `POST /kyc`, `GET /kyc` | – | ✓ | ✓ | |
| `GET /admin/kyc`, `PUT /admin/kyc/{id}/approve`, `PUT /admin/kyc/{id}/reject` | ✓ | – | – | reject needs `reason` |
| `PUT /admin/wallets/{id}/freeze`, `PUT /admin/wallets/{id}/unfreeze` | ✓ | – | – | freeze needs `reason` |
| `GET /admin/flagged-transactions` | ✓ | – | – | paginated |
| `PUT /admin/transactions/{ref}/approve`, `/reject` | ✓ | – | – | needs `reason`; stored with admin id + time |
| `POST /admin/reconciliation/run` | ✓ | – | – | same check as the daily job |
| `POST /transfers` 🔑 | – | ✓ | – | to a User's phone number |
| `GET /transfers/{ref}` | ✓ | own | own | |
| `POST /money-requests`, `GET /money-requests` | – | ✓ | – | filters: `direction`, `status` |
| `PUT /money-requests/{id}/pay` 🔑, `/decline`, `/cancel` | – | ✓ | – | pay/decline: payer only; cancel: requester only |
| `GET /merchants/me/qr` | – | – | ✓ | PNG of the merchant code |
| `POST /payments/merchant` 🔑 | – | ✓ | – | by `merchant_code` |
| `POST /payments/{ref}/refund` 🔑 | – | – | ✓ | only the receiving merchant, within 7 days |
| `GET /merchants/me/payments` | – | – | ✓ | paginated |
| `POST /bank-accounts`, `GET /bank-accounts`, `DELETE /bank-accounts/{id}` | – | ✓ | ✓ | add needs OTP; max 3 |
| `POST /withdrawals` 🔑, `GET /withdrawals` | – | ✓ | ✓ | users need Full KYC |
| `GET /transactions`, `GET /transactions/{ref}` | all | own | own | filters below |
| `GET /statements?month=YYYY-MM&format=pdf\|csv` | – | ✓ | ✓ | |
| `GET /reports/admin-dashboard`, `/reports/ledger-summary` | ✓ | – | – | |
| `GET /reports/merchant-sales` | – | – | ✓ | `from_date`, `to_date` |
| `GET /reports/my-spending` | – | ✓ | – | `month=YYYY-MM` |

**Pagination** (`skip`, `limit` ≤ 100) on every list. **`GET /transactions`** also supports `type`, `status`, `min_amount`,
`max_amount`, `from_date`, `to_date`, `sort_by=date|amount`, `order=asc|desc`, e.g.
`/transactions?type=P2P Transfer&status=Success&from_date=2026-10-01&skip=0&limit=10`.

**Status codes:** 200/201 success · 400 business rule failed (clear message) · 401 bad/expired token · 403 wrong role or
frozen wallet · 404 not found · 409 duplicate or request still processing · 422 validation error or reused idempotency key
with a different body · 423 PIN locked · 429 OTP requested too soon.

## 8. Business rules

### KYC limits
| | Minimum KYC | Full KYC |
|---|---|---|
| Max wallet balance | ₹10,000 | ₹2,00,000 |
| Send per day / month | ₹10,000 / ₹25,000 | ₹25,000 / ₹1,00,000 |
| Bank withdrawals | not allowed | allowed |

Daily/monthly limits count transfers, merchant payments and withdrawals together (IST day/month). PAN format
`ABCDE1234F`. A frozen wallet can receive system credits but cannot send, pay or withdraw.

### PIN and OTP
- PIN: 4 digits, hashed; required for transfers, merchant payments and withdrawals; 3 wrong attempts → 30-minute lock (423);
  reset needs an OTP.
- OTP: 6 digits, emailed, stored hashed, valid 5 minutes, single use, max 3 wrong attempts, one new OTP per 60 seconds,
  bound to its purpose (`High Value Transfer`, `Add Bank Account`, `PIN Reset`). Required for transfers above ₹5,000,
  adding a bank account and PIN reset.

### Payments
- **Add money:** ₹10 – ₹50,000; balance may not exceed the KYC cap; `simulate_status: Failed` saves a Failed transaction with no ledger entries.
- **Transfers:** receiver found by phone, must be a **User** with an Active wallet; no self-transfers.
- **Merchant payment:** merchant receives amount − 1% fee (fee goes to the Fees account); payer earns 2% cashback (max ₹50),
  Pending for 24 h then credited by a job; cancelled if the payment is refunded first.
- **Refunds:** only the receiving merchant, within 7 days, partial allowed, total never above the original, merchant needs enough balance.
- **Money requests:** by phone, expire after 48 h, max 5 pending to the same person; paying follows all transfer rules.
- **Withdrawals:** minimum ₹100, PIN required, counts toward the daily limit, money moves wallet → Withdrawal Clearing (Pending);
  the job completes it; account numbers ending `0000` fail and the money returns as a `Withdrawal Reversal`.
- **Fraud:** a transfer is put **On Hold** if it is above ₹20,000 or is the 6th outgoing transfer within a minute. Money moves to the
  Hold account; Admin approve → receiver, reject → back to sender. Users are emailed.

## 9. Ledger design
- `accounts`: one per wallet (`User Wallet` / `Merchant Wallet`) plus system accounts **Bank Settlement, Cashback Pool, Fees,
  Withdrawal Clearing, Hold**.
- `transactions`: the business event (ref like `TXN-20261020-8F3K2A`).
- `ledger_entries`: append-only `Debit`/`Credit` rows with `balance_after`; never edited or deleted — mistakes are corrected with a
  new `Reversal` transaction.
- Convention: **balance = total credits − total debits**. Bank Settlement shows negative once users add money (the platform holds it for them).
- `wallets.balance` is a quick copy updated in the same DB transaction. The posting function refuses unbalanced entries and
  any wallet going below zero.

**Example — user pays merchant ₹1,000 (`TXN-20261020-8F3K2A`, Merchant Payment)**

| Account | Debit | Credit | Balance after |
|---|--:|--:|--:|
| User Wallet | 1,000.00 | | 4,000.00 |
| Merchant Wallet | | 990.00 | 990.00 |
| Fees (system) | | 10.00 | 10.00 |
| **Total** | **1,000.00** | **1,000.00** | |

A 24-hour-later cashback posts `Dr Cashback Pool 20 / Cr User Wallet 20` as a separate `Cashback` transaction.

| Flow | Postings |
|---|---|
| Add money | Dr Bank Settlement / Cr wallet |
| P2P transfer | Dr sender / Cr receiver |
| Refund | Dr merchant / Cr user |
| Withdrawal | Dr wallet / Cr Withdrawal Clearing → later Dr Clearing / Cr Bank Settlement (failure: Dr Clearing / Cr wallet) |
| Fraud hold | Dr sender / Cr Hold → approve: Dr Hold / Cr receiver · reject: Dr Hold / Cr sender |

## 10. Idempotency & concurrency
- **Idempotency:** same key + same request → saved response with header `Idempotent-Replayed: true` (money moves once);
  same key + different request → 422; still processing → 409; keys last 24 h. Missing key → 400. The saved response commits in the
  same DB transaction as the money movement. Requests that fail with an error release their key so the client can retry.
- **Concurrency:** each money movement is one DB transaction. Wallets are locked with `SELECT … FOR UPDATE`, **lower wallet id
  first**, then ledger accounts in id order, so opposite transfers cannot deadlock. MySQL runs at `READ COMMITTED` so limit and
  fraud checks after a lock see the latest data.

## 11. Scheduled jobs (start automatically with the app)
| Job | Schedule | What it does |
|---|---|---|
| Cashback | hourly | credits Pending cashback older than 24 h |
| Withdrawals | every 5 min | completes Pending withdrawals older than 10 min (or fails + reverses) |
| Request expiry | hourly | marks Pending money requests Expired after 48 h |
| Cleanup | daily 02:00 UTC | deletes expired OTPs and idempotency keys older than 24 h |
| Reconciliation | daily 02:30 UTC | wallet balance = sum of its ledger entries; total debits = total credits; mismatches logged and emailed to Admin |

## 12. Tests
```bash
pytest -v
```
20 tests pass: registration and role rules, add money (incl. failed attempt), transfer + ledger balance, idempotency, PIN lock,
weak PIN, OTP rules (threshold, single use, purpose), daily-limit message, frozen wallet, merchant fee/cashback/refund,
cashback job, fraud hold approve/reject, velocity rule, withdrawal complete + reversal, money requests, statement closing
balance (CSV + PDF), and wallet lock ordering. They run on a temporary SQLite file (the only place `create_all` is used).

## 13. Verification on MySQL
1. `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head`.
2. `alembic revision --autogenerate -m "check"` should generate an empty migration (delete it).
3. With the server running on MySQL: `python scripts/concurrency_check.py` — expect four `201`s, no 500 or hang, and
   `reconciliation ok: True`.

## 14. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| 400 "Idempotency-Key header is required" | add the header on money APIs |
| 422 on a repeated request | the same key was used with a different body — use a new key |
| 404 "Receiver not found" on `/transfers` | receiver must be a **User**; merchants are paid with `/payments/merchant` and their code |
| 404 "Bank account not found" on `/withdrawals` | `bank_account_id` is the `id` from `GET /bank-accounts`, not the account number |
| 403 "Withdrawals need Full KYC" | submit KYC and have Admin approve it (merchants are exempt) |
| 400 "balance limit … would be exceeded" | Minimum KYC caps the wallet at ₹10,000 |
| 400 OTP errors | request a fresh OTP for the right purpose; OTPs last 5 min, single use, 60 s between requests |
| 423 | PIN locked for 30 minutes after 3 wrong attempts |
| Endpoints appear twice in Swagger | old `wallet.py` router tag — use the current version (tags set per route) |
| Emails not arriving | `SMTP_HOST` empty means emails are only logged; check console logs |

## 15. Assumptions
1. Money is `DECIMAL(12,2)` / `Decimal`; JSON returns amounts as strings (`"990.00"`).
2. "Today"/"this month" use IST (UTC+5:30); timestamps are stored in UTC.
3. P2P receivers must be Active (Level 8); frozen wallets still receive system credits (cashback, refunds, reversals, returned holds).
4. Only Users send P2P, add money and pay merchants; Merchants receive, refund and withdraw. Phone transfers to merchants are not allowed.
5. Merchant wallets use Full-KYC send/withdrawal limits and are exempt from the balance cap on incoming customer payments.
6. The 1% fee is not refunded; any refund cancels still-pending cashback.
7. Failed requests (wrong PIN, limit reached…) are not stored as transactions; only a simulated failed Add Money is saved as `Failed`.
8. PIN/OTP wrong-attempt counters commit immediately (no money has moved yet).
9. `/otp/verify` does not consume the OTP; the action it was issued for does.
10. The 6th transfer within 60 seconds is held; held transfers count toward limits.
11. Bank account numbers are stored in plain text in this demo (masked in responses); encrypt in production. Deleting a bank account is a soft delete.
12. Admin has no wallet. A money request paid by a transfer that goes On Hold is marked Paid.
13. Statements list the wallet's ledger entries, so closing = opening + credits − debits. PDFs use "Rs." (base font lacks ₹).

## 16. Not implemented (bonus items)
WebSocket live notifications · scheduled payments · mock bill payments · Razorpay test mode · password-protected PDFs.
(Done from the bonus list: pytest tests, Dockerfile and Docker Compose.)

## 17. Submission checklist
- GitHub repo (`.env` and `statements/` are git-ignored; push `.env.example`)
- Alembic migration files · README (this file)
- Swagger screenshots of tested APIs
- Same request twice with the same `Idempotency-Key` returning the same response (`Idempotent-Replayed: true`)
- A PDF and a CSV statement
- Reconciliation result (`POST /admin/reconciliation/run` or the job log line)
