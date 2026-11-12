# Taskboard: Django REST + React Task Manager

A Todoist-style task manager. Django REST Framework + Simple JWT + MySQL on the backend, React (Vite) on the frontend.
Includes all 11 levels **and every bonus feature**: subtasks, Kanban board with drag and drop, dark mode,
recurring tasks, refresh-token blacklisting on logout, email reminders, backend tests, and Docker Compose.

```
task-manager/
├── backend/    Django project (config, accounts, tasks)
├── frontend/   React app (Vite)
├── docs/       Postman collection + screenshots
└── docker-compose.yml
```

## Run the backend

Requirements: Python 3.10+, MySQL 8 running locally. (On Windows `mysqlclient` needs a wheel; `pip install mysqlclient` usually works on recent Python versions.)

```bash
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                # then edit SECRET_KEY and DB_* values
# create the database once:
#   mysql -u root -p -e "CREATE DATABASE task_manager CHARACTER SET utf8mb4;"

python manage.py makemigrations accounts tasks
python manage.py migrate
python manage.py createsuperuser    # email + names + password
python manage.py seed_demo          # optional: demo user with sample data
python manage.py runserver          # http://localhost:8000
```

> `makemigrations accounts tasks` generates the migration files (commit them). Run it *before* `migrate`, because the
> project uses a custom email-based user model.

## Run the frontend

```bash
cd frontend
npm install
cp .env.example .env                # VITE_API_URL=http://localhost:8000/api
npm run dev                         # http://localhost:5173
```

The backend only accepts requests from the origin in `FRONTEND_URL` (CORS).

## Test user

After `python manage.py seed_demo`:

| Email | Password |
|-------|----------|
| demo@example.com | Demo@12345 |

(Or register your own account on `/register`.)

## Run with Docker (bonus)

```bash
docker compose up --build
# frontend http://localhost:5173   backend http://localhost:8000
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py seed_demo
```

## Tests (bonus)

```bash
cd backend
python manage.py test                      # uses MySQL; the DB user must be able to create test_task_manager
USE_SQLITE=True python manage.py test      # no MySQL needed
```

## Email reminders (bonus)

```bash
python manage.py send_task_reminders       # emails users about unfinished tasks due tomorrow
```
Emails print to the terminal by default. Set the `EMAIL_*` variables in `.env` for real SMTP.
Schedule it daily with cron / Windows Task Scheduler.

## API list

All endpoints start with `/api/`. Everything except register, login, refresh and logout needs `Authorization: Bearer <access>`; otherwise the API returns `401`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register (`first_name, last_name, email, password, confirm_password`) |
| POST | `/api/auth/login/` | Login with email, returns `access` (30 min) and `refresh` (1 day) |
| POST | `/api/auth/token/refresh/` | Get a new access token |
| POST | `/api/auth/logout/` | Blacklist the refresh token (bonus) |
| GET | `/api/auth/me/` | Current user |
| PUT | `/api/auth/change-password/` | `old_password, new_password, confirm_password` |
| GET, POST | `/api/categories/` | List / create own categories |
| PUT, DELETE | `/api/categories/{id}/` | Update / delete (tasks are kept, category set to none) |
| GET, POST | `/api/tasks/` | List (filters below, 10 per page) / create |
| GET, PUT, PATCH, DELETE | `/api/tasks/{id}/` | Retrieve / update / delete |
| PATCH | `/api/tasks/{id}/toggle-complete/` | Switch between Done and To Do |
| GET | `/api/tasks/dashboard/` | Counts, completion %, per-category counts, due today and overdue lists |
| POST | `/api/tasks/{id}/subtasks/` | Add a subtask (bonus) |
| PATCH, DELETE | `/api/tasks/{id}/subtasks/{sid}/` | Update / delete a subtask (bonus) |

**Task filters:** `status`, `priority`, `category` (id), `due` (`today`, `overdue`, `upcoming`), `search` (title and description),
`ordering` (`due_date`, `priority`, `created_at`, prefix `-` for descending), `page`, `page_size` (max 100, used by the Kanban board).
Example: `/api/tasks/?status=To Do&priority=High&due=overdue&ordering=due_date&page=1`

**Rules worth knowing**
- Overdue = due date passed and status is not Done. "Due today" also excludes Done tasks.
- `priority` ordering is by meaning (Low < Medium < High). Tasks without a due date sort last.
- The "no past due date" rule applies when creating a task, so old tasks can still be edited.
- Errors use `{ "field_name": ["message"] }` with status 400, 401, 404 as appropriate.
- Recurring tasks (daily / weekly): completing one creates the next occurrence once, with its subtasks reset.

## Postman

Import `docs/Task-Manager.postman_collection.json`. Run **Login** first; it stores the tokens in collection variables.

## Screenshots

Add screenshots of each page and Django Admin to `docs/screenshots/` (register, login, dashboard, tasks list, board,
create/edit task, categories, profile, 404, admin).

## Demo flow checklist

Register → Login (dashboard) → refresh (still logged in) → create categories → create tasks → try a past due date →
search / filter overdue / sort → complete a task → edit → delete with confirmation → dashboard →
set `ACCESS_TOKEN_MINUTES=1` in `.env`, restart, wait 1 minute and click around to see the silent refresh →
logout → open `/tasks` (redirected to login) → show data in `/admin/`.

## Deployment (Vercel + Render)

**1. MySQL.** Render has no managed MySQL, so create a free cloud MySQL (Aiven, TiDB Cloud, or Railway) and note host, port, database, user, password.

**2. GitHub.** `git init && git add . && git commit -m "Task manager" && git push` to a new repository.
Also run `python manage.py makemigrations accounts tasks` locally first and commit the migration files.

**3. Backend on Render.** New → Blueprint (uses `render.yaml`) or New → Web Service, runtime **Docker**, root directory `backend`.
Environment variables: `SECRET_KEY`, `DEBUG=False`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSL=True`,
`FRONTEND_URL` (set after step 4). Open the Render Shell and run `python manage.py createsuperuser` and `python manage.py seed_demo`.

**4. Frontend on Vercel.** Import the repo, set **Root Directory** to `frontend`, framework Vite, and add
`VITE_API_URL=https://<your-render-service>.onrender.com/api`. Deploy.

**5. Connect them.** Put the Vercel URL into Render's `FRONTEND_URL` (exact origin, no trailing slash) and redeploy the backend (CORS).

Free Render services sleep after inactivity, so the first request can take about 50 seconds.
