# Event & Movie Ticket Booking System (FastAPI)

Organizers create events and shows, customers pick seats on a **live seat map**, pay with a **mock payment or Razorpay
(test mode)** and receive **QR-code PDF tickets** that staff scan at the gate.

**Stack:** FastAPI · SQLAlchemy 2 · MySQL · Alembic · Redis · JWT · Passlib (bcrypt) · qrcode + ReportLab · WebSockets ·
APScheduler · BackgroundTasks + SMTP · Razorpay · Uvicorn · Docker.

## Table of contents
1. [Features](#1-features)
2. [Setup](#2-setup)
3. [Environment variables](#3-environment-variables)
4. [Test users](#4-test-users)
5. [Quick walkthrough (Swagger)](#5-quick-walkthrough-swagger)
6. [API reference](#6-api-reference)
7. [Payments: mock and Razorpay](#7-payments-mock-and-razorpay)
8. [Razorpay webhook](#8-razorpay-webhook)
9. [Tickets and QR codes](#9-tickets-and-qr-codes)
10. [WebSocket testing](#10-websocket-testing)
11. [Background jobs](#11-background-jobs)
12. [Project layout](#12-project-layout)
13. [Key design decisions](#13-key-design-decisions)
14. [Assumptions](#14-assumptions)
15. [Bonus features](#15-bonus-features)
16. [Troubleshooting](#16-troubleshooting)
17. [Submission checklist](#17-submission-checklist)

---------------------------------------------------------------------------------------------------

## 1. Features

* Roles: Admin, Organizer (needs admin approval), Customer, Staff (gate scanner assigned to a venue).
* Venues, screens and seats (bulk creation, seat categories Silver / Gold / Recliner, seat status changes).
* Events and shows with a 15-minute cleaning gap rule, per-category show prices and cached public listing.
* **Live seat map** over WebSockets with Redis seat locks (10 minutes, all-or-nothing multi-seat lock, max 10 seats per show).
* Single-empty-seat rule, best-seat suggestion and dynamic pricing (+10% when a show is more than 80% booked).
* Bookings with a full bill (seat total, convenience fee, GST, grand total).
* Payments: **mock** (`/pay`, with simulated success / failure) and **Razorpay test mode** (order -> Checkout -> verify, plus webhook).
* HMAC-signed **QR ticket PDFs**, gate scanning (one entry per ticket) and entry statistics.
* Cancellations with a refund policy, automatic refunds when a show is cancelled, and a waitlist for sold-out shows.
* Reports (admin dashboard, sales, occupancy, top events, refunds, Excel export).
* E-mail notifications (booking, payment, cancellation, reminders) and scheduled jobs.

---------------------------------------------------------------------------------------------------

## 2. Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then edit the values (see section 3)
```

Create the database (MySQL):
```sql
CREATE DATABASE ticket_booking CHARACTER SET utf8mb4;
```

### Redis
```bash
# Docker (recommended - notification flag included)
docker run -d --name redis -p 6379:6379 redis:7 redis-server --notify-keyspace-events Ex
# or a local install:  redis-server --notify-keyspace-events Ex
```
The `Ex` flag lets the server push *"Seat A5 is now Available"* the moment a 10-minute lock expires.
The app tries `CONFIG SET notify-keyspace-events` on start-up; if your Redis forbids it, start Redis with the flag.
Without it everything still works - only the *instant* lock-expiry push is missing (the REST seat map is always correct).
Redis is also used for the Razorpay webhook event-id de-duplication, rate limiting and caching, so it must be running.

### Alembic (tables are never created with `create_all`)
```bash
alembic upgrade head                       # create all tables (0001 schema, 0002 Razorpay columns)
alembic downgrade -1                       # roll back one migration
alembic revision --autogenerate -m "msg"   # new migration after changing models
alembic current / alembic history          # inspect
```

### Seed demo data and run
```bash
python -m app.utils.seed                   # users for every role + a venue with a 10-row screen
uvicorn app.main:app --reload
```
* Swagger: http://localhost:8000/docs
* Seat-map test page: http://localhost:8000/seat-map-test
* Razorpay test page: http://localhost:8000/razorpay-test

### Docker (app + MySQL + Redis)
```bash
cp .env.example .env
docker compose up --build        # migrations + seed run automatically
```
The compose file overrides `DATABASE_URL` and `REDIS_URL` for the containers; generated PDFs are kept in `./tickets`.

### SMTP
Fill `SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM` in `.env`.
For Gmail use `smtp.gmail.com`, port `587`, TLS `true` and an **App Password** (Google account -> Security -> 2-Step
Verification -> App passwords). For local testing use [MailHog/Mailpit](https://github.com/axllent/mailpit)
(`SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_USE_TLS=false`, empty user/password).
If `SMTP_HOST` is empty, emails are only **logged to the console** (handy for development).

### Tests
```bash
pytest -q       # business-rule unit tests (bill, refund policy, single-empty-seat rule, QR signature, Razorpay signatures)
```

---------------------------------------------------------------------------------------------------

## 3. Environment variables

| Variable                  | Purpose                                                                                   |
|---------------------------|-------------------------------------------------------------------------------------------|
| `DATABASE_URL`            | MySQL connection string, e.g. `mysql+pymysql://root:pass@localhost:3306/ticket_booking`   |
| `REDIS_URL`               | Redis connection string, default `redis://localhost:6379/0`                               |
| `JWT_SECRET_KEY`          | Signs login tokens (30-minute expiry). Use a long random string.                          |
| `QR_SECRET_KEY`           | Signs ticket QR values. Falls back to `JWT_SECRET_KEY`, then to a built-in dev default.   |
| `SMTP_*`                  | Mail server settings (see above). Empty `SMTP_HOST` = log emails to the console.          |
| `RAZORPAY_KEY_ID`         | Razorpay **test** key id (`rzp_test_...`). Needed for `razorpay-order` / `razorpay-verify`. |
| `RAZORPAY_KEY_SECRET`     | Razorpay test key secret. Signs / verifies the Checkout result.                           |
| `RAZORPAY_WEBHOOK_SECRET` | The secret **you type** when creating the webhook in the Razorpay dashboard (not the key secret). Only needed for the webhook. |

Never commit `.env`. Changing `QR_SECRET_KEY` after tickets were issued makes those old tickets fail the gate scan.

---------------------------------------------------------------------------------------------------

## 4. Test users (created by `python -m app.utils.seed`)

| Role      | Email                   | Password        | Notes                                         |
|-----------|-------------------------|-----------------|-----------------------------------------------|
| Admin     | admin@example.com       | Admin@123       |                                               |
| Organizer | organizer@example.com   | Organizer@123   | already approved                              |
| Customer  | customer@example.com    | Customer@123    |                                               |
| Customer  | customer2@example.com   | Customer@123    | use for the two-tab live seat-map demo        |
| Staff     | staff@example.com       | Staff@123       | assigned to *PVR Cinemas - Banjara Hills*     |

Use `POST /auth/login`, copy `access_token`, click **Authorize** in Swagger and paste it (tokens last 30 minutes).
New organizers (`POST /auth/register` with `"role": "Organizer"`) must be approved with `PUT /admin/organizers/{id}/approve`.

## 5. Quick walkthrough (Swagger)

1. Login as **organizer** -> `POST /events` (status `Published`) -> `POST /events/{id}/shows`
   (`screen_id: 1`, a future `show_date`, `start_time`, and a price for **every** seat category: Silver, Gold, Recliner).
2. Login as **customer** -> `GET /shows/{id}/seats` -> `POST /shows/{id}/lock-seats` `{"seat_ids":[..]}`
   -> `POST /bookings` `{"show_id":.., "seat_ids":[..]}` -> `POST /bookings/{id}/pay`
   (`simulate_status: Failed` first, then `Success`) -> `GET /bookings/{id}/ticket` (PDF with QR).
3. Open the PDF, copy the QR text (`BKG-....<signature>`; any QR reader shows it) and login as **staff** ->
   `POST /tickets/scan`. Scanning opens 1 hour before the show; scan twice to see the `409 Ticket already used at ...`.
4. `GET /reports/...` as admin / organizer.

Razorpay variant of step 2: instead of `/pay`, open http://localhost:8000/razorpay-test, paste the customer token and booking id and pay with
test card `4111 1111 1111 1111` (any future expiry / CVV, OTP `1234`) or UPI `success@razorpay`.

---------------------------------------------------------------------------------------------------

## 6. API reference

Swagger groups the endpoints by tag. Roles in brackets; "any" = any logged-in user.

**Authentication** (`/auth`)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/register` | Register a Customer or Organizer (organizers need approval) |
| POST | `/auth/login` | Returns `access_token` |
| GET  | `/auth/me` | Current user |

**Admin** (`/admin`)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/admin/organizers/pending` | Organizers waiting for approval |
| PUT | `/admin/organizers/{user_id}/approve` | Approve an organizer |
| POST | `/admin/staff` | Create a gate staff user |

**Venues, Screens & Seats**
| Method | Path | Notes |
|--------|------|-------|
| POST / GET | `/venues` | Create / list venues |
| PUT | `/venues/{venue_id}` | Update a venue |
| POST | `/venues/{venue_id}/screens` | Add a screen |
| POST | `/screens/{screen_id}/seats/bulk` | Create seats in bulk |
| GET | `/screens/{screen_id}/layout` | Seat layout |
| PUT | `/seats/{seat_id}/status` | Activate / deactivate a seat |

**Events & Shows**
| Method | Path | Notes |
|--------|------|-------|
| POST / GET | `/events` | Create / list (search, filter, sort, paginate; cached) |
| GET / PUT | `/events/{event_id}` | Detail / update (`status: Cancelled` cancels all its shows and refunds) |
| POST / GET | `/events/{event_id}/shows` | Create / list shows |
| PUT | `/shows/{show_id}` | Update a show |
| PUT | `/shows/{show_id}/cancel` | Cancel a show (automatic refunds) |

**Seat Locking**
| Method | Path | Notes |
|--------|------|-------|
| GET | `/shows/{show_id}/seats` | Live seat map with prices |
| POST | `/shows/{show_id}/lock-seats` | Lock seats for 10 minutes (rate limited, 5/min) |
| DELETE | `/shows/{show_id}/lock-seats` | Release your locks |
| GET | `/shows/{show_id}/seats/suggest` | Best-seat suggestion (`count`, `category`) |

**Bookings**
| Method | Path | Notes |
|--------|------|-------|
| POST | `/bookings` | Create a booking from your locked seats |
| GET | `/bookings` | Your bookings (paginated) |
| GET | `/bookings/{booking_id}` | One booking with its bill |

**Payments**
| Method | Path | Notes |
|--------|------|-------|
| POST | `/bookings/{booking_id}/pay` | Mock payment (`simulate_status` Success / Failed) |
| GET | `/bookings/{booking_id}/payments` | Payment attempts for a booking |
| POST | `/bookings/{booking_id}/razorpay-order` | Create (or reuse) the Razorpay order; amount in paise |
| POST | `/bookings/{booking_id}/razorpay-verify` | Verify the Checkout signature and confirm the booking |

**Webhooks**
| Method | Path | Notes |
|--------|------|-------|
| POST | `/webhooks/razorpay` | Called by Razorpay (see section 8). Headers: `X-Razorpay-Signature`, `X-Razorpay-Event-Id` |

**Tickets & Entry**
| Method | Path | Notes |
|--------|------|-------|
| GET | `/bookings/{booking_id}/ticket` | PDF ticket with QR (Confirmed bookings only) |
| POST | `/tickets/scan` | Staff scans a QR value |
| GET | `/shows/{show_id}/entries` | Entry statistics for a show |

**Cancellations, Refunds & Waitlist**
| Method | Path | Notes |
|--------|------|-------|
| PUT | `/bookings/{booking_id}/cancel` | Cancel with refund policy |
| GET | `/bookings/{booking_id}/refunds` | Refunds of a booking |
| POST / GET | `/shows/{show_id}/waitlist` | Join / list the waitlist for a sold-out show |
| DELETE | `/waitlist/{waitlist_id}` | Leave the waitlist |

**Reports & Dashboard** (`/reports`)
`GET /reports/admin-dashboard`, `/reports/event-sales`, `/reports/event-sales/export` (Excel), `/reports/occupancy`,
`/reports/top-events`, `/reports/refunds`.

**Test pages and WebSockets** (not shown in Swagger responses)
`GET /seat-map-test`, `GET /razorpay-test`, `ws /ws/shows/{show_id}/seats`, `ws /ws/notifications`.

---------------------------------------------------------------------------------------------------

## 7. Payments: mock and Razorpay

Both methods end in the same code, so the result is identical: payment row + confirmed booking + permanent seats +
ticket row + PDF in **one transaction**, then locks are released and the live seat map is updated.

**Mock:** `POST /bookings/{id}/pay` with `payment_method` and `simulate_status`. The amount always comes from the booking's
`grand_total`, never from the request.

**Razorpay (optional - the mock keeps working without keys):**
1. Create a free Razorpay account, switch the dashboard to **Test Mode** and copy the keys (`rzp_test_...`).
2. Put `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env` and run `alembic upgrade head` (migration `0002_razorpay` adds the columns).
3. Flow: `POST /bookings/{id}/razorpay-order` -> Razorpay Checkout in the browser -> `POST /bookings/{id}/razorpay-verify`
   with `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`.
4. Verification is HMAC-SHA256 of `order_id|payment_id` with the key secret. **A wrong signature never confirms a booking.**
5. The easiest way to try it is the local page http://localhost:8000/razorpay-test (paste customer token + booking id).

Behaviour worth knowing:
* The order is created once per booking and reused on retries.
* A payment id is processed only once (unique column + row lock), so repeated verify calls are safe.
* If a verified payment arrives for a booking that can no longer be fulfilled (expired, cancelled, seats taken) the payment is
  stored as `Refunded` with a `Late Payment` refund and the booking is left as it is.
* **Refund rows are bookkeeping only.** The project does not call Razorpay's refund API; in a real account you would also
  issue the refund from the dashboard or add that API call.

---------------------------------------------------------------------------------------------------

## 8. Razorpay webhook

`POST /webhooks/razorpay` is called by Razorpay's servers (not by users). It is a safety net for cases where the browser never
reaches `razorpay-verify` (tab closed, network drop). **It is not needed for local testing** - `razorpay-verify` already confirms
the booking, and Razorpay cannot reach `localhost` anyway.

What each call does:
1. If `RAZORPAY_WEBHOOK_SECRET` is empty -> `503`.
2. The raw body is checked against `X-Razorpay-Signature` (HMAC-SHA256 with the webhook secret) -> wrong or missing: `400`.
3. Invalid JSON -> `400`.
4. If `X-Razorpay-Event-Id` was already handled (Redis key `rzp:event:<id>`, kept 24 h) -> `duplicate event ignored`.
5. The event is processed; any exception returns `500` so Razorpay retries. Only after success is the event id stored.

Event handling:
* Only `payment.captured` and `payment.failed` are handled; other events are ignored.
* The booking is found by `razorpay_order_id`; unknown orders are ignored; an already recorded payment id returns `already processed`.
* `payment.captured`: the amount must equal the booking total in paise (otherwise logged and ignored). A Pending booking is
  confirmed; a booking that is no longer payable is auto-refunded.
* `payment.failed`: a failed payment is recorded if the booking is still Pending, so the customer can retry.

Setting it up (only if you want to test it):
1. Run `ngrok http 8000` (or deploy the app on a public URL).
2. Razorpay Dashboard -> Settings -> Webhooks -> Add: URL `https://<id>.ngrok.io/webhooks/razorpay`, events `payment.captured` and
   `payment.failed`, and a secret of your choice.
3. Put the same secret in `.env` as `RAZORPAY_WEBHOOK_SECRET` and restart the server.
4. Pay on the test page and close the tab right after Checkout succeeds - the booking should still become Confirmed.

Manual test with curl (the signature must be computed over the exact bytes sent):
```bash
SECRET="your_webhook_secret"
BODY='{"event":"payment.failed","payload":{"payment":{"entity":{"id":"pay_test123","order_id":"order_XXXX","amount":50000}}}}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')
curl -X POST http://localhost:8000/webhooks/razorpay \
  -H "Content-Type: application/json" -H "X-Razorpay-Signature: $SIG" -H "X-Razorpay-Event-Id: evt_test_1" -d "$BODY"
```
`order_id` must match a booking's `razorpay_order_id`, otherwise the response is `ignored: unknown order`.

---------------------------------------------------------------------------------------------------

## 9. Tickets and QR codes

* One PDF and one QR per booking, generated on payment success and stored in `tickets/<booking_number>.pdf`.
* The QR text is `<booking_number>.<signature>` where `signature` = first 32 hex characters of
  `HMAC-SHA256(QR_SECRET_KEY, booking_number)`.
* **Get the value:** scan the QR on the PDF with any phone camera, or read it from the database
  (`SELECT qr_value FROM tickets WHERE booking_id = 4;`), or compute it:
```bash
python3 -c "import hmac,hashlib;s='YOUR_QR_SECRET_KEY';n='BKG-20261029-0005';print(n+'.'+hmac.new(s.encode(),n.encode(),hashlib.sha256).hexdigest()[:32])"
```
* **Scan:** login as staff -> `POST /tickets/scan` with `{"qr_value": "<value>"}`. The signature is verified, the booking must be
  Confirmed, the show must be at the staff member's venue and not cancelled, scanning opens 1 hour before the show, and the second scan returns
  `409 Ticket already used at ...`.
* `GET /shows/{show_id}/entries` shows how many tickets have been scanned.

---------------------------------------------------------------------------------------------------

## 10. WebSocket testing


Endpoint: `ws://localhost:8000/ws/shows/{show_id}/seats?token=<access_token>`
(an invalid token closes the connection with code `4401`). The full seat map arrives first, then
live `seat_update` messages such as `Seat A5 is now Locked`; your own locks show as **Yours**.

**Postman:** New -> WebSocket -> paste the URL above -> Connect. Lock seats from Swagger (as the same or another customer)
and watch the messages arrive instantly.

**Browser console:**
```js
const ws = new WebSocket("ws://localhost:8000/ws/shows/1/seats?token=<access_token>");
ws.onmessage = (e) => console.log("Update:", e.data);
```

**HTML test page:** open `http://localhost:8000/seat-map-test`, paste a token, enter the show id and press *Connect*.
Open it in **two tabs with two different customers**; click a green seat in one tab and it turns orange in the other.

Extra: `ws://localhost:8000/ws/notifications?token=<token>` delivers personal live notifications
(show cancelled, auto-refund, waitlist seats available).

---------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------

## 11. Background jobs (APScheduler, started with the app)

| Job                  | Schedule        | What it does                                                          |
|----------------------|-----------------|-----------------------------------------------------------------------|
| `expire_bookings`    | every minute    | Marks Pending Payment bookings past their lock expiry as `Expired`    |
| `reminders`          | every 30 min    | E-mails customers whose show starts within 3 hours (once per booking) |
| `complete_shows`     | every 15 min    | Marks Scheduled shows whose end time has passed as Completed         |
| `complete_events`    | daily 00:10     | Marks Published events whose shows are all Completed as Completed     |

---------------------------------------------------------------------------------------------------

## 12. Project layout

```
app/
  main.py  database.py  redis_client.py  config.py
  models/      SQLAlchemy models (+ enums)
  schemas/     Pydantic schemas split by domain (user, venue, event, seat, booking, payment, ticket, cancellation, report)
  routers/     auth, admin, venues, events (events+shows), seats, bookings, payments, webhooks, tickets, cancellations, reports, pages
  services/    seat locking, booking, payment, razorpay, tickets/PDF/QR, cancellation/waitlist, cache, rate limit, email
  auth/        password hashing, JWT, role dependencies
  websockets/  connection manager, seat-map socket, Redis lock-expiry listener
  jobs/        APScheduler jobs
  utils/       pure helpers (billing, refund policy, seat rules, QR signing, Razorpay signatures, pagination, seed)
static/        seat_map_test.html, razorpay_test.html
alembic/       versions: 0001_initial_schema, 0002_razorpay_columns
tickets/       generated PDFs (git-ignored)
tests/         pytest unit tests
```

---------------------------------------------------------------------------------------------------

## 13. Key design decisions

* **Seat locking** - `SET lock:show:{show}:seat:{seat} <customer_id> NX EX 600`. Multi-seat locks are all-or-nothing
  (seats acquired in the same request are released on any conflict and a `409` lists the unavailable seats).
  Release uses an atomic Lua compare-and-delete so a customer can never delete someone else's lock.
* **Seats are confirmed once** - `booked_seats.confirmed_seat_id` is `NULL` while pending/cancelled and equals `seat_id`
  when confirmed; `UNIQUE(show_id, confirmed_seat_id)` enforces "one confirmed booking per seat" and (MySQL allows
  repeated NULLs) lets cancelled seats be sold again.
* **Payment (mock + Razorpay)** - amount always comes from `bookings.grand_total`; the row is locked (`SELECT ... FOR UPDATE`) so a
  double payment is impossible. Success = payment + confirmed booking + permanent seats + ticket row + PDF in **one
  transaction**; locks are released and the live map updated after commit. If the lock expired and someone else took
  the seats, the payment is stored as `Refunded`, a `Late Payment` refund is created and the booking is `Cancelled`.
* **QR code** - `<booking_number>.<first 32 hex chars of HMAC-SHA256(QR_SECRET_KEY, booking_number)>`.
* **Live updates** - REST code (possibly running in worker threads) calls `manager.push_*`, which hands the message to
  the event loop thread-safely; a Redis keyspace-notification listener pushes lock expiries.
* **Caching** - `GET /events` and `GET /events/{id}` are cached 5 minutes per viewer scope (public / organizer / admin);
  every event or show create/update/cancel clears the cache. The seat map is never cached.

## 14. Assumptions

1. All date/times are the **server's local time** (naive datetimes). Run the server in the venue's time zone.
2. Show `end_time` = start + event duration; it may fall after midnight (`end_at` keeps the full datetime).
3. The 15-minute cleaning gap applies before and after every show on the same screen.
4. Screen `total_seats` is recalculated from the real number of seats after each bulk creation.
5. "At most 10 seats per show" counts confirmed seats plus current locks. Locking again an already-locked own seat is a no-op.
6. Single-empty-seat rule: a free seat is rejected only when it would sit between one of the customer's seats and a
   *taken* seat (booked, locked by someone else, or inactive). The edge of a row does not count as taken.
7. A customer lock request counts toward the 5/min rate limit even if it fails with 409/400.
8. Payment success for a booking that is still `Pending Payment` but past its lock expiry is allowed until the
   minute-job marks it `Expired`; if the seats are still free the lock is re-acquired, otherwise it is auto-refunded.
9. One PDF ticket / one QR per booking; scanning admits the whole booking (shows customer name, seats, seat count).
10. Customer cancellation of a `Pending Payment` booking just releases the seats (no refund). Refund % uses
    "> 24h -> 100%", "2h to 24h (inclusive of 2h) -> 50%", "< 2h -> not allowed". Refunds are mock (`status = Processed`)
    and the payment is marked `Refunded`.
11. Waitlist "sold out" means no Available seat in the preferred category (or in the whole show if no category).
    Notified entries are marked `Notified`; seats are **not** reserved - booking stays first come, first served.
12. Reports: revenue = `grand_total` of Confirmed bookings; refunds are reported separately from the refund table.
13. Organizers cancelling an event (`PUT /events/{id}` with `status: Cancelled`) cancels and refunds all its scheduled shows.
14. `GET /events` shows only Published events to customers/anonymous users; organizers see their own events in every
    status; admins see all. Sorting events without shows puts them last.
16. Razorpay: the order amount is `grand_total` in paise and the booking number is the receipt; the Payment row stores
    method `Razorpay`. If a verified payment arrives for a booking that is already Confirmed / Cancelled / Expired
    (or the seats were lost) it is recorded as `Refunded` with a `Late Payment` refund and the booking is left as it is.
    **Refund rows are bookkeeping only** - the project does not call Razorpay's refund API, so in a real account you
    would also issue the refund from the dashboard (or add that API call).
15. Dynamic pricing (bonus): +10% on seat prices once a show is more than 80% booked (applies to the seat map and new
    bookings; the price actually charged is stored on the booked seat).

## 15. Bonus features

Included: **Razorpay (test mode)**, dynamic pricing, best-seat suggestion (`GET /shows/{id}/seats/suggest?count=3&category=Gold`),
pytest unit tests (bill, refund policy, single-empty-seat rule, QR signing, Razorpay signatures), Excel export
(`GET /reports/event-sales/export`), Dockerfile + Docker Compose.
Not implemented: coupons, Razorpay refund API call.

## 16. Troubleshooting

| Problem | Likely cause / fix |
|---------|--------------------|
| `razorpay-order` fails | `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` missing or not test keys; restart after editing `.env` |
| `Invalid payment signature` on verify | Wrong `RAZORPAY_KEY_SECRET`, or the values sent do not come from the same Checkout |
| Webhook returns 503 | `RAZORPAY_WEBHOOK_SECRET` is empty |
| Webhook returns 400 | Secret in `.env` differs from the dashboard, or the body was changed before signing |
| Webhook never arrives locally | Razorpay cannot reach `localhost`; use ngrok. It is optional for local testing |
| `Invalid QR code (signature check failed)` | `QR_SECRET_KEY` changed since the ticket was issued, or the value was copied incompletely |
| Scan rejected as too early | Scanning opens 1 hour before the show |
| No instant "seat available" push | Redis started without `--notify-keyspace-events Ex` |
| Swagger shows a duplicate "Payments (Razorpay)" group | Remove the extra `tags=["Payments (Razorpay)"]` from the routes in `app/routers/payments.py` |

## 17. Submission checklist (things you must produce yourself)

* Push to GitHub (`.env` and `tickets/*` are git-ignored; commit `.env.example`).
* Swagger screenshots, successful/failed payment, PDF ticket with QR, scan + repeated scan, two-tab seat-map recording.
