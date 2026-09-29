# Library Management System

A backend Library Management System built using Python, FastAPI, SQLAlchemy, MySQL, JWT Authentication, and Role-Based Access Control (RBAC).

## Technologies

- Python 3.9+
- FastAPI
- Uvicorn
- SQLAlchemy
- MySQL
- PyMySQL
- Pydantic
- JWT / python-jose
- Passlib / bcrypt
- python-multipart
- python-dotenv
- Swagger UI

## Project Structure

```text
library_management_fastapi/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   │   ├── category.py
│   │   ├── book.py
│   │   ├── member.py
│   │   ├── borrow.py
│   │   └── users.py
│   ├── schemas/
│   │   ├── category.py
│   │   ├── book.py
│   │   ├── member.py
│   │   ├── borrow.py
│   │   └── users.py
│   ├── routers/
│   │   ├── categories.py
│   │   ├── books.py
│   │   ├── members.py
│   │   ├── borrow.py
│   │   └── auth.py
│   ├── services/
│   │   ├── category_service.py
│   │   ├── book_service.py
│   │   ├── member_service.py
│   │   ├── borrow_service.py
│   │   └── auth_service.py
│   └── auth/
│       ├── jwt.py
│       └── dependencies.py
├── sql/
│   └── schema.sql
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Features

### Authentication
- User registration
- User login
- JWT access-token authentication
- Password hashing
- Active/inactive accounts
- Role-based authorization

### Roles

The application has two roles:

- `Admin`
- `User`

### Admin permissions

Admin can:

- Create, view, update, and delete categories
- Create, view, update, and delete books
- Create, view, update, and delete members
- Create user/member login accounts
- Borrow books
- Return books
- View member borrowing information
- View book borrow history
- View overdue books

### User permissions

A normal User can:

- Login
- View their own profile
- View their own borrowed books

A normal User cannot:

- Manage categories
- Create, update, or delete books
- Manage members
- Borrow books
- Return books
- View book borrow history
- View overdue books
- View another member's borrowing information

## User and Member Relationship

When an Admin creates a Member, the application automatically creates both a User account and a Member record.

```text
User
  |
  | one-to-one
  v
Member
  |
  | one-to-many
  v
BorrowRecord
  |
  | many-to-one
  v
Book
  |
  | many-to-one
  v
Category
```

Passwords are hashed before being stored.

## Database

Database name:

```text
library_db
```

Main tables:

```text
users
categories
members
books
borrow_records
```

Relationships:

```text
users.user_id        -> members.user_id
categories.category_id -> books.category_id
members.member_id    -> borrow_records.member_id
books.book_id        -> borrow_records.book_id
```

The complete SQL schema is available in:

```text
sql/schema.sql
```

## Environment

Create `.env` in the project root:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/library_db
SECRET_KEY=my-library-management-secret-key-2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Replace `YOUR_PASSWORD` with your MySQL password.

Do not commit `.env` to GitHub.

## Installation

```bash
cd library_management_fastapi
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## MySQL Setup

Create the database:

```sql
CREATE DATABASE IF NOT EXISTS library_db;
```

Then execute:

```text
sql/schema.sql
```

The schema creates the tables, relationships, constraints, indexes, and sample categories/books.

## Run the Application

```bash
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

## Authentication APIs

### Register

```text
POST /auth/register
```

Example:

```json
{
  "username": "user1",
  "email": "user1@gmail.com",
  "password": "user123",
  "role": "User",
  "phone": "9876543210",
  "address": "Nellore"
}
```

Registration creates a User and Member automatically.

### Login

```text
POST /auth/login
```

Example:

```json
{
  "username": "user1",
  "password": "user123"
}
```

Response:

```json
{
  "access_token": "JWT_TOKEN",
  "token_type": "bearer"
}
```

### Current User

```text
GET /auth/me
```

## Swagger Authorization

1. Login.
2. Copy `access_token`.
3. Click `Authorize`.
4. Enter:

```text
Bearer YOUR_ACCESS_TOKEN
```

5. Click `Authorize`.

## Category APIs

```text
POST   /categories/
GET    /categories/
GET    /categories/{category_id}
PUT    /categories/{category_id}
DELETE /categories/{category_id}
```

Category creation, update, and deletion are Admin-only.

Example:

```json
{
  "category_name": "Programming",
  "description": "Programming and software development books"
}
```

## Book APIs

### Create

```text
POST /books
```

Admin-only.

Example:

```json
{
  "title": "Python Programming",
  "author": "John Smith",
  "isbn": "9781000000001",
  "category_id": 1,
  "total_copies": 5,
  "available_copies": 5,
  "published_year": 2024
}
```

### View

```text
GET /books
GET /books/{book_id}
```

Filtering and pagination:

```text
GET /books?title=Python
GET /books?author=John
GET /books?category_id=1
GET /books?skip=0&limit=10
```

### Update

```text
PUT /books/{book_id}
```

Admin-only. The update schema supports individual field updates.

Example:

```json
{
  "available_copies": 4
}
```

Another example:

```json
{
  "title": "Advanced Python Programming"
}
```

### Delete

```text
DELETE /books/{book_id}
```

Admin-only. A book cannot be deleted while it has an active `Borrowed` or `Overdue` record.

## Member APIs

All member-management endpoints are Admin-only.

```text
POST   /members/
GET    /members/
GET    /members/{member_id}
PUT    /members/{member_id}
DELETE /members/{member_id}
```

### Create Member and Login Account

Admin uses:

```text
POST /members/
```

Example:

```json
{
  "username": "rahul",
  "email": "rahul@gmail.com",
  "password": "rahul123",
  "name": "Rahul Kumar",
  "phone": "9876543210",
  "address": "Nellore",
  "membership_date": "2026-09-29",
  "is_active": true
}
```

This creates:

```text
users
  username = rahul
  role = User
  password_hash = hashed password

members
  user_id = corresponding users.user_id
  name = Rahul Kumar
```

Rahul can then login with:

```text
Username: rahul
Password: rahul123
```

The password is never returned by the Member API.

## Borrow and Return APIs

### Borrow

```text
POST /borrow/borrow
```

Admin-only.

Example:

```json
{
  "book_id": 1,
  "member_id": 2
}
```

The system checks:

- Member exists
- Member is active
- Book exists
- Copies are available
- Member has fewer than 3 active books
- Member has not already borrowed the same book

Then it creates the borrow record, sets the due date to 14 days after the borrow date, and decreases available copies.

### Return

```text
PUT /borrow/return/{borrow_id}
```

Admin-only.

The system records the return date, changes the status to `Returned`, and increases available copies.

## Member Borrowing Information

```text
GET /borrow/members/{member_id}/books
```

Access:

- Admin: Any member
- User: Own member record only

A User cannot view another user's borrowing information.

## Book Borrow History

```text
GET /borrow/books/{book_id}/borrow-history
```

Access:

- Admin: Yes
- User: No

A normal User receives `403 Forbidden`.

## Overdue Books

```text
GET /borrow/overdue
```

Access:

- Admin: Yes
- User: No

A borrowed record whose due date has passed is changed to `Overdue`.

## Business Rules

### Borrowing

- Inactive members cannot borrow.
- Book and member must exist.
- Available copies must be greater than zero.
- A member can have a maximum of 3 active books.
- A member cannot borrow the same book twice without returning it.
- Available copies decrease when borrowing.
- Due date is 14 days after the borrow date.

### Returning

- A returned book cannot be returned again.
- Return date is recorded.
- Status becomes `Returned`.
- Available copies increase.

### Overdue

A borrowed book becomes overdue when:

```text
due_date < current_date
```

Status becomes:

```text
Overdue
```

### Book Deletion

Books with active `Borrowed` or `Overdue` records cannot be deleted.

## Validation

The API validates:

- Required fields
- Username uniqueness
- User email uniqueness
- Member email uniqueness
- Category name uniqueness
- ISBN uniqueness
- Phone length
- Book title length
- Author length
- ISBN length
- Category ID
- Total copies
- Available copies
- Published year
- User role

Available copies cannot exceed total copies.

## HTTP Status Codes

```text
200 OK
201 Created
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
500 Internal Server Error
```

## Role-Based Access Summary

| Feature | Admin | User |
|---|---|---|
| Register | Yes | Yes |
| Login | Yes | Yes |
| View own profile | Yes | Yes |
| Create category | Yes | No |
| View categories | Yes | According to router access |
| Update category | Yes | No |
| Delete category | Yes | No |
| Create book | Yes | No |
| View books | Yes | According to router access |
| Update book | Yes | No |
| Delete book | Yes | No |
| Create member | Yes | No |
| View members | Yes | No |
| Update member | Yes | No |
| Delete member | Yes | No |
| Borrow book | Yes | No |
| Return book | Yes | No |
| View own borrowed books | Yes | Yes |
| View another member's borrowed books | Yes | No |
| View book borrow history | Yes | No |
| View overdue books | Yes | No |

## Recommended Swagger Testing Order

1. Register Admin.
2. Login Admin.
3. Authorize Swagger with Admin token.
4. Check `/auth/me`.
5. Create categories.
6. View categories.
7. Create books.
8. View books.
9. Update a book.
10. Create a member.
11. Login as the created User/Member.
12. Authorize with the User token.
13. Test the User's own borrowed-book endpoint.
14. Verify User cannot borrow.
15. Verify User cannot return.
16. Verify User cannot view borrow history.
17. Verify User cannot view overdue books.
18. Authorize again with Admin token.
19. Borrow a book.
20. View member borrowing information.
21. View book borrow history.
22. View overdue books.
23. Return the book.
24. Verify available copies increased.

## Example Test Data

### Admin Login

```json
{
  "username": "admin",
  "password": "admin123"
}
```

### Admin Creates Member

```json
{
  "username": "rahul",
  "email": "rahul@gmail.com",
  "password": "rahul123",
  "name": "Rahul Kumar",
  "phone": "9876543210",
  "address": "Nellore",
  "membership_date": "2026-09-29",
  "is_active": true
}
```

### Member Login

```json
{
  "username": "rahul",
  "password": "rahul123"
}
```

### Admin Borrows a Book for Rahul

```json
{
  "book_id": 1,
  "member_id": 2
}
```

### Rahul Views His Borrowing Information

```text
GET /borrow/members/2/books
```

### Rahul Attempts to Borrow

```text
POST /borrow/borrow
```

Expected:

```text
403 Forbidden
```

### Rahul Attempts to Return

```text
PUT /borrow/return/1
```

Expected:

```text
403 Forbidden
```

### Rahul Attempts to View Borrow History

```text
GET /borrow/books/1/borrow-history
```

Expected:

```text
403 Forbidden
```

### Rahul Attempts to View Overdue Books

```text
GET /borrow/overdue
```

Expected:

```text
403 Forbidden
```

## Security

- Passwords are hashed before database storage.
- JWT tokens are used for authentication.
- Protected endpoints require authentication.
- Admin-only operations use role-based authorization.
- Users cannot access another member's private borrowing information.
- `.env` contains sensitive configuration and must not be committed to GitHub.

## Recommended .gitignore

```text
__pycache__/
*.py[cod]

venv/
.venv/

.env
.env.*
!.env.example

.vscode/
.idea/

*.log

.pytest_cache/
.coverage
htmlcov/

*.egg-info/
dist/
build/

.DS_Store
Thumbs.db
```

## .env.example

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/library_db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Do not put the actual MySQL password or production secret key in `.env.example`.

## Assumptions

- MySQL is installed and running locally.
- The database is named `library_db`.
- SQLAlchemy is used for database operations.
- JWT is used for authentication.
- Passwords are stored using hashing.
- Admin creates Members with login credentials.
- A Member created by Admin automatically receives a User account with role `User`.
- A User and Member have a one-to-one relationship.
- A Member can have multiple borrow records.
- A Book can have multiple borrow records over time.
- A Member can have a maximum of three active borrowed books.
- The borrowing period is 14 days.
- Admin is responsible for borrowing and returning books.
- Normal Users can view their own borrowing information but cannot borrow or return books.
- Book borrow history and overdue-book information are Admin-only.

## Project Objective

The objective is to develop a secure Library Management backend providing:

- User authentication
- JWT authorization
- Role-based access control
- Category management
- Book management
- Member management
- Borrow and return functionality
- Borrow history
- Overdue tracking
- Database persistence
- Input validation
- Business-rule enforcement
- Interactive Swagger documentation

## Run

```bash
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

# End of README
