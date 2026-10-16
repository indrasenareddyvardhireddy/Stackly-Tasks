# Real-Time Support Ticket System (FastAPI)

A backend where customers raise support tickets, tickets are **automatically assigned** to support agents, and customers and agents **chat live** on each ticket.

**Features:** JWT authentication · role-based access control (Admin / Agent / Customer) · async MySQL access · WebSocket chat · live notifications · SLA tracking with automatic escalation · Alembic migrations · admin reports · optional email notifications.

**Stack:** Python 3.9+ (3.11 or 3.12 recommended) · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · MySQL via `aiomysql` · Alembic · JWT (python-jose) · Passlib/bcrypt · WebSockets · APScheduler · Uvicorn.

---

## Table of contents
1. [Project structure](#1-project-structure)
2. [Setup](#2-setup)
3. [Alembic commands](#3-alembic-commands)
4. [Test credentials](#4-test-credentials)
5. [Logging in with Swagger](#5-logging-in-with-swagger)
6. [Roles and permissions](#6-roles-and-permissions)
7. [API reference](#7-api-reference)
8. [How the main features work](#8-how-the-main-features-work)
9. [WebSocket testing](#9-websocket-testing)
10. [API testing walkthrough per role](#10-api-testing-walkthrough-per-role)
11. [Sample chat: billing query](#11-sample-chat-billing-query)
12. [Email notifications (bonus)](#12-email-notifications-bonus)
13. [Assumptions and design decisions](#13-assumptions-and-design-decisions)
14. [Troubleshooting](#14-troubleshooting)
15. [Bonus status](#15-bonus-status)
16. [Submission checklist](#16-submission-checklist)

---

## 1. Project structure
```
support-ticket-system/
├── app/
│   ├── main.py            FastAPI app, routers, scheduler lifespan, /chat-test page
│   ├── config.py          settings read from .env (pydantic-settings)
│   ├── database.py        async engine + AsyncSession dependency
│   ├── seed.py            sample categories + one test user per role
│   ├── utils.py           utcnow() helper (all timestamps are naive UTC)
│   ├── models/            SQLAlchemy models + enums
│   ├── schemas/           Pydantic request/response models
│   ├── routers/           REST endpoints (auth, agents, categories, sla, tickets,
│   │                      messages, feedback, notifications, reports)
│   ├── services/          business logic (tickets, assignment, SLA, chat,
│   │                      notifications, email, history)
│   ├── auth/              password hashing, JWT, role-check dependencies
│   ├── websockets/        chat + notification sockets, connection managers
│   └── jobs/              APScheduler jobs (SLA check, escalation, auto-close)
├── alembic/               migrations (tables are created ONLY by Alembic)
├── static/chat_test.html  browser chat tester, served at GET /chat-test
├── docs/                  put your screenshots here
├── alembic.ini
├── requirements.txt
├── .env.example           copy to .env (never commit .env)
├── .gitignore
└── README.md
```

**Data model (all tables have `created_at` and `updated_at`):**

| Table | Purpose |
|---|---|
| `users` | All accounts (role: Admin / Agent / Customer, `is_active`) |
| `agent_profiles` | Agent availability (Online/Offline) and `max_open_tickets` (default 10) |
| `agent_categories` | Which categories each agent can handle (many-to-many) |
| `categories` | Ticket categories (unique name, `is_active`) |
| `sla_policies` | First-response and resolution minutes per priority |
| `tickets` | Tickets, SLA due times, breach/escalation flags |
| `messages` | Chat messages and internal notes |
| `ticket_status_history` | Every status change, assignment, priority change and escalation |
| `feedback` | One rating (1 to 5) per ticket |
| `notifications` | Saved notifications (so missed ones can be read later) |

Relationships: Category → many Tickets · Customer → many Tickets · Agent → many assigned Tickets · Ticket → many Messages · Ticket → many History records · Ticket → one Feedback.

---

## 2. Setup

### Prerequisites
- Python 3.9 or newer (3.11/3.12 recommended; very new versions such as 3.14 may have package-compatibility issues)
- MySQL 8 running locally

### Steps
**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
py -3.12 -m venv .venv          # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Use a **fresh virtual environment for this project**. If your prompt shows a venv from a different project, packages will be missing (see [Troubleshooting](#14-troubleshooting)).

Then, on any OS:
```bash
# 1. Create the database (once). The name must match DATABASE_URL.
mysql -u root -p -e "CREATE DATABASE support_tickets CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Create your .env file
cp .env.example .env          # Windows: copy .env.example .env
#    then edit DATABASE_URL (user, password, database name) and JWT_SECRET_KEY

# 3. Create all tables + default SLA policies
alembic upgrade head

# 4. Insert sample categories and one test user per role
python -m app.seed

# 5. Run the API
uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- Chat test page: http://localhost:8000/chat-test

### Environment variables (`.env`)
| Variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | `mysql+aiomysql://USER:PASSWORD@HOST:3306/DBNAME?charset=utf8mb4` | required |
| `JWT_SECRET_KEY` | Long random string used to sign tokens | required |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `30` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Optional email settings (leave `SMTP_HOST` empty to disable email) | empty |

In `DATABASE_URL` the database name is the part after the port: `.../3306/support_tickets?...` means the database is `support_tickets`.

### Why run `python -m app.seed`?
`alembic upgrade head` creates empty tables. The API cannot bootstrap itself from empty: public registration only creates Customers, and only an Admin can create Agents and categories. The seed script creates the first Admin, four categories (Billing, Technical, Account, Delivery), two Agents and one Customer so you can start testing immediately. It is safe to run repeatedly (existing records are skipped). Skip it or change the passwords in a real deployment.

---

## 3. Alembic commands
```bash
alembic upgrade head                                    # apply all migrations
alembic downgrade -1                                    # roll back one revision
alembic downgrade base                                  # roll back everything
alembic current                                         # show the current revision
alembic history                                         # list all revisions
alembic revision --autogenerate -m "describe change"    # new migration after editing models
```
Tables are never created with `create_all`. The initial migration is `alembic/versions/0001_initial_schema.py`; it also inserts the default SLA policies.

---

## 4. Test credentials
Created by `python -m app.seed`:

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@example.com` | `Admin@123` | Full access |
| Agent | `agent1@example.com` | `Agent@123` | Handles **Billing, Account**; starts **Offline** |
| Agent | `agent2@example.com` | `Agent@123` | Handles **Technical, Delivery**; starts **Offline** |
| Customer | `customer@example.com` | `Customer@123` | Can create tickets |

Agents start Offline. Call `PUT /agents/me/availability` with `{"availability": "Online"}` as the agent so auto-assignment works.

Category ids after seeding: 1 = Billing, 2 = Technical, 3 = Account, 4 = Delivery.

---

## 5. Logging in with Swagger
`POST /auth/login` uses the standard OAuth2 password form, so the **Authorize** button in Swagger works.

- **username** → the account **email** (e.g. `admin@example.com`)
- **password** → the password
- Leave `grant_type` empty (or `password`). Clear the placeholder `string` values in `client_id`, `client_secret` and `scope`, and leave them empty.

**Easiest:** click **Authorize** (top right), enter email and password, leave client fields empty, click **Authorize**. Swagger then sends the token with every request. To switch users, click **Authorize → Logout** and log in as someone else.

For WebSocket tests you need the raw `access_token` from the `/auth/login` response. Tokens expire after **30 minutes**; log in again if you get `401` or a `4401` WebSocket close.

---

## 6. Roles and permissions

| Action | Admin | Agent | Customer |
|---|:---:|:---:|:---:|
| Register publicly (always creates a Customer) | ✔ | ✔ | ✔ |
| Create Admin / Agent accounts | ✔ | ✘ | ✘ |
| Manage categories and SLA policies | ✔ | ✘ | ✘ |
| View categories and SLA policies | ✔ | ✔ | ✔ (active categories only) |
| Create tickets | ✘ | ✘ | ✔ |
| View tickets | all | only tickets assigned to them | only their own |
| Change ticket status / priority | ✔ | only on their assigned tickets | ✘ |
| Assign / reassign tickets | ✔ | ✘ | ✘ |
| Reopen a Resolved ticket | ✘ | ✘ | ✔ (own, within 7 days, max 2 times) |
| Chat on a ticket | ✔ | assigned tickets | own tickets |
| Send internal notes | ✔ | ✔ | ✘ (never sees them) |
| Give feedback | ✘ | ✘ | ✔ (own Resolved/Closed ticket, once) |
| Reports and dashboard | ✔ | ✘ | ✘ |
| Own notifications | ✔ | ✔ | ✔ |

Status codes: `401` invalid/expired/missing token · `403` wrong role or not your ticket · `404` not found · `409` duplicate · `400` business-rule violation · `422` validation error.

---

## 7. API reference

### Auth
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/auth/register` | Public | Register a Customer |
| POST | `/auth/login` | Public | Login (form: `username` = email, `password`) → token |
| GET | `/auth/me` | Any user | Current user |
| POST | `/auth/admins` | Admin | Create an Admin account (extra endpoint) |

### Agents
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/agents` | Admin | Create an agent (categories, availability, `max_open_tickets`) |
| GET | `/agents` | Admin | List agents (`availability`, `is_active`, `skip`, `limit`) |
| PUT | `/agents/{agent_id}` | Admin | Update agent (name, email, categories, availability, capacity, `is_active`) |
| PUT | `/agents/me/availability` | Agent | Set Online/Offline |
| GET | `/agents/me/tickets` | Agent | My assigned tickets (`status`, `skip`, `limit`) |

### Categories and SLA policies
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/categories` | Admin | Create category |
| GET | `/categories` | Any user | List (non-admins see only active) |
| PUT | `/categories/{category_id}` | Admin | Update |
| DELETE | `/categories/{category_id}` | Admin | Delete (blocked if open tickets exist) |
| GET | `/sla-policies` | Any user | List the four policies |
| PUT | `/sla-policies/{priority}` | Admin | Update minutes for `Low`, `Medium`, `High` or `Urgent` |

Default SLA: Low 24 h / 72 h · Medium 8 h / 48 h · High 2 h / 24 h · Urgent 30 min / 8 h (first response / resolution).

### Tickets
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/tickets` | Customer | Create (auto-assigned if possible) |
| GET | `/tickets` | Any user (role-scoped) | List with filters, sorting, pagination |
| GET | `/tickets/{ticket_id}` | Owner / assigned agent / Admin | Details |
| PUT | `/tickets/{ticket_id}/status` | Assigned agent / Admin | Change status |
| PUT | `/tickets/{ticket_id}/priority` | Assigned agent / Admin | Change priority (recalculates SLA due times) |
| PUT | `/tickets/{ticket_id}/reopen` | Customer | Reopen a Resolved ticket |
| PUT | `/tickets/{ticket_id}/assign` | Admin | Assign / reassign |
| GET | `/tickets/{ticket_id}/history` | Owner / assigned agent / Admin | Status and assignment history |

**`GET /tickets` filters:** `ticket_number`, `subject` (partial match), `status`, `priority`, `category_id`, `assigned_agent_id`, `sla_breached`, `from_date`, `to_date`.
**Sorting:** `sort_by` (`created_at`, `updated_at`, `priority`, `status`, `resolution_due`, `first_response_due`) and `order` (`asc` / `desc`).
**Pagination:** `skip` (default 0), `limit` (default 10, max 100).
Example: `GET /tickets?status=Open&priority=High&sort_by=created_at&order=desc&skip=0&limit=10`

### Messages (chat over REST)
| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/tickets/{ticket_id}/messages` | Owner / assigned agent / Admin | Messages, oldest first (`skip`, `limit`). Customers never get internal notes. Marks the other side's messages read |
| POST | `/tickets/{ticket_id}/messages` | Owner / assigned agent / Admin | Send a message; body `{"message": "...", "is_internal_note": false}` |

### Feedback
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/tickets/{ticket_id}/feedback` | Ticket's customer | `{"rating": 1-5, "comment": "..."}`. Only for Resolved/Closed tickets; one per ticket |
| GET | `/tickets/{ticket_id}/feedback` | Owner / assigned agent / Admin | View feedback |

### Notifications
| Method | Path | Description |
|---|---|---|
| GET | `/notifications` | My notifications (`unread_only`, `skip`, `limit`) |
| PUT | `/notifications/{notification_id}/read` | Mark one as read |
| PUT | `/notifications/read-all` | Mark all as read |

### Reports (Admin only; optional `from_date` / `to_date`)
| Path | Returns |
|---|---|
| `GET /reports/dashboard` | Total tickets, tickets by status, unassigned tickets, SLA-breached tickets, agents online |
| `GET /reports/agent-performance` | Per agent: tickets resolved, avg first response and resolution time, SLA breach %, avg rating |
| `GET /reports/category-summary` | Per category: ticket count, avg resolution time |
| `GET /reports/sla-summary` | Per priority: SLA met / breached |
| `GET /reports/customer-satisfaction` | Average rating and 1–5 star distribution |

### WebSockets
| Path | Description |
|---|---|
| `WS /ws/tickets/{ticket_id}?token=...` | Live ticket chat |
| `WS /ws/notifications?token=...` | Live notifications and open-ticket counters |

---

## 8. How the main features work

### Ticket status flow
```
Open → Assigned → In Progress → Waiting on Customer ⇄ In Progress
                       └──────→ Resolved → Closed
```
- Only the assigned agent or an Admin changes status/priority. Invalid jumps return `400`.
- **Closed** tickets cannot be updated or reopened.
- Every status change is stored in `ticket_status_history` (old status, new status, who, when).
- The system moves *Assigned → In Progress* on the agent's first public reply, and *Waiting on Customer → In Progress* when the customer replies.

### Automatic assignment
- A new ticket goes to an agent who is **Online**, **active**, handles the ticket's **category**, and is under `max_open_tickets`.
- If several match, the agent with the **fewest open tickets** wins.
- No agent available → the ticket stays `Open` and unassigned, and is assigned automatically when a matching agent goes Online (or frees capacity by resolving a ticket).
- Going Offline does **not** move tickets; only an Admin can reassign (`PUT /tickets/{id}/assign`). Reassignment is saved to history and notifies the old and new agent.

### Reopening
A customer can reopen a **Resolved** ticket within **7 days** of resolution, at most **2 times**. It goes back to *In Progress*. Closed tickets cannot be reopened.

### Chat rules
- WebSocket auth uses the `token` query parameter; an invalid token closes the connection (code `4401`).
- Only the ticket's customer, the assigned agent and Admin may join (`4403` otherwise; `4404` if the ticket does not exist).
- Every message is saved, then pushed to everyone connected to that ticket.
- On connect, the last **50 messages** are sent first (`history` event).
- **Internal notes** (`is_internal_note: true`) reach only Agents and Admin, via REST, WebSocket history and live broadcast.
- The agent's first public reply records `first_response_at`.
- Messages are marked read when the *other side* opens the chat.
- The **typing indicator** (`{"type":"typing"}`) is broadcast but never saved.
- Customers cannot send messages on **Closed** tickets.
- Disconnects are cleaned up without errors, including dead connections found while broadcasting.

### Live notifications
| Recipient | Event |
|---|---|
| Agent | A ticket is assigned or reassigned to them; the customer replies or reopens while they are away |
| Customer | Their ticket's status changes; an agent/admin replies while they are not in the chat |
| Admin | A ticket breaches its SLA or is escalated |
| Agent and Admin | Live open-ticket counter (`open_tickets_count`) |

Every notification is also saved in the `notifications` table, so missed ones appear in `GET /notifications`.

### SLA tracking and escalation (APScheduler)
| Job | Schedule | What it does |
|---|---|---|
| SLA check | every 5 minutes | Marks `sla_breached` when the first-response or resolution due time passes; notifies admins |
| Escalation | every 5 minutes (30 s after the check) | Raises priority by one level for each breach, notifies admins, writes history. Each breach escalates **once**. Urgent tickets can't go higher but admins are still notified |
| Auto-close | daily at 02:00 UTC | Closes Resolved tickets not reopened within 7 days |

Jobs start automatically with the app. Time spent in **Waiting on Customer** (and in Resolved before a reopen) does not count toward the resolution SLA; the due time is pushed back by that amount.

### Validation
Unique email, ticket number and category name · subject 5–150 characters · description at least 10 characters · messages 1–2000 characters · rating 1–5 · inactive categories can't be used for new tickets · inactive users can't log in.

---

## 9. WebSocket testing
WebSocket endpoints do not appear in Swagger. First prepare a ticket and tokens.

### Preparation
1. Start the server: `uvicorn app.main:app --reload`.
2. In Swagger, log in as `customer@example.com` and `agent1@example.com` and copy each `access_token`.
3. As the agent: `PUT /agents/me/availability` → `{"availability": "Online"}`.
4. As the customer: `POST /tickets` with `{"category_id": 1, "subject": "Charged twice for October invoice", "description": "I was charged twice for invoice INV-2026-1042.", "priority": "High"}`. Note the ticket `id` (e.g. `1`). The status should be `Assigned`.

### Option A: HTML test page (easiest)
1. Open http://localhost:8000/chat-test in two windows (normal + incognito).
2. Window A: paste the **customer** token, enter the ticket id, click **Connect**.
3. Window B: paste the **agent** token, same ticket id, **Connect**.
4. Send messages from either window; both update instantly. Typing in one window shows "Customer is typing..." / "Agent is typing..." in the other. Tick **Internal note** in the agent window to send a note the customer never sees.

### Option B: Postman
1. New → **WebSocket** → URL `ws://localhost:8000/ws/tickets/1?token=<access_token>` → **Connect**.
2. Open a second tab with the other user's token.
3. Send (JSON): `{"message": "Hello"}`.
4. Typing indicator: `{"type": "typing"}`. Internal note (agent): `{"message": "private", "is_internal_note": true}`.

### Option C: Browser console
Open http://localhost:8000/docs, press F12 → Console, then:
```js
const ws = new WebSocket("ws://localhost:8000/ws/tickets/1?token=<access_token>");
ws.onmessage = (e) => console.log("Message:", e.data);
ws.send(JSON.stringify({ "message": "Hello" }));   // run after it connects
```

### Messages you send
```json
{"message": "Hello"}
{"message": "Check the logs", "is_internal_note": true}
{"type": "typing", "is_typing": true}
```

### Events you receive
| `type` | Meaning |
|---|---|
| `history` | Last 50 messages (sent right after connecting) |
| `message` | A new message: `{"type":"message","data":{...}}` |
| `typing` | `{"type":"typing","role":"Agent","text":"Agent is typing...", ...}` |
| `read` | The other side opened the chat |
| `error` | Rejected action, e.g. empty message or closed ticket |

### Close codes
| Code | Reason |
|---|---|
| `4401` | Invalid or expired token |
| `4403` | Not allowed on this ticket (or access revoked) |
| `4404` | Ticket not found |

### Checklist of rules to verify
| Rule | How to test | Expected |
|---|---|---|
| Invalid token closes connection | Connect with a garbage token | Closed with `4401` |
| Only customer / assigned agent / admin join | Connect with `agent2` or another customer | Closed with `4403` |
| Saved and delivered instantly | Send from one window | Appears in both; also in `GET /tickets/{id}/messages` |
| Last 50 messages on connect | Disconnect and reconnect | `history` arrives first |
| Internal notes hidden | Agent sends a note | Customer window and customer's `GET messages` don't contain it |
| First reply sets `first_response_at` | Agent's first normal reply, then `GET /tickets/{id}` | Field filled in; status `In Progress` |
| Read receipts | Connect the other side | `read` event; `is_read: true` in REST |
| Typing indicator not saved | Type without sending | Shown live; absent from `GET messages` |
| No messages on Closed tickets | Resolve → Close, then customer sends | `error` event |
| Clean disconnect | Close a window | No errors in the server log |

### Notifications socket
Connect to `ws://localhost:8000/ws/notifications?token=<access_token>`. You receive `{"type":"connected","unread_count":N}`, `{"type":"open_tickets_count","count":N}` (agents and admins) and `{"type":"notification","data":{...}}` live. Send the text `ping` to get `{"type":"pong"}`.

---

## 10. API testing walkthrough per role
Use **Authorize** in Swagger and switch users with **Logout**. Use the ids from your own responses.

### Public (no token)
| Endpoint | Input | Expected |
|---|---|---|
| `POST /auth/register` | `{"name":"New User","email":"new@example.com","password":"Test@1234"}` | 201, role Customer |
| `POST /auth/register` | same email again | 409 |
| `POST /auth/register` | password `abc` | 422 |
| `POST /auth/login` | wrong password | 401 |
| `GET /auth/me` or `GET /tickets` | no token | 401 |

### Admin (`admin@example.com`)
| Endpoint | Input | Expected |
|---|---|---|
| `GET /auth/me` | | 200, role Admin |
| `POST /categories` | `{"category_name":"Sales","description":"Sales questions"}` | 201 |
| `POST /categories` | same name | 409 |
| `PUT /categories/{id}` | `{"is_active":false}` | 200 |
| `DELETE /categories/{id}` | unused / with open tickets | 200 / 400 |
| `GET /sla-policies` | | 200, four policies |
| `PUT /sla-policies/High` | `{"first_response_minutes":120,"resolution_minutes":1440}` | 200 |
| `PUT /sla-policies/High` | resolution < first response | 422 |
| `POST /agents` | `{"name":"Dan Agent","email":"agent3@example.com","password":"Agent@123","category_ids":[1,2],"max_open_tickets":5}` | 201 |
| `POST /agents` | unknown category id | 404 |
| `GET /agents` | `?availability=Online&skip=0&limit=10` | 200 |
| `PUT /agents/{id}` | `{"is_active":false}`, then that agent logs in | login returns 403 |
| `POST /auth/admins` | name, email, password | 201 |
| `GET /tickets` | `?status=Open&priority=High&sort_by=priority&order=desc` | 200, all tickets |
| `PUT /tickets/{id}/assign` | `{"agent_id": <id>}` | 200; same agent again → 400 |
| `PUT /tickets/{id}/priority` | `{"priority":"Urgent"}` | 200, due times recalculated |
| `GET /tickets/{id}/history` | | 200, assignment and status entries |
| `GET /reports/dashboard`, `/agent-performance`, `/category-summary`, `/sla-summary`, `/customer-satisfaction` | optional dates | 200 |
| `POST /tickets` | valid body | 403 (customers only) |

### Agent (`agent1@example.com`)
| Endpoint | Input | Expected |
|---|---|---|
| `PUT /agents/me/availability` | `{"availability":"Online"}` | 200 |
| `GET /agents/me/tickets` | `?status=Assigned` | 200, only own tickets |
| `GET /tickets` | | 200, only assigned tickets |
| `GET /tickets/{someone else's}` | | 403 |
| `PUT /tickets/{id}/status` | `In Progress` | 200 |
| `PUT /tickets/{id}/status` | jump straight to `Closed` | 400 |
| `PUT /tickets/{id}/status` | `Waiting on Customer`, then `Resolved` | 200 each |
| `PUT /tickets/{id}/priority` | `{"priority":"High"}` | 200 |
| `POST /tickets/{id}/messages` | `{"message":"Looking into it"}` | 201; `first_response_at` is set |
| `POST /tickets/{id}/messages` | `{"message":"Check logs","is_internal_note":true}` | 201 |
| `GET /notifications` | | 200, contains `ticket_assigned` |
| `PUT /notifications/read-all` | | 200 |
| `POST /agents`, `POST /categories`, `GET /agents`, `PUT /tickets/{id}/assign`, `GET /reports/dashboard`, `POST /tickets/{id}/feedback` | | 403 |

### Customer (`customer@example.com`)
| Endpoint | Input | Expected |
|---|---|---|
| `GET /categories` | | 200, active only |
| `POST /tickets` | `{"category_id":1,"subject":"Cannot pay invoice","description":"Card is declined at checkout","priority":"High"}` | 201, e.g. `TKT-20261016-0001`, auto-assigned if an agent is Online |
| `POST /tickets` | subject `"Hi"` / description under 10 chars | 422 |
| `POST /tickets` | inactive / unknown category | 400 / 404 |
| `GET /tickets` | | 200, only own tickets |
| `GET /tickets/{someone else's}` | | 403 |
| `POST /tickets/{id}/messages` | `{"message":"Any update?"}` | 201 |
| `POST /tickets/{id}/messages` | `"is_internal_note":true` | 403 |
| `POST /tickets/{id}/messages` | empty message | 422 |
| `GET /tickets/{id}/messages` | | 200, no internal notes |
| `PUT /tickets/{id}/status` or `/priority` | | 403 |
| `PUT /tickets/{id}/reopen` | Resolved ticket | 200, In Progress, `reopen_count` 1 |
| `PUT /tickets/{id}/reopen` | not Resolved / third time / Closed | 400 |
| `POST /tickets/{id}/feedback` | `{"rating":5,"comment":"Great help"}` on Resolved | 201 |
| `POST /tickets/{id}/feedback` | ticket still open / second time / rating 6 | 400 / 409 / 422 |
| `POST /tickets/{id}/messages` | ticket Closed | 400 |
| `GET /agents`, `GET /reports/dashboard`, `POST /categories`, `PUT /tickets/{id}/assign` | | 403 |

### Cross-role scenarios
- **Full flow:** agent Online → customer creates ticket → status `Assigned` → they chat in `/chat-test` → agent sets In Progress then Resolved → customer leaves feedback → admin checks `/reports/*`.
- **No agent available:** set all agents Offline, create a ticket (stays `Open`, `assigned_agent_id: null`), then set an agent Online → it becomes `Assigned` automatically.
- **Reassignment:** admin calls `PUT /tickets/{id}/assign` → both agents get a notification and the history shows it.
- **SLA breach and escalation:** admin sets `PUT /sla-policies/Low` to `{"first_response_minutes":1,"resolution_minutes":2}`; customer creates a `Low` ticket; wait about 6 minutes without replying → `sla_breached: true`, priority raised to `Medium`, an `escalation` history entry, admin notifications. Restore the policy afterwards (1440 and 4320 minutes).
- **Capacity limit:** set an agent's `max_open_tickets` to 1 and create two tickets in their category; the second does not go to that agent.

---

## 11. Sample chat: billing query
**Ticket** (customer, `POST /tickets`):
```json
{
  "category_id": 1,
  "subject": "Charged twice for October invoice",
  "description": "I was charged twice for invoice INV-2026-1042 on 12 October. Please refund the duplicate payment.",
  "priority": "High"
}
```
Make sure `agent1` (Billing) is Online first. Open `/chat-test` in two windows (customer and agent) on the ticket id.

| # | Who | Message |
|---|---|---|
| 1 | Customer | Hi, I was charged twice for my October invoice INV-2026-1042. Can you help? |
| 2 | Agent | Hello Carol, sorry about that! I'm looking into your account now. |
| 3 | Agent *(internal note)* | Checked the payment gateway: two successful charges of ₹4,999 within 2 minutes. Duplicate confirmed. Needs refund approval. |
| 4 | Agent | I can see two charges of ₹4,999 on 12 October. You're right, one of them is a duplicate. |
| 5 | Customer | Yes, that's it. How long will the refund take? |
| 6 | Agent | I've started the refund for the duplicate charge. It usually takes 5 to 7 business days to reach your card. |
| 7 | Customer | Great. Will I get a confirmation? |
| 8 | Agent | Yes, you'll get an email with a refund reference number within 24 hours. Is there anything else I can help with? |
| 9 | Customer | No, that's all. Thank you so much! |
| 10 | Agent | You're welcome! I'll mark this as resolved. Have a great day! |

**Screenshot tips**
- After messages 1–2, `GET /tickets/{id}` shows `first_response_at` filled in and status `In Progress`.
- Message 3 appears only in the agent window (yellow).
- Type message 5 in the customer window without sending to capture "Customer is typing..." in the agent window.
- After message 10: agent `PUT /tickets/{id}/status` → `Resolved`; customer `POST /tickets/{id}/feedback` → `{"rating":5,"comment":"Quick refund, very helpful"}`.

---

## 12. Email notifications (bonus)
Emails are sent in the background (FastAPI `BackgroundTasks` + SMTP) for:

| Event | Recipient |
|---|---|
| Ticket created | The customer |
| Ticket resolved | The customer |
| SLA breached | All active admins |

If `SMTP_HOST` is empty, emails are skipped and a log line `SMTP not configured; skipping email ...` is written. Nothing else is affected, and a failed send never breaks a request.

**Gmail example (`.env`):**
```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youraddress@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=youraddress@gmail.com
SMTP_USE_TLS=true
```
`SMTP_PASSWORD` must be a Google **App Password** (Google Account → Security → 2-Step Verification → App passwords), not your normal password. Restart uvicorn after editing `.env`. The seeded `@example.com` addresses are not real inboxes, so register a customer with your own email to receive messages.

**Test without a mail server:**
```bash
pip install aiosmtpd
python -m aiosmtpd -n -l localhost:1025
```
Then set `SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_USE_TLS=false` and leave `SMTP_USER` empty. Sent emails print in that terminal.

---

## 13. Assumptions and design decisions
- **IDs:** `agent_id` always equals the agent's `user_id`; `assigned_agent_id` references `users.id`.
- **Login** uses the OAuth2 password form (`username` holds the email) so Swagger's Authorize button works.
- **Admin accounts** are created by an Admin via `POST /auth/admins` (extra endpoint); the first Admin comes from the seed script. `POST /agents` creates Agents.
- Agent `name`, `email` and `is_active` live on the user record; the agent profile holds availability, capacity and categories.
- **"Open tickets"** for an agent = assigned tickets in Assigned / In Progress / Waiting on Customer. Resolved and Closed tickets don't count toward `max_open_tickets`.
- **Status flow:** Open → Assigned → In Progress → (Waiting on Customer | Resolved) → Closed. *Waiting on Customer → In Progress* is also allowed. The system performs *Assigned → In Progress* on the agent's first public reply and *Waiting → In Progress* when the customer replies.
- **Reopen:** customer only, Resolved tickets only, within 7 days, max 2 times. Time spent Resolved doesn't count toward the SLA.
- **Priority change** recalculates due times from `created_at` using the new policy (plus paused time). **Escalation** raises priority but does not recalculate due times.
- Each breach (first response, resolution) is escalated once. A ticket answered or resolved late before the job ran is marked breached but not escalated.
- **Category delete:** blocked while open tickets exist. Categories that only have finished tickets are deactivated (to keep history); unused ones are hard-deleted.
- `GET /categories` and `GET /sla-policies` are readable by any logged-in user (customers need categories to create tickets); only Admin can modify. Non-admins see only active categories.
- Customers can't message on Closed tickets; agents and Admin may still add notes there.
- Message length is 1–2000 characters (2000 allowed).
- Messages are marked read when the *other side* opens the chat (WebSocket connect or `GET /tickets/{id}/messages`).
- **Reports** filter tickets by `created_at` in the date range (feedback by its own `created_at`). SLA "met" counts Resolved/Closed tickets that never breached.
- All timestamps are stored as naive **UTC**.
- List endpoints return plain arrays with `skip` / `limit` (default limit 10, max 100).
- Live notifications are sent before the surrounding transaction commits; they are saved in the same transaction.

---

## 14. Troubleshooting
| Problem | Cause and fix |
|---|---|
| `ImportError: ... requires ... 'greenlet'` / `ModuleNotFoundError` | Dependencies are missing, often because the **wrong virtual environment** is active (check the path in the traceback). Create a fresh venv in this folder and run `pip install -r requirements.txt` |
| `ValidationError` for `DATABASE_URL` / `JWT_SECRET_KEY` | `.env` is missing. Run `copy .env.example .env` (Windows) or `cp .env.example .env` and fill it in |
| `Unknown database 'support_tickets'` | Create the database first (see [Setup](#2-setup)); the name must match `DATABASE_URL` |
| `Access denied for user` / can't connect to MySQL | Wrong user or password in `DATABASE_URL`, or MySQL isn't running |
| `cryptography` error for MySQL 8 login | Make sure `pip install -r requirements.txt` finished (it installs `cryptography`) |
| bcrypt / passlib error such as `module 'bcrypt' has no attribute '__about__'` | Keep `bcrypt==4.0.1` as pinned in `requirements.txt`; prefer Python 3.11/3.12 |
| `401 Unauthorized` after a while | The token expired (30 min). Log in again |
| Login fails in Swagger | Enter the email in `username`, clear the placeholder `string` values in `client_id` / `client_secret` / `scope` |
| Ticket stays `Open` and unassigned | No agent is Online, active, handling that category and under capacity. Set the agent Online via `PUT /agents/me/availability` |
| WebSocket closes with `4401` / `4403` / `4404` | Expired token / not your ticket / ticket doesn't exist |
| `/chat-test` can't connect | Use the same host as the server and a valid token; the page builds `ws://` / `wss://` from the page URL |
| No emails received | SMTP isn't configured, or you used a seeded `@example.com` address. See [Email notifications](#12-email-notifications-bonus) |

---

## 15. Bonus status
- **Email notifications** (ticket created, resolved, SLA breached) via `BackgroundTasks` + SMTP: **implemented**.
- **File attachments in chat** (images and PDFs up to 5 MB): **not implemented**.

---

## 16. Submission checklist
- [ ] Push to GitHub (only `.env.example`; `.env` is git-ignored)
- [ ] Alembic migration files are in `alembic/versions/`
- [ ] Swagger screenshots of tested APIs saved in `docs/`
- [ ] Screenshots of the customer ↔ agent chat saved in `docs/`
- [ ] README is up to date with setup steps, Alembic commands, credentials, WebSocket testing and assumptions
