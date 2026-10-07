# E-Commerce Order Management System

A FastAPI backend for an E-Commerce Order Management System with MySQL, SQLAlchemy, Alembic, JWT authentication, role-based access control, carts, orders, payments, returns/refunds, reviews, coupons, reports, password reset, and email notifications.

## Tech Stack

- Python 3.9+
- FastAPI
- Pydantic
- SQLAlchemy
- MySQL
- Alembic
- JWT Authentication
- Passlib + bcrypt
- Uvicorn
- SMTP / Gmail App Password or Mailtrap
- FastAPI BackgroundTasks

## Project Structure

```text
ecommerce_order_management/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── auth/
│   │   └── dependencies.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   └── utils/
├── alembic/
│   └── versions/
├── scripts/
│   └── create_admin.py
├── tests/
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Features

### Authentication
- Customer-only public registration
- Admin accounts created manually
- JWT authentication with 30-minute expiry
- `GET /auth/me`
- Password hashing
- Forgot password
- Password reset tokens
- Change password
- Admin/Customer role-based authorization

### Categories
- Admin create/update/delete
- Public category listing
- Unique category names
- Category deletion blocked when products use the category

### Products
- Admin CRUD
- Unique SKU
- Price and stock validation
- Soft delete with `is_active`
- Product search/filtering
- Category and price filters
- In-stock filter
- Sorting and pagination

### Cart
- One cart per customer
- Add/update/remove items
- Duplicate product increases quantity
- Stock validation
- Subtotal calculation

### Addresses
- Multiple addresses
- One default address
- 10-digit Indian mobile validation starting with 6/7/8/9
- 6-digit pincode validation

### Orders
- Cart checkout
- Transaction-safe stock deduction
- Order number generation
- GST calculation
- Delivery charge
- Free delivery above configured threshold
- Coupon support
- Price snapshots
- Customer cancellation
- Admin status management

### Payments
- UPI
- Card
- Net Banking
- COD
- Exact amount validation
- Unique transaction ID
- Successful/failed payments
- Refund status

### Returns and Refunds
- Delivered orders only
- Seven-day return window
- One return per order
- Admin approval/rejection
- Refund processing
- Stock restoration
- Rejection reason

### Reviews
- Only customers who purchased and received the product can review
- One review per customer/product
- Own review update/delete
- Product average rating and review count

### Coupons
- Percentage and flat discounts
- Minimum order value
- Expiry date
- Usage limit
- `used_count` tracking
- Admin create/list
- Coupon application during order creation

### Email Notifications
Background email notifications for:
- Registration
- Order placed
- Payment successful
- Order shipped
- Order delivered
- Order cancelled
- Return approved/refunded
- Return rejected

Email failures are logged without failing the main business transaction.

### Reports
Admin-only:
- Sales report
- Orders by status
- Top 5 products
- Low-stock products

## Roles

### Admin
Admin can:
- Manage categories
- Manage products
- Create and view coupons
- View all orders
- Update order status
- View/approve/reject returns
- View reports

Admin registration is not public.

Create an admin with:

```powershell
python -m scripts.create_admin
```

### Customer
Customers can:
- Register/login
- Browse products/categories
- Manage addresses
- Manage cart
- Place orders
- Make payments
- Cancel eligible orders
- Request returns
- Write reviews
- Reset/change password
- Apply coupons during checkout

Customers cannot access Admin-only operations.

## Installation

Create a virtual environment:

```powershell
python -m venv venv
```

Activate:

```powershell
.env\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Python 3.11 or 3.12 is recommended for package compatibility.

## MySQL Setup

Create the database:

```sql
CREATE DATABASE ecommerce_db;
```

Alembic is used for schema management. Do not use `Base.metadata.create_all()` as a replacement for migrations.

## Environment Variables

Create `.env` in the project root:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/ecommerce_db

JWT_SECRET_KEY=your-strong-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM_EMAIL=your_email@gmail.com

GST_RATE=0.18
DELIVERY_CHARGE=50
FREE_DELIVERY_THRESHOLD=500
```

Never commit `.env`. Commit only `.env.example`.

## Gmail SMTP

Use a Gmail App Password rather than your normal Gmail password.

1. Enable 2-Step Verification.
2. Open Google Account security settings.
3. Create an App Password.
4. Put it in `SMTP_PASSWORD`.

Mailtrap can also be used for development.

## Alembic

Check current migration:

```powershell
alembic current
```

View history:

```powershell
alembic history
```

Apply migrations:

```powershell
alembic upgrade head
```

Create a migration:

```powershell
alembic revision -m "description of change"
```

Review autogenerated migrations before applying them. Avoid blindly applying migrations that try to remove unrelated tables, columns, indexes, or constraints.

## Create Admin

Run:

```powershell
python -m scripts.create_admin
```

Then log in through:

```text
POST /auth/login
```

## Run FastAPI

```powershell
uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

# API Endpoints

## Authentication

```text
POST /auth/register
POST /auth/login
GET  /auth/me
POST /auth/forgot-password
POST /auth/reset-password
POST /auth/change-password
```

Public registration always creates a Customer.

## Categories

```text
POST   /categories          Admin
GET    /categories          Public
PUT    /categories/{id}     Admin
DELETE /categories/{id}     Admin
```

Delete response:

```json
{
  "message": "Category deleted successfully",
  "category_id": 1,
  "category_name": "Electronics"
}
```

## Products

```text
POST   /products
GET    /products
GET    /products/{id}
PUT    /products/{id}
DELETE /products/{id}
```

Example:

```json
{
  "name": "Samsung Galaxy S24",
  "sku": "SAM-S24-001",
  "description": "Samsung smartphone",
  "category_id": 1,
  "price": 74999,
  "stock_quantity": 20,
  "is_active": true
}
```

Product deletion is a soft delete.

Supported product query parameters include:

```text
name
category_id
min_price
max_price
in_stock
sort_by
order
skip
limit
```

## Cart

```text
GET    /cart
POST   /cart/items
PUT    /cart/items/{item_id}
DELETE /cart/items/{item_id}
DELETE /cart
```

## Addresses

```text
POST   /addresses
GET    /addresses
PUT    /addresses/{id}
DELETE /addresses/{id}
PUT    /addresses/{id}/default
```

## Orders

```text
POST /orders
GET  /orders
GET  /orders/{id}
PUT  /orders/{id}/cancel
PUT  /orders/{id}/status
```

`PUT /orders/{id}/status` is Admin-only.

Valid status flow:

```text
Pending -> Confirmed -> Shipped -> Delivered
```

Cancellation is allowed from Pending or Confirmed.

## Payments

```text
POST /orders/{id}/pay
GET  /orders/{id}/payments
```

Payment methods:

```text
UPI
Card
Net Banking
COD
```

## Returns

```text
POST /orders/{id}/returns
GET  /returns
PUT  /returns/{id}/approve
PUT  /returns/{id}/reject
```

Only Delivered orders within seven days can be returned.

## Reviews

```text
POST   /products/{product_id}/reviews
GET    /products/{product_id}/reviews
PUT    /reviews/{review_id}
DELETE /reviews/{review_id}
```

## Coupons

```text
POST /coupons
GET  /coupons
```

Admin creates coupons.

Example:

```json
{
  "code": "OFFER11",
  "coupon_type": "Percentage",
  "value": 11,
  "minimum_order_value": 1110,
  "expires_at": "2026-10-15T23:59:59",
  "usage_limit": 11
}
```

The current coupon database design uses:

```text
used_count
```

and does not use the obsolete:

```text
usage_count
is_active
```

Coupon application is performed during order creation, for example:

```text
POST /orders?address_id=1&coupon_code=OFFER11
```

## Reports

Admin-only:

```text
GET /reports/sales
GET /reports/orders-by-status
GET /reports/top-products
GET /reports/low-stock
```

## Order Calculation

```text
Subtotal = sum of item line totals

Discount = coupon discount

Taxable Amount = Subtotal - Discount

GST = Taxable Amount × GST_RATE

Delivery = ₹0 if taxable amount > FREE_DELIVERY_THRESHOLD
           otherwise ₹50

Grand Total = Taxable Amount + GST + Delivery
```

Example:

```text
Subtotal       = ₹2000
Coupon 10%     = ₹200
Taxable amount = ₹1800
GST 18%        = ₹324
Delivery       = ₹0
Grand Total    = ₹2124
```

## Order Transaction

Order placement performs:

1. Address validation
2. Cart validation
3. Product row locking
4. Stock validation
5. Price calculation
6. Coupon validation
7. GST calculation
8. Delivery calculation
9. Order creation
10. Order-item creation
11. Stock deduction
12. Coupon usage update
13. Cart clearing
14. Commit

Any failure rolls back the transaction.

## Payment Rules

- Payment amount must equal the grand total.
- Double payment is blocked.
- Successful payment sets payment status to Paid.
- Failed payments can be retried.
- Cancelled orders cannot be paid.
- COD is handled according to the order/payment business rules.

## Return and Refund Rules

Return is allowed only when:

```text
Order status = Delivered
```

and the request is within seven days.

Admin approval:

```text
Requested -> Approved -> Refunded
```

Approval restores stock and refunds the order grand total.

Rejection requires a rejection reason.

# Swagger Testing

Open:

```text
http://127.0.0.1:8000/docs
```

## Admin Test Sequence

```text
1.  POST /auth/login
2.  GET  /auth/me
3.  POST /categories
4.  GET  /categories
5.  PUT  /categories/{id}
6.  POST /products
7.  GET  /products
8.  GET  /products/{id}
9.  PUT  /products/{id}
10. DELETE /products/{id}
11. POST /coupons
12. GET  /coupons
13. GET  /orders
14. GET  /orders/{id}
15. PUT  /orders/{id}/status
16. GET  /returns
17. PUT  /returns/{id}/approve
    OR
    PUT  /returns/{id}/reject
18. GET /reports/sales
19. GET /reports/orders-by-status
20. GET /reports/top-products
21. GET /reports/low-stock
```

## Customer Test Sequence

```text
1.  POST /auth/register
2.  POST /auth/login
3.  GET  /auth/me
4.  POST /auth/forgot-password
5.  POST /auth/reset-password
6.  POST /auth/change-password
7.  GET  /categories
8.  GET  /products
9.  POST /addresses
10. PUT  /addresses/{id}/default
11. POST /cart/items
12. PUT  /cart/items/{item_id}
13. POST /orders
14. POST /orders/{id}/pay
15. PUT  /orders/{id}/cancel
16. POST /orders/{id}/returns
17. POST /products/{product_id}/reviews
18. PUT  /reviews/{review_id}
19. DELETE /reviews/{review_id}
```

## Authorization Testing

No JWT:

```text
401 Unauthorized
```

Customer trying Admin endpoint:

```text
403 Forbidden
```

Admin:

```text
200 OK / 201 Created
```

After changing a user's role, log in again to obtain a new JWT.

# Email Notifications

Background email events:

```text
Registration successful
Order placed
Payment successful
Order shipped
Order delivered
Order cancelled
Return approved/refunded
Return rejected
```

Check Uvicorn logs if email delivery fails.

The main business transaction should not fail only because an email could not be sent.

# Security

- JWT authentication
- Role-based access control
- Password hashing
- Customer ownership checks
- Admin-only management operations
- Environment variables for secrets
- SMTP credentials stored in `.env`
- No public Admin registration

Never commit:

```text
.env
venv/
__pycache__/
passwords
JWT secrets
SMTP credentials
```

# Git

```powershell
git init
git add .
git commit -m "Initial e-commerce order management system"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Recommended `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
*.log

venv/
.venv/
env/

.env

.vscode/
.idea/

.pytest_cache/
.coverage
htmlcov/

*.sqlite3
*.db

.DS_Store
Thumbs.db
```

# Troubleshooting

## 401 Unauthorized

Check that:
- You logged in.
- You copied the access token.
- Swagger is authorized.
- The token has not expired.
- The Bearer token is being sent.

## 403 Forbidden

The JWT is valid but the user lacks the required role.

Check:

```sql
SELECT id, email, role FROM users;
```

Admin must have:

```text
Admin
```

Log in again after changing a role.

## 422 Validation Error

Check required fields, data types, IDs, dates, phone numbers, pincodes, and enum values.

## Coupon schema mismatch

Check:

```sql
DESCRIBE coupons;
```

The current design should contain:

```text
used_count
```

and should not contain:

```text
usage_count
is_active
```

## Alembic

```powershell
alembic current
alembic history
alembic upgrade head
```

Use explicit, reviewed migrations for schema cleanup.

# Submission Checklist

```text
[ ] GitHub repository
[ ] README.md
[ ] requirements.txt
[ ] .env.example
[ ] .gitignore
[ ] Alembic migrations
[ ] Admin test credentials documented securely
[ ] Customer test credentials documented securely
[ ] Swagger screenshots
[ ] Order placed email screenshot
[ ] Order shipped email screenshot
[ ] Refund processed email screenshot
```

# Final Admin Checklist

```text
[ ] Admin login
[ ] GET /auth/me
[ ] Create category
[ ] List categories
[ ] Update category
[ ] Delete category
[ ] Create product
[ ] List products
[ ] Search/filter products
[ ] Get product
[ ] Update product
[ ] Soft delete product
[ ] Create coupon
[ ] List coupons
[ ] List all orders
[ ] View order details
[ ] Update order status
[ ] View returns
[ ] Approve return
[ ] Reject return
[ ] Sales report
[ ] Orders by status
[ ] Top products
[ ] Low stock report
```

# Final Customer Checklist

```text
[ ] Customer registration
[ ] Customer login
[ ] GET /auth/me
[ ] Forgot password
[ ] Reset password
[ ] Change password
[ ] Browse categories
[ ] Browse products
[ ] Search/filter products
[ ] Create address
[ ] Set default address
[ ] Add item to cart
[ ] Update cart
[ ] Remove cart item
[ ] Place order
[ ] Apply coupon
[ ] Make payment
[ ] Cancel eligible order
[ ] Request return
[ ] Add review
[ ] Update own review
[ ] Delete own review
```
