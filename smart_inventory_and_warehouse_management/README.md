# Smart Inventory & Warehouse Management System

A FastAPI backend for managing products, warehouses, inventory, suppliers, purchase orders, sales orders, returns, stock movements, reports, notifications, and audit logs.

## Tech Stack

- Python 3.9+
- FastAPI and Pydantic
- SQLAlchemy and MySQL
- Alembic migrations
- JWT authentication and role-based access control
- Passlib/bcrypt password hashing
- FastAPI BackgroundTasks and SMTP email notifications
- Pytest and Uvicorn

## Main Features

- Authentication and protected APIs
- Role-based permissions
- Product and category catalog
- Warehouse management
- Inventory and stock movement tracking
- Supplier and customer records
- Purchase order creation, approval, and receiving
- Sales order processing, stock reservation, picking, packing, dispatch, and delivery
- Returns workflow
- Transfers and stock adjustments
- Reports and audit logs
- Low-stock and order-related email notifications, when configured
- Alembic database migrations and automated tests

## Roles

- **Admin** — administrative setup and privileged operations.
- **Inventory Manager** — inventory workflows permitted by the application's role rules.
- **Warehouse Staff** — warehouse-floor workflows permitted by the application's role rules.

Customers and suppliers are business records, not necessarily application login roles. Check the current code and schemas for the exact role enum values and permissions.

## Project Structure

```text
smart_inventory/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── auth/
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── models/
│   │   ├── all.py
│   │   └── __init__.py
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── alembic/
│   └── versions/
├── scripts/
│   └── create_admin.py
├── tests/
├── .env.example
├── alembic.ini
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.9+
- MySQL Server
- PowerShell or the VS Code terminal

## 1. Open the Project

Open a terminal in the project root (the folder containing `app`, `alembic.ini`, and `requirements.txt`):

```powershell
cd path\to\smart_inventory
```

## 2. Create and Activate a Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

```bat
venv\Scripts\activate.bat
```

Or temporarily allow activation in the current PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Create the MySQL Database

Create the database name expected by your `.env` configuration. Example:

```sql
CREATE DATABASE smart_inventory_db;
```

If your project uses another database name, create that database instead.

## 5. Configure Environment Variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your local values. A typical configuration looks like this:

```dotenv
DATABASE_URL=mysql+pymysql://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:3306/smart_inventory_db
SECRET_KEY=replace_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_email_app_password
SMTP_FROM_EMAIL=your_email@example.com
```

These are examples only. **Use the exact variable names required by your project's settings file.** Replace all placeholders. Do not commit `.env` or real credentials to GitHub; commit `.env.example` with placeholders only.

## 6. Apply Database Migrations

Run from the project root:

```powershell
alembic upgrade head
```

Check the current migration:

```powershell
alembic current
```

Review Alembic configuration and model imports before generating new migrations. Do not delete or edit migration history casually.

## 7. Create the Initial Admin

If the project contains `scripts/create_admin.py`, run it from the project root:

```powershell
python -m scripts.create_admin
```

Follow the script output and verify that the account can log in. Change any default or temporary password before using the system beyond local testing. Admin accounts should be created through the authorized backend setup process, not public customer registration unless the code explicitly allows it.

If you see a Passlib/bcrypt compatibility warning, check the installed versions and `requirements.txt`, then verify that password hashing and login both work. Do not rely only on a printed success message.

## 8. Start the API

```powershell
uvicorn app.main:app --reload
```

Open:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

Use the Health section in Swagger to find the health-check route. Stop the server with `Ctrl+C`.

## 9. Log In Through Swagger

1. Open `http://127.0.0.1:8000/docs`.
2. Find the login endpoint under **Authentication**.
3. Submit the credentials for an existing user.
4. Copy the access token from the response.
5. Click **Authorize**.
6. For HTTP Bearer authentication, paste only the token in the token field; Swagger adds `Bearer` automatically.
7. Test protected endpoints.

If Swagger shows OAuth2 username/password/client fields instead of a token field, confirm that the OpenAPI security scheme and authentication dependencies match the intended authentication method.

## 10. Suggested API Testing Flow

Use the exact endpoint paths, request bodies, enum values, and required fields shown in your running Swagger documentation.

### Admin

1. Log in and test the current-user endpoint, if available.
2. Create staff accounts through the authorized admin workflow.
3. Create warehouses, categories, products, suppliers, and customers as allowed by the code.
4. Create a purchase order with a valid supplier and product IDs.
5. Approve the purchase order if required, then receive its items.
6. Verify inventory and stock movements.
7. Create a sales order, then follow the configured confirmation, picking, packing, dispatch, and delivery steps.
8. Test returns, reports, audit logs, transfers, and adjustments where permitted.

### Inventory Manager

1. Log in with a manager account.
2. Test inventory and stock movement views.
3. Create and process purchase orders according to the configured workflow.
4. Test the sales-order and return workflows permitted to this role.
5. Test reports and other manager-authorized endpoints.
6. Confirm that admin-only endpoints reject the manager when appropriate.

### Warehouse Staff

1. Log in with a warehouse-staff account.
2. View the products, warehouses, inventory, purchase orders, and sales orders available to the role.
3. Test receiving, picking, packing, dispatch, transfer, or adjustment steps that the code permits.
4. Confirm that catalog administration, order approval, reports, or audit endpoints are denied when they are outside the role's permissions.
5. Check whether warehouse assignment is required for warehouse operations.

### Security Checks

- No token, invalid token, or expired token: expect `401 Unauthorized`.
- Valid token without permission: expect `403 Forbidden`.
- Missing resource: expect `404 Not Found` where implemented.
- Invalid quantities, duplicate identifiers, and invalid state transitions should be rejected by validation/business rules.

**Inventory note:** Do not assume a direct endpoint exists to manually create inventory. In the intended workflow, stock is generally changed through supported operations such as purchase-order receiving, sales dispatch, returns, transfers, or adjustments. Confirm the actual routes in Swagger.

## 11. Test Low-Stock Email Notifications

1. Configure valid SMTP settings in `.env`.
2. Restart the API after changing environment variables.
3. Create or update a product with a low-stock threshold using the actual schema.
4. Reduce stock through a supported operation until the alert condition is met.
5. Check server logs and the recipient mailbox.
6. Confirm that the stock-changing operation calls the notification logic.

If SMTP times out, verify the host, port, credentials, network/firewall access, provider requirements, and TLS mode. Port 587 commonly uses STARTTLS, while port 465 commonly uses implicit SSL; the code must match the chosen port. A successful API response does not guarantee email delivery.

## 12. Reports Dashboard Is Empty

Reports may return empty results if no matching transactions exist. Try this order:

1. Create a category, product, warehouse, supplier, and customer.
2. Create and receive a purchase order.
3. Create and process a sales order.
4. Call the report endpoint again.
5. Check date ranges, status filters, and warehouse/product filters.
6. Inspect the response and server logs if the result is still empty.

## 13. Run Tests

If tests are included:

```powershell
pytest
```

For detailed output:

```powershell
pytest -v
```

Use a dedicated test database and avoid running destructive tests against production data.

## 14. Common Issues

### `ModuleNotFoundError: No module named 'app'`
Run commands from the project root. For scripts in the `scripts` package, use module execution where appropriate:

```powershell
python -m scripts.create_admin
```

### Model import error
Check imports against the actual model layout. If models are consolidated in `app/models/all.py` and exported from `app/models/__init__.py`, do not import from a nonexistent `app.models.user` module.

### `401 Unauthorized`
- Log in again and use a fresh token.
- Check token expiry and the JWT secret.
- Confirm that the token's `sub` claim has the format expected by `get_current_user` (for example, a numeric user ID if the code converts it to `int`).

### `403 Forbidden`
The account is authenticated but does not have permission for the endpoint. Use an authorized role rather than removing permission checks.

### MySQL connection error
- Confirm MySQL is running.
- Check database name, username, password, host, and port.
- Ensure the database exists and the configured driver is installed.

### Alembic migration error
Check `.env`, database connectivity, `alembic current`, and files in `alembic/versions`. Do not mark a migration applied unless the schema really matches.

### Passlib/bcrypt warning
Check compatibility between the installed `passlib` and `bcrypt` versions and the versions pinned in `requirements.txt`. Verify password hashing and login after correcting the environment.

### SMTP timeout
Check host, port, TLS mode, credentials, firewall/network access, and email-provider restrictions.

### `PO item not found`
Use a purchase-order item ID belonging to the specific purchase order being received. Fetch the purchase order and its items first, then use the matching item ID in the receive request.

## 15. `.gitignore` Suggestions

Review your existing `.gitignore` before replacing it. A typical file includes:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo

# Virtual environments
venv/
.venv/
env/

# Environment secrets
.env
.env.*
!.env.example

# Test and coverage
.pytest_cache/
.coverage
htmlcov/

# Logs
*.log

# IDEs
.vscode/
.idea/

# Operating system
.DS_Store
Thumbs.db
```

## 16. Security Checklist

- Never commit `.env` or credentials.
- Use a strong, random JWT secret.
- Change default/bootstrap passwords.
- Enforce role checks on protected endpoints.
- Validate quantities, IDs, order states, and stock changes.
- Use a separate database for tests.
- Do not log passwords, access tokens, or SMTP secrets.
- Configure HTTPS and secure secret storage before deployment.

## Final Note

This README covers setup and the intended workflows. The checked-out code is the source of truth for exact endpoint paths, request fields, environment-variable names, role values, and permissions. Use the running `/docs` page and the current schemas to confirm those details before sending requests.
