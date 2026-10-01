# Employee & Leave Management System

A backend REST API built with **Python, FastAPI, SQLAlchemy, MySQL, Alembic, JWT Authentication, Passlib, and bcrypt** for managing users, departments, employees, and leave requests.

## Technology Stack

- Python 3.9+
- FastAPI
- Pydantic
- SQLAlchemy
- MySQL
- PyMySQL
- Alembic
- JWT Authentication
- Passlib / bcrypt
- Uvicorn
- python-dotenv

## Roles

### Admin
- Full system access
- Manage departments
- Create, update, and deactivate employees
- Manage leaves
- Approve/reject leaves
- Reset employee passwords
- View reports

### HR
- Manage employees
- Create, update, and deactivate employees
- Reset employee passwords
- View and manage leaves
- Approve/reject leaves
- View reports

### Employee
- View own profile
- Update own permitted personal details
- Apply for leave
- View own leave history
- View own leave balance
- Cancel own pending leave

Employees cannot manage departments, other employees, salaries, departments, designations, employment type, joining date, employee code, active status, or employee passwords.

## Project Structure

```text
employee_leave_management_system/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── auth/
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── models/
│   │   ├── user.py
│   │   ├── department.py
│   │   ├── employee.py
│   │   └── leave_request.py
│   ├── schemas/
│   │   ├── user.py
│   │   ├── department.py
│   │   ├── employee.py
│   │   └── leave_request.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── departments.py
│   │   ├── employees.py
│   │   ├── leaves.py
│   │   └── reports.py
│   └── services/
│       └── leave_service.py
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_employee_leave.py
│   └── env.py
├── alembic.ini
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Authentication

### Register

```http
POST /auth/register
```

Example:

```json
{
  "username": "admin",
  "email": "admin@gmail.com",
  "password": "Admin@123"
}
```

### Login

```http
POST /auth/login
```

Example:

```json
{
  "username": "admin",
  "password": "Admin@123"
}
```

Use the returned JWT token in Swagger:

```text
Authorize
Bearer <access_token>
```

### Current User

```http
GET /auth/me
```

## Automatic Employee User Account

When Admin or HR creates an employee, the application automatically creates a linked Employee user account.

- Username = employee name
- Email = employee email
- Role = Employee
- Password = generated temporary password
- Employee is linked to the User through `user_id`

The temporary password is returned in the employee creation response.

Example:

```json
{
  "employee_id": 1,
  "user_id": 3,
  "employee_code": "EMP001",
  "name": "Rahul Kumar",
  "email": "rahul@gmail.com",
  "username": "Rahul Kumar",
  "temporary_password": "A7xP2mQ9!kL3",
  "role": "Employee"
}
```

If the employee changes their name through the allowed self-update operation, the linked username is also updated.

## Employee Password Reset

Original passwords cannot be recovered because only bcrypt hashes are stored.

Admin and HR can generate a new temporary password:

```http
POST /employees/{employee_id}/reset-password
```

Example response:

```json
{
  "employee_id": 1,
  "user_id": 3,
  "username": "Rahul Kumar",
  "temporary_password": "X8kP2mL9@qR4",
  "message": "Employee password reset successfully"
}
```

## Department APIs

```text
POST   /departments
GET    /departments
GET    /departments/{department_id}
PATCH  /departments/{department_id}
DELETE /departments/{department_id}
GET    /departments/{department_id}/employees
```

Department creation, update, and deletion are Admin-only.

A department cannot be deleted while it has active employees.

Example:

```json
{
  "department_name": "IT"
}
```

## Employee APIs

```text
POST   /employees
GET    /employees
GET    /employees/{employee_id}
PATCH  /employees/{employee_id}
DELETE /employees/{employee_id}
POST   /employees/{employee_id}/reset-password
GET    /employees/{employee_id}/leaves
GET    /employees/{employee_id}/leave-balance
```

### Create Employee

Admin/HR only.

Example:

```json
{
  "employee_code": "EMP001",
  "name": "Rahul Kumar",
  "email": "rahul@gmail.com",
  "phone": "9876543210",
  "department_id": 1,
  "designation": "Python Developer",
  "salary": 45000,
  "date_of_joining": "2026-09-30",
  "employment_type": "Full-Time",
  "is_active": true
}
```

### Employee Self-Update

Employees can update only their own permitted personal information.

Example:

```json
{
  "name": "Rahul Reddy",
  "phone": "9876543211"
}
```

Employees cannot change salary, department, designation, employee code, joining date, employment type, or active status.

### Employee Deletion

```http
DELETE /employees/{employee_id}
```

This is a soft delete. The employee's `is_active` value is changed to `false`.

## Leave APIs

```text
POST   /leaves
GET    /leaves
GET    /leaves/{leave_id}
POST   /leaves/{leave_id}/approve
POST   /leaves/{leave_id}/reject
POST   /leaves/{leave_id}/cancel
```

Employee-specific endpoints:

```text
GET /employees/{employee_id}/leaves
GET /employees/{employee_id}/leave-balance
```

## Leave Types

- Sick
- Casual
- Earned

## Leave Statuses

- Pending
- Approved
- Rejected
- Cancelled

## Annual Leave Balance

| Leave Type | Annual Balance |
|---|---:|
| Sick | 12 |
| Casual | 10 |
| Earned | 15 |

## Leave Business Rules

1. Leave can be applied only for weekdays.
2. Past leave dates are not allowed.
3. Start date cannot be after end date.
4. Overlapping leave requests are not allowed.
5. Insufficient balance prevents application.
6. Balance is deducted only after approval.
7. Only Pending requests can be approved.
8. Only Pending requests can be rejected.
9. Only Pending requests can be cancelled.
10. Rejection reason is required.
11. Inactive employees cannot apply for leave.
12. HR cannot approve their own leave.

### Apply Leave

```http
POST /leaves
```

Example:

```json
{
  "leave_type": "Sick",
  "start_date": "2026-10-05",
  "end_date": "2026-10-07",
  "reason": "Medical leave"
}
```

### Reject Leave

```http
POST /leaves/{leave_id}/reject
```

Example:

```json
{
  "rejection_reason": "Insufficient staffing during the requested period"
}
```

## Database Tables

### users

```text
user_id
username
email
password_hash
role
is_active
created_at
updated_at
```

### departments

```text
department_id
department_name
created_at
updated_at
```

### employees

```text
employee_id
user_id
employee_code
name
email
phone
department_id
designation
salary
date_of_joining
employment_type
is_active
created_at
updated_at
```

### leave_requests

```text
leave_id
employee_id
leave_type
start_date
end_date
total_days
reason
status
rejection_reason
approved_by
approved_at
created_at
updated_at
```

## Database Relationships

```text
Department 1 ──────── * Employees
Employee   1 ──────── * Leave Requests
User       1 ──────── 1 Employee
```

## Environment Configuration

Create `.env` in the project root:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/employee_leave_db
JWT_SECRET_KEY=my-super-secret-key
JWT_ALGORITHM=HS256
```

Do not commit `.env` to GitHub.

Commit `.env.example` instead:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/employee_leave_db
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
```

## MySQL Setup

```sql
CREATE DATABASE employee_leave_db;
```

Then:

```sql
USE employee_leave_db;
```

Tables are created and managed through Alembic.

The application should not use `Base.metadata.create_all()`.

## Virtual Environment

Windows:

```powershell
cd C:\Users\indra\OneDrive\Desktop\Stackly-Tasks\employee_leave_management_system
python -m venv venv
venv\Scripts\activate
```

If PowerShell blocks activation, use Command Prompt:

```cmd
venv\Scripts\activate
```

## Install Dependencies

```powershell
pip install -r requirements.txt
```

Or:

```powershell
pip install fastapi uvicorn sqlalchemy pymysql alembic python-dotenv python-jose passlib bcrypt pydantic
```

## Alembic

The project uses a single initial migration:

```text
alembic/versions/0001_initial_employee_leave.py
```

Run:

```powershell
alembic upgrade head
```

Check migration:

```powershell
alembic current
```

## Run FastAPI

```powershell
uvicorn app.main:app --reload
```

Application:

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

## Recommended Swagger Testing Flow

1. Login as Admin using `POST /auth/login`.
2. Copy the JWT token and click `Authorize`.
3. Create a department using `POST /departments`.
4. Create an employee using `POST /employees`.
5. Save the returned temporary password.
6. Login as the employee using the employee name and temporary password.
7. Use `GET /auth/me` to verify the employee account.
8. Use `PATCH /employees/{employee_id}` to update allowed personal details.
9. Apply leave using `POST /leaves`.
10. Login as Admin/HR and approve or reject the leave.
11. Check the employee balance using `GET /employees/{employee_id}/leave-balance`.

## Validation

### Phone

Phone number must:
- Contain exactly 10 digits
- Contain digits only
- Start with 6, 7, 8, or 9

Valid:

```text
9876543210
8123456789
7012345678
```

Invalid:

```text
1234567890
987654321
987654321A
+919876543210
```

### Salary

Salary must be greater than zero.

### Joining Date

Joining date cannot be in the future.

### Employee Code

Employee code must be unique.

### Email

Employee email must be unique.

### Department

Department must exist before assigning it to an employee.

## HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 | Successful request |
| 201 | Resource created |
| 400 | Bad request/business rule violation |
| 401 | Authentication required/invalid or expired token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Duplicate/conflict |
| 422 | Validation error |

## Security

The application implements:

- JWT authentication
- 30-minute JWT expiration
- Password hashing with bcrypt
- Role-based access control
- Protected routes
- Inactive-user restrictions
- Unique usernames
- Unique email addresses
- Environment-based secrets
- Secure password storage

Passwords are never stored as plain text.

## Useful MySQL Queries

### View Users

```sql
SELECT user_id, username, email, role, is_active, created_at
FROM users;
```

### View Employee/User Relationship

```sql
SELECT
    e.employee_id,
    e.user_id,
    e.employee_code,
    e.name,
    e.email,
    u.username,
    u.role,
    u.is_active
FROM employees e
JOIN users u ON e.user_id = u.user_id;
```

### View Employees

```sql
SELECT * FROM employees;
```

### View Departments

```sql
SELECT * FROM departments;
```

### View Leave Requests

```sql
SELECT * FROM leave_requests;
```

## .gitignore

```gitignore
__pycache__/
*.py[cod]

venv/
.env

.vscode/
.idea/

*.log

.pytest_cache/
.mypy_cache/
```

## requirements.txt

```text
fastapi
uvicorn
sqlalchemy
pymysql
alembic
python-dotenv
python-jose
passlib
bcrypt
pydantic
```

## Complete API Summary

### Authentication

```text
POST /auth/register
POST /auth/login
GET  /auth/me
```

### Departments

```text
POST   /departments
GET    /departments
GET    /departments/{department_id}
PATCH  /departments/{department_id}
DELETE /departments/{department_id}
GET    /departments/{department_id}/employees
```

### Employees

```text
POST   /employees
GET    /employees
GET    /employees/{employee_id}
PATCH  /employees/{employee_id}
DELETE /employees/{employee_id}
POST   /employees/{employee_id}/reset-password
GET    /employees/{employee_id}/leaves
GET    /employees/{employee_id}/leave-balance
```

### Leaves

```text
POST /leaves
GET  /leaves
GET  /leaves/{leave_id}
POST /leaves/{leave_id}/approve
POST /leaves/{leave_id}/reject
POST /leaves/{leave_id}/cancel
```

### Reports

```text
GET /reports/dashboard
GET /reports/leave-summary
```

## Important Notes

- Run `alembic upgrade head` before API testing.
- Do not use `Base.metadata.create_all()` for the application database.
- Keep `.env` out of GitHub.
- Commit `.env.example`.
- Save employee temporary passwords securely.
- If a temporary password is lost, Admin or HR can reset it.
- Employees can update only their own permitted personal details.
- Employees cannot change salary, department, designation, employee code, joining date, employment type, or active status.
- Only Admin and HR can manage employee accounts.
- Only Admin and HR can approve or reject leave requests.
- Leave balance is deducted only after approval.

## Quick Start

```powershell
cd C:\Users\indra\OneDrive\Desktop\Stackly-Tasks\employee_leave_management_system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

## Project Status

The system includes:

- FastAPI REST API
- MySQL database
- SQLAlchemy ORM
- Alembic migration
- JWT authentication
- Admin, HR, and Employee roles
- Role-based authorization
- Department management
- Employee management
- Automatic employee user accounts
- Employee password reset
- Employee self-update restrictions
- Leave application
- Leave approval/rejection/cancellation
- Leave balance management
- Leave validation
- Pagination
- Filtering
- Reports
- Swagger documentation
- Environment configuration
- Secure password hashing
