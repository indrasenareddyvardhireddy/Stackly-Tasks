# Food Delivery System (FastAPI)

A complete backend for a food delivery platform. Customers order from nearby restaurants and apply coupons,
restaurants accept and prepare orders, and the nearest delivery partner delivers them with live tracking.

**Highlights:** JWT authentication and role-based access control · Haversine location search · cart and coupons ·
bill calculation with surge pricing · nearest-partner assignment with 30-second offers · delivery OTP verification ·
WebSockets for live tracking and alerts · APScheduler background jobs · Alembic migrations · ratings and reports.

## Table of contents
1. [Tech stack](#1-tech-stack)
2. [Project structure](#2-project-structure)
3. [Setup](#3-setup)
4. [Test accounts, locations and coupons](#4-test-accounts-locations-and-coupons)
5. [Access control](#5-access-control-who-can-call-what)
6. [API reference](#6-api-reference)
7. [Business rules](#7-business-rules)
8. [Validation, pagination, filtering and sorting](#8-validation-pagination-filtering-and-sorting)
9. [Reports](#9-reports)
10. [Scheduled jobs](#10-scheduled-jobs)
11. [WebSocket testing](#11-websocket-testing)
12. [End-to-end walkthrough](#12-end-to-end-walkthrough)
13. [Testing](#13-testing)
14. [Troubleshooting](#14-troubleshooting)
15. [Assumptions](#15-assumptions)

---

## 1. Tech stack
Python 3.12 (3.9+ supported) · FastAPI · Pydantic · SQLAlchemy 2 · MySQL 8 · Alembic · JWT (PyJWT) ·
Passlib (bcrypt) · WebSockets · APScheduler · Uvicorn · pytest · Docker

## 2. Project structure
```
food-delivery/
├── app/
│   ├── main.py               # app, router registration, scheduler start-up
│   ├── database.py           # engine, session, settings from .env
│   ├── models/               # SQLAlchemy models (user, restaurant, customer, coupon, order)
│   ├── schemas/              # Pydantic request schemas and validation
│   ├── routers/              # auth, restaurants, addresses, cart, coupons, orders,
│   │                         # partners, ratings, reports, ws
│   ├── services/             # coupon, cart, order, assignment, restaurant logic
│   ├── auth/                 # password hashing, JWT, role dependencies
│   ├── websockets/           # connection manager
│   ├── jobs/                 # APScheduler jobs
│   └── utils/                # geo (Haversine), pricing, seed script, helpers
├── static/tracking_test.html # live tracking test page (served at /tracking-test)
├── alembic/                  # migrations (versions/0001_initial_schema.py)
├── tests/                    # pytest unit tests
├── smoke_test.py             # optional end-to-end endpoint checker
├── alembic.ini · requirements.txt · .env.example · .gitignore
└── Dockerfile · docker-compose.yml
```

---

## 3. Setup

### Prerequisites
- **Python 3.12** (recommended). Python 3.14 has no prebuilt wheel for the pinned `pydantic-core` and the install
  fails with `link.exe not found`. On Windows: `winget install Python.Python.3.12`, then open a **new** terminal.
- **MySQL 8** running locally.

### Windows (PowerShell)
```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
# If scripts are blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

### Linux / macOS
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Configure `.env`
```
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/food_delivery
JWT_SECRET_KEY=any-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```
URL-encode special characters in the password (for example `@` becomes `%40`). Only `.env.example` is committed.

### Create the database, tables and sample data
```bash
# create the empty database (MySQL Workbench or the mysql client)
mysql -u root -p -e "CREATE DATABASE food_delivery CHARACTER SET utf8mb4;"

alembic upgrade head          # creates all tables (create_all is NOT used)
python -m app.utils.seed      # optional sample users, restaurants, menu, coupons (safe to re-run)
uvicorn app.main:app --reload
```

### Docker alternative
```bash
docker compose up --build                          # starts MySQL + API, runs migrations
docker compose exec api python -m app.utils.seed
```

### URLs
| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/docs | Swagger UI (use **Authorize** with the token from `POST /auth/login`) |
| http://127.0.0.1:8000/tracking-test | Live order tracking test page |

> With `--reload` on Windows, saving a file prints a `KeyboardInterrupt` traceback before
> `Application startup complete`. This is harmless.

### Alembic commands
| Purpose | Command |
|---|---|
| Apply all migrations | `alembic upgrade head` |
| Roll back one migration | `alembic downgrade -1` |
| Generate a migration after model changes | `alembic revision --autogenerate -m "message"` |
| Show current version | `alembic current` |

---

## 4. Test accounts, locations and coupons

### Test accounts
Created by the seed script. **All passwords: `Password@123`**. Log in with the email address.

| Role | Email |
|---|---|
| Admin | admin@example.com |
| Restaurant Owner (approved) | owner@example.com |
| Customer | customer@example.com |
| Delivery Partner 1 (approved, online) | partner1@example.com |
| Delivery Partner 2 (approved, online) | partner2@example.com |

Admin accounts cannot be created through public registration, so the first admin comes from the seed script.
Newly registered owners and partners must be approved with `PUT /admin/users/{id}/approve`.

**Using Swagger:** call `POST /auth/login`, copy `access_token`, click **Authorize** and paste it. Log in again and
re-authorize to switch roles. Tokens expire after 30 minutes.

### Sample locations
| Entity | Latitude, Longitude |
|---|---|
| Customer address (Home, Gachibowli) | 17.4486, 78.3908 |
| Spice Garden Biryani (restaurant) | 17.4500, 78.3900 |
| Dosa Corner (restaurant) | 17.4400, 78.3800 |
| Partner 1 start | 17.4470, 78.3890 |
| Partner 2 start | 17.4600, 78.4000 |

Example: `GET /restaurants/nearby?latitude=17.4486&longitude=78.3908&cuisine_type=Biryani&min_rating=0&skip=0&limit=10`

### Sample coupons
| Code | Rule |
|---|---|
| `WELCOME50` | Flat ₹50, min order ₹199, first order only, 1 use per user, platform-wide |
| `BIRYANI20` | 20% up to ₹100, min ₹299, only Spice Garden Biryani, 100 total uses, 5 per user |
| `FLAT100` | Flat ₹100, min order ₹499, platform-wide |

Codes are case-insensitive (`welcome50` is the same as `WELCOME50`).

---

## 5. Access control: who can call what
A missing, invalid or expired token returns **401**. A wrong role returns **403**. Restaurant owners and delivery
partners must be **approved by an admin** before using restricted endpoints; otherwise they get 403
"awaiting admin approval". Inactive users cannot log in.

| Role | Can do |
|---|---|
| **Public** | `POST /auth/register`, `POST /auth/login`, `GET /tracking-test` |
| **Any logged-in user** | `GET /auth/me`, `GET /restaurants/nearby`, `GET /restaurants/{id}`, `GET /restaurants/{id}/menu`, `GET /restaurants/{id}/ratings` |
| **Admin** | Approve users, view notifications, platform-wide and all coupons, admin reports |
| **Restaurant Owner** (approved) | Own restaurants and menus, own restaurant coupons, accept/reject/prepare orders, owner reports |
| **Customer** | Addresses, cart, coupons, place/list/view/cancel/reorder own orders, ratings |
| **Delivery Partner** (approved) | Availability, location, offers, pickup/out-for-delivery/deliver, earnings |

Delivery partner endpoints are usable **only** by approved delivery partners; admin, customer and owner get 403.

---

## 6. API reference

### Auth and admin (Level 2)
| Method | Endpoint | Access |
|---|---|---|
| POST | `/auth/register` | Public (customer, restaurant owner, delivery partner; admin returns 403) |
| POST | `/auth/login` | Public |
| GET | `/auth/me` | Any logged-in user |
| PUT | `/admin/users/{user_id}/approve` | Admin |
| GET | `/admin/notifications` | Admin |

### Restaurants and menu (Level 3)
| Method | Endpoint | Access |
|---|---|---|
| POST | `/restaurants` | Approved owner |
| GET | `/restaurants/me` | Owner |
| GET | `/restaurants/{restaurant_id}` | Any logged-in user |
| PUT | `/restaurants/{restaurant_id}` | Owner (own restaurant) |
| PUT | `/restaurants/{restaurant_id}/open-status` | Owner (own restaurant) |
| POST | `/restaurants/{restaurant_id}/categories` | Owner (own restaurant) |
| POST | `/restaurants/{restaurant_id}/menu-items` | Owner (own restaurant) |
| GET | `/restaurants/{restaurant_id}/menu` | Any logged-in user (grouped by category, unavailable items marked) |
| PUT | `/menu-items/{item_id}` | Owner |
| PUT | `/menu-items/{item_id}/availability` | Owner |
| DELETE | `/menu-items/{item_id}` | Owner (soft delete) |

### Location search and addresses (Level 4)
| Method | Endpoint | Access |
|---|---|---|
| GET | `/restaurants/nearby` | Any logged-in user |
| POST / GET | `/addresses` | Customer |
| PUT / DELETE | `/addresses/{address_id}` | Customer |
| PUT | `/addresses/{address_id}/default` | Customer |

### Cart and coupons (Levels 5 and 6)
| Method | Endpoint | Access |
|---|---|---|
| GET / DELETE | `/cart` | Customer |
| POST | `/cart/items` | Customer |
| PUT / DELETE | `/cart/items/{item_id}` | Customer |
| POST | `/cart/apply-coupon` | Customer |
| DELETE | `/cart/coupon` | Customer |
| GET | `/coupons/available` | Customer |
| POST / GET | `/coupons` | Admin, approved owner (own restaurants) |
| PUT | `/coupons/{coupon_id}` | Admin, owner (own coupons) |
| PUT | `/coupons/{coupon_id}/deactivate` | Admin, owner (own coupons) |

### Orders: customer (Level 7), shown as **Orders** in Swagger
| Method | Endpoint | Access |
|---|---|---|
| POST | `/orders` | Customer |
| GET | `/orders` | Customer (own orders; filters: status, restaurant_id, from_date, to_date) |
| GET | `/orders/{order_id}` | Customer (own order; only the customer sees `delivery_otp`) |
| PUT | `/orders/{order_id}/cancel` | Customer (only while `Placed`) |
| POST | `/orders/{order_id}/reorder` | Customer |

### Orders: restaurant (Level 8), shown as **Restaurant Order Handling** in Swagger
| Method | Endpoint | Access |
|---|---|---|
| GET | `/restaurants/me/orders` | Owner |
| PUT | `/orders/{order_id}/accept` | Owner (needs estimated preparation minutes) |
| PUT | `/orders/{order_id}/reject` | Owner (needs a reason) |
| PUT | `/orders/{order_id}/preparing` | Owner |
| PUT | `/orders/{order_id}/ready` | Owner |

### Delivery partner (Level 9)
| Method | Endpoint | Access |
|---|---|---|
| PUT | `/partners/me/availability` | Approved partner |
| PUT | `/partners/me/location` | Approved partner |
| GET | `/partners/me/offers` | Approved partner |
| PUT | `/offers/{offer_id}/accept` | Approved partner (own offer) |
| PUT | `/offers/{offer_id}/decline` | Approved partner (own offer) |
| PUT | `/orders/{order_id}/pickup` | Assigned partner |
| PUT | `/orders/{order_id}/out-for-delivery` | Assigned partner |
| PUT | `/orders/{order_id}/deliver` | Assigned partner (needs the customer's OTP) |
| GET | `/partners/me/earnings` | Approved partner |

### Ratings (Level 12)
| Method | Endpoint | Access |
|---|---|---|
| POST | `/orders/{order_id}/rating` | Customer (own order, once `Delivered`, one per order) |
| GET | `/restaurants/{restaurant_id}/ratings` | Any logged-in user |

### Reports (Level 15)
See [section 9](#9-reports).

### WebSockets (Level 10)
| Endpoint | Who can connect |
|---|---|
| `WS /ws/orders/{order_id}` | The order's customer, the restaurant's owner, the assigned partner, admin |
| `WS /ws/restaurant` | Approved restaurant owners |
| `WS /ws/partner` | Approved delivery partners |

---

## 7. Business rules

### Bill calculation
| Component | Rule |
|---|---|
| Item total | Sum of all line totals |
| Discount | Coupon discount (percentage capped at `max_discount`; flat; never more than the item total) |
| Packaging charges | Sum of packaging charge × quantity |
| Delivery fee | ₹20 for the first 3 km, plus ₹8 for every extra km (rounded up) |
| Platform fee | ₹5 |
| GST | 5% on (item total − discount) |
| Tip | Optional, cannot be negative |
| **Grand total** | (item total − discount) + packaging + delivery fee + platform fee + GST + tip |

**Surge pricing (bonus):** delivery fee ×1.5 between 12:00–14:00 and 19:00–22:00.
**Partner earnings:** ₹25 + ₹6 per km + the customer's tip. Coupons never reduce partner earnings.

### Restaurant open status and search
- A restaurant is open only when the current time is between `opening_time` and `closing_time` and it is not temporarily closed.
- `GET /restaurants/nearby` returns only open, active restaurants within their own `delivery_radius_km`, each with
  `distance_km` and `estimated_delivery_minutes` (preparation time + travel at 20 km/h). Distance uses the Haversine
  function in `app/utils/geo.py`.

### Cart
One cart per customer, items from one restaurant only (409 otherwise: "Your cart has items from another restaurant.
Clear the cart to continue"). Adding the same item increases its quantity; quantity is 1 to 10; unavailable items
cannot be added; clearing the cart also removes the coupon.

### Coupons
- Admin creates platform-wide coupons; owners create coupons only for their own restaurants.
- Valid only if active, within `valid_from`/`valid_to`, item total meets `min_order_value`, and total and per-user
  limits are not exceeded. `first_order_only` coupons need no previous `Delivered` order.
- One coupon per order. It is **re-validated when the order is placed**; usage is counted only then and is released
  if the order is cancelled or rejected.
- Invalid coupons return 400 with a clear reason (for example "Minimum order value is ₹299", "This coupon has expired").

### Placing an order
Runs in a **single database transaction** (validate coupon, create order and items, save coupon usage, clear cart);
any failure rolls everything back. It fails if the cart is empty, the restaurant is closed, the address is outside
the delivery radius, or the item total is below the restaurant's minimum. Order items store the price at order time.
Online payment is a mock (the order is `Paid`); COD stays `Pending` until delivery. A 4-digit delivery OTP is
generated and only the customer can see it. Order numbers look like `ORD-20261020-0001`.

### Order status flow
`Placed → Accepted → Preparing → Ready for Pickup → Picked Up → Out for Delivery → Delivered`
Also `Rejected` (by the restaurant or automatically) and `Cancelled` (by the customer, only while `Placed`).
Every change is stored in `order_status_history` (old status, new status, changed_by, time).
Cancelled or rejected Online orders become `Refunded` and the coupon usage is released.

### Delivery partner assignment
1. When the restaurant accepts, the order is offered to the nearest partner who is approved, online, has no active
   delivery and is within 5 km of the restaurant.
2. The partner has 30 seconds. On decline or expiry it goes to the next nearest partner, skipping those who declined.
3. If nobody is available it is retried every minute; Admin is notified after 15 minutes.
4. Accepting uses row locking (`with_for_update`), so only one partner can win an order. A partner can have only one
   active delivery at a time.
5. Pickup needs status `Ready for Pickup` and the assigned partner. Delivery needs the correct OTP; a wrong OTP
   returns 400 and three wrong attempts lock the delivery and notify Admin.
6. On delivery, COD orders become `Paid` and `delivered_at` is recorded.

---

## 8. Validation, pagination, filtering and sorting

### Validation (422 for invalid input)
Unique email, order number, vehicle number and coupon code · phone is 10 digits · pincode is 6 digits · latitude
−90 to 90 and longitude −180 to 180 · price greater than 0 · `opening_time` before `closing_time` · tip not negative ·
OTP exactly 4 digits · coupon `discount_value` greater than 0, percentage between 1 and 100, `valid_to` after
`valid_from`. Status codes used: 200, 201, 400, 401, 403, 404, 409, 422.

### Pagination (`skip`, `limit`)
`GET /restaurants/nearby`, `GET /orders`, `GET /restaurants/me/orders`, `GET /coupons`,
`GET /restaurants/{restaurant_id}/ratings`

### Filters and sorting
| Endpoint | Options |
|---|---|
| `GET /restaurants/nearby` | `name`, `cuisine_type`, `veg_only`, `min_rating`, `has_offers`; `sort_by` (`distance`, `rating`, `estimated_delivery_minutes`) and `order` (`asc`, `desc`); default sort is by distance |
| `GET /orders` | `status`, `restaurant_id`, `from_date`, `to_date` |
| `GET /coupons` | `restaurant_id`, `is_active`, `discount_type` |

---

## 9. Reports
| Endpoint | Access | Contents |
|---|---|---|
| `GET /reports/admin-dashboard` | Admin | Today's orders, delivered, cancelled, rejected, revenue, discount given, online partners, average delivery time |
| `GET /reports/top-restaurants` | Admin | Top 10 restaurants by orders and revenue for a date range |
| `GET /reports/coupon-usage` | Admin, owner | Times used, total discount, revenue per coupon for a date range |
| `GET /reports/restaurant-sales` | Owner | Daily sales, total orders, best-selling items, average preparation time |
| `GET /reports/partner-summary` | Partner | Deliveries completed, total distance, earnings by day |

`GET /partners/me/earnings` shows deliveries and earnings for today and for a date range (`from_date`, `to_date`).

---

## 10. Scheduled jobs
Started automatically with the application.

| Job | Interval |
|---|---|
| Auto-reject `Placed` orders older than 5 minutes ("Restaurant did not respond"), refund Online, release coupon, notify the customer live | 1 min |
| Expire delivery offers older than 30 s and offer to the next nearest partner | 10 s |
| Retry unassigned accepted orders; notify Admin after 15 min (`GET /admin/notifications`) | 1 min |
| Set partners offline after 10 min without a location update | 5 min |
| Deactivate coupons whose `valid_to` has passed | daily (and once at startup) |

All automatic changes are stored in the order history with `changed_by = "System"`.

---

## 11. WebSocket testing
Token is passed as `?token=<access_token>`. Invalid tokens, or users not allowed on the order, are disconnected
(close code 4401). Live tracking shows status, partner name, vehicle and location, distance remaining and ETA.
Owners receive new-order alerts on `/ws/restaurant`; partners receive offers (restaurant name, pickup distance,
delivery distance, expected earnings, seconds left) on `/ws/partner`.

- **HTML page:** open http://127.0.0.1:8000/tracking-test, paste the customer token and order ID, click **Connect**,
  then change the order status from Swagger and watch it update instantly.
- **Postman:** New → WebSocket → `ws://127.0.0.1:8000/ws/orders/1?token=<access_token>` → Connect.
- **Browser console:**
  ```js
  const ws = new WebSocket("ws://127.0.0.1:8000/ws/orders/1?token=<access_token>");
  ws.onmessage = (e) => console.log("Update:", e.data);
  ```
- **Partner location:** every 5 to 10 seconds call `PUT /partners/me/location` with
  `{"latitude": 17.4480, "longitude": 78.3900}`, or send `{"type":"location","latitude":17.448,"longitude":78.39}`
  over `/ws/partner`. The customer's tracking socket receives the new location, distance remaining and ETA.

---

## 12. End-to-end walkthrough
| Step | Log in as | Call |
|---|---|---|
| 1 | customer | `POST /cart/items` → `{"menu_item_id":1,"quantity":2}` |
| 2 | customer | `POST /cart/apply-coupon` → `{"code":"BIRYANI20"}` |
| 3 | customer | `POST /orders` → `{"address_id":1,"payment_method":"Online","tip_amount":20}`; note `id` and `delivery_otp` |
| 4 | owner | `PUT /orders/{id}/accept` → `{"estimated_preparation_minutes":15}` |
| 5 | partner1 (or partner2) | `GET /partners/me/offers`, then `PUT /offers/{offer_id}/accept` within 30 seconds |
| 6 | owner | `PUT /orders/{id}/preparing`, then `PUT /orders/{id}/ready` |
| 7 | partner | `PUT /orders/{id}/pickup`, `/out-for-delivery`, then `PUT /orders/{id}/deliver` → `{"otp":"<otp>"}` |
| 8 | customer | `POST /orders/{id}/rating` → `{"restaurant_rating":5,"partner_rating":5}` |

Then open the reports as admin, owner and partner.

---

## 13. Testing

**Unit tests** (Haversine, delivery fee and surge, bill formula, discount caps, partner earnings):
```bash
python -m pytest -q
```

**End-to-end smoke test** (server running and database seeded, in a second terminal):
```bash
python smoke_test.py
```
It logs in as every role, runs the full order lifecycle, checks the 401/403/422 cases, tests the WebSockets and
prints `PASS` or `FAIL` per check. It creates real rows on each run. Because `GET /orders` and
`GET /orders/{order_id}` are customer-only in this version, the checks "GET /orders (admin sees all)",
"GET /orders/{id} as owner" and "owner does NOT see delivery_otp" are expected to report `FAIL` (they get 403).

---

## 14. Troubleshooting
| Problem | Fix |
|---|---|
| `pydantic-core` build fails, `link.exe not found` | You are on Python 3.14. Use Python 3.12. |
| `source` is not recognized (PowerShell) | Use `.\venv\Scripts\Activate.ps1` |
| Running scripts is disabled | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| Access denied or cannot connect to MySQL | Check user, password and host in `DATABASE_URL`; MySQL must be running. |
| `Table already exists` on migrate | Drop and recreate the database, then run `alembic upgrade head`. |
| bcrypt or passlib error | `pip install bcrypt==4.0.1` |
| Nearby search returns nothing | Restaurants must be open now and within their radius; use the sample coordinates. |
| 403 "awaiting admin approval" | Approve the owner or partner with `PUT /admin/users/{id}/approve` as admin. |
| Alembic cannot import `app` | Run commands from the project root with the venv active. |

---

## 15. Assumptions
- Times are naive server-local time. "Open" means `opening_time <= now <= closing_time` and not temporarily closed.
- Money is stored as `DECIMAL(10,2)` and handled as floats rounded to 2 decimals.
- Reports and the top-restaurants ranking count `Delivered` orders only.
- The nearby `has_offers` filter matches restaurants with an active in-date coupon, or any platform-wide coupon.
- A partner who declined or let an offer expire is not offered the same order again; newly online partners are
  picked up by the 1-minute retry job.
- Offers go only to partners with a stored location within 5 km of the restaurant.
- Partner earnings use the straight-line restaurant-to-customer distance.
- Owners and partners can log in before approval but get 403 on restricted actions.
- Deleting an address that is used by an order returns 409 (orders keep their address reference).
- The OTP is shown only to the customer; three wrong attempts lock delivery (403) and create an admin notification.
- **`GET /orders` and `GET /orders/{order_id}` are customer-only** in this version. Owners see their orders through
  `GET /restaurants/me/orders` and partners through the delivery endpoints and WebSocket. The assignment also asks for
  Admin to "view all orders"; this is not available through these two endpoints. To restore it, use
  `require_roles(CUSTOMER, ADMIN)` on both and filter by customer only when the caller is a customer.
- Bonus items: surge pricing, tests and Docker are included; scheduled orders are not implemented.
- Swagger and live-tracking screenshots must be captured by running the app.
