# Hospital Appointment Booking System

A FastAPI backend for hospital departments, doctors, schedules,
appointments, consultations, medical files, notifications, and (when
implemented) live queue updates.

> **Important:** This README is based on the project details discussed
> during development. Confirm exact paths, request fields, role
> dependencies, and feature availability in your current code and
> Swagger UI at `/docs`. An endpoint described here is not proof that it
> is already implemented.

## Contents

-   Features
-   Technology stack
-   Project structure
-   Roles and permissions
-   API endpoint reference
-   Appointment workflow and rules
-   Schedules and slots
-   Consultations and files
-   Email notifications
-   Level 8 WebSockets
-   Installation and setup
-   Run and test
-   Troubleshooting
-   Security recommendations

## Features

-   JWT authentication for protected routes.
-   Admin, Doctor, and Patient roles.
-   Patient registration and login.
-   Department and doctor management.
-   Doctor schedules, breaks, and leave handling, if implemented.
-   Appointment booking, listing, cancellation, and rescheduling.
-   Appointment numbers and queue token numbers.
-   Appointment check-in and consultation workflow.
-   Consultation records linked to appointments.
-   Appointment file upload, listing, and download.
-   Patient appointment history.
-   SMTP emails when configured and called by the application.
-   Live queue and personal notifications for Level 8, if implemented.

## Technology stack

-   Python 3.9+
-   FastAPI and Uvicorn
-   SQLAlchemy ORM
-   MySQL and typically PyMySQL
-   Pydantic
-   JWT authentication
-   Password hashing using the library configured in the project
-   SMTP email
-   FastAPI/Starlette WebSockets
-   Alembic, if configured in the repository

Check `requirements.txt` for the exact package versions.

## Project structure

Your actual file names may differ. Keep existing project names rather
than creating duplicate routers.

``` text
hospital_appointment_booking/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── auth/
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── departments.py
│   │   ├── doctors.py
│   │   ├── appointments.py
│   │   ├── consultations.py
│   │   ├── files.py
│   │   └── reports.py
│   ├── services/
│   │   ├── booking.py
│   │   └── notifications.py
│   └── websockets/          # if Level 8 is implemented
│       ├── manager.py
│       └── router.py
├── static/
│   └── queue_test.html      # optional WebSocket test page
├── alembic/                 # if configured
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Roles and permissions

This is the intended policy; actual access is defined by your route
dependencies and ownership checks.

  ----------------------------------------------------------------------------
  Capability             Admin             Doctor            Patient
  ---------------------- ----------------- ----------------- -----------------
  Login                  Yes               Yes               Yes

  Public registration    No admin          No                Yes, patient only
                         registration                        

  View own profile       Yes               Yes               Yes

  Manage departments     Yes               No by default     No

  Create doctor accounts Yes               No                No

  View                   Yes               Yes               Yes
  doctors/departments                                        

  Manage doctor          Admin or as       Own               No
  schedules/leave        configured        schedule/leave if 
                                           permitted         

  Book appointment       Usually no        No                Yes

  List appointments      Hospital-wide if  Assigned doctor's Own appointments
                         authorized        appointments      

  Cancel appointment     If policy permits As configured     Own eligible
                                                             appointment

  Reschedule appointment As configured     No by default     Own eligible
                                                             appointment

  Check in patient       Yes               No by default     No

  Create consultation    No by default     Assigned doctor   No

  View consultation      If policy permits Assigned doctor   Own appointment
                                                             if permitted

  Upload/list/download   As configured     Authorized        Own authorized
  files                                    appointments      appointments

  Patient history        If explicitly     As configured     Own history
                         permitted                           

  Hospital reports       Yes               Only if granted   No

  Live queue             Authenticated and Yes               As allowed by
                         authorized users                    queue visibility
                                                             policy

  Personal notifications Own connection    Own connection    Own connection
  ----------------------------------------------------------------------------

Always verify each route's `Depends(...)`, `require_roles(...)`,
appointment ownership, and doctor assignment checks.

## API endpoint reference

The paths below include routes discussed during development. Check
`/docs` for the exact registered routes and schemas. Some paths are
expected patterns and may differ in your code.

### Authentication

  ------------------------------------------------------------------------
  Method            Endpoint           Intended access   Purpose
  ----------------- ------------------ ----------------- -----------------
  POST              `/auth/register`   Public; patient   Register a
                                       registration only patient

  POST              `/auth/login`      Public            Authenticate and
                                                         receive token(s)

  GET               `/auth/me`         Authenticated     Current profile
                                       user              
  ------------------------------------------------------------------------

### Departments

  -------------------------------------------------------------------------------------------
  Method            Endpoint                         Intended access        Purpose
  ----------------- -------------------------------- ---------------------- -----------------
  GET               `/departments`                   Public/authenticated   List departments
                                                     depending on           
                                                     configuration          

  POST              `/departments`                   Admin                  Create department

  GET               `/departments/{department_id}`   Public/authenticated   Department
                                                     depending on           details
                                                     configuration          

  PUT               `/departments/{department_id}`   Admin                  Update department

  DELETE            `/departments/{department_id}`   Admin                  Delete department
  -------------------------------------------------------------------------------------------

### Doctors, schedules, and leave

  -----------------------------------------------------------------------------------------------------------
  Method            Endpoint                                         Intended access        Purpose
  ----------------- ------------------------------------------------ ---------------------- -----------------
  POST              `/admin/doctors`                                 Admin                  Create doctor
                                                                                            account/profile

  GET               `/doctors`                                       Public/authenticated   List doctors
                                                                     depending on           
                                                                     configuration          

  GET               `/doctors/{doctor_id}`                           Public/authenticated   Doctor details
                                                                     depending on           
                                                                     configuration          

  POST              `/doctors/{doctor_id}/schedules`                 Admin or authorized    Add schedule
                                                                     doctor                 

  GET               `/doctors/{doctor_id}/schedules`                 As configured          List schedules

  PUT               `/doctors/{doctor_id}/schedules/{schedule_id}`   Admin or authorized    Update schedule
                                                                     doctor                 

  POST              `/doctors/{doctor_id}/leaves`                    Admin or authorized    Add doctor leave
                                                                     doctor                 

  GET               `/doctors/{doctor_id}/available-slots`           As configured          Get available
                                                                                            slots

  PUT               `/doctors/me/call-next`                          Doctor only            Call next
                                                                                            eligible
                                                                                            checked-in
                                                                                            patient
  -----------------------------------------------------------------------------------------------------------

### Appointments

  ------------------------------------------------------------------------------------------------------
  Method            Endpoint                                      Intended access      Purpose
  ----------------- --------------------------------------------- -------------------- -----------------
  POST              `/appointments`                               Patient              Book appointment

  GET               `/appointments`                               Admin, Doctor,       List appointments
                                                                  Patient; results     
                                                                  filtered by role     

  GET               `/appointments/{appointment_id}`              Authorized           Appointment
                                                                  participants/admin   details

  PUT               `/appointments/{appointment_id}/cancel`       Patient owning       Cancel
                                                                  appointment or       appointment
                                                                  Admin, subject to    
                                                                  policy               

  PUT               `/appointments/{appointment_id}/reschedule`   Patient owning       Reschedule
                                                                  appointment          appointment

  PUT               `/appointments/{appointment_id}/check-in`     Admin                Check in patient
  ------------------------------------------------------------------------------------------------------

### Consultations and files

  ------------------------------------------------------------------------------------------------------------
  Method            Endpoint                                               Intended access   Purpose
  ----------------- ------------------------------------------------------ ----------------- -----------------
  POST              `/appointments/{appointment_id}/consultation`          Assigned Doctor   Create
                                                                                             consultation

  GET               `/appointments/{appointment_id}/consultation`          Authorized        View consultation
                                                                           doctor/patient;   
                                                                           admin if          
                                                                           permitted         

  POST              `/appointments/{appointment_id}/files?file_type=...`   Authorized user   Upload file
                                                                           according to file 
                                                                           policy            

  GET               `/appointments/{appointment_id}/files`                 Authorized        List files
                                                                           appointment       
                                                                           participants      

  GET               `/files/{file_id}/download`                            Authorized user   Download file

  GET               `/patients/me/history`                                 Patient; admin    Patient history
                                                                           only if           
                                                                           explicitly        
                                                                           allowed           
  ------------------------------------------------------------------------------------------------------------

### Reports

Report paths depend on the report router registered in `app/main.py`.
Intended policy: Admin can view hospital-wide reports; doctors may see
their own reports only if permitted; patients should see only their own
information. Check `/docs` for exact paths.

## Appointment workflow and rules

Typical workflow: 1. Admin creates a department. 2. Admin creates a
doctor account and profile. 3. Admin or authorized doctor configures
schedule, break, and leave. 4. Patient registers and logs in. 5. Patient
checks available slots and books an appointment. 6. Admin checks in the
patient within the allowed time window. 7. Doctor calls the next
checked-in patient. 8. Appointment becomes `In Consultation`. 9. Doctor
saves the consultation. 10. Doctor calls the next patient only after the
current consultation is saved.

Rules discussed during development: - Doctor must be active and the
requested slot valid. - Duplicate/occupied slots should be rejected. -
The implementation includes checks intended to prevent a patient from
booking overlapping appointments and more than one appointment with the
same doctor on the same day. - Patient cancellation requires more than
two hours before the appointment in the discussed implementation. -
Rescheduling is limited to two times and requires more than two hours
before the appointment in the discussed implementation. - Check-in is
restricted to an allowed window, described as 30 minutes before the
appointment in the discussed implementation. - Consultation creation
requires appointment status `In Consultation`. - Verify actual status
strings and rules in code.

## Schedules and slots

A schedule typically includes weekday, start time, end time, and
optional break start/end. The booking service should check that the
appointment is in the future, matches the doctor's working day and
hours, avoids breaks and leave, and is not already booked.

Example body (if your schema uses these fields):

``` json
{
  "day_of_week": 0,
  "start_time": "09:00:00",
  "end_time": "13:00:00",
  "break_start": "11:00:00",
  "break_end": "11:30:00"
}
```

This assumes Monday is `0`; verify your code's weekday convention. For a
15-minute slot duration, 11:00--11:30 should not be bookable.

Example appointment body (confirm in Swagger):

``` json
{
  "doctor_id": 2,
  "appointment_date": "2026-10-20",
  "slot_time": "09:00:00",
  "reason": "Regular checkup"
}
```

Use a future date and a genuinely available slot.

## Consultations and medical files

### Create a consultation

1.  Log in as the assigned doctor.
2.  Ensure the appointment is `In Consultation`.
3.  Call `POST /appointments/{appointment_id}/consultation`.
4.  Send the fields required by the actual Pydantic schema.
5.  Verify with `GET /appointments/{appointment_id}/consultation`.

Diagnosis, prescription, and notes are common fields, but the exact JSON
must match your schema.

### Upload a file

1.  Log in with a user authorized for the appointment.
2.  Open `POST /appointments/{appointment_id}/files`.
3.  Enter the appointment ID and select a file.
4.  Set `file_type` to one of the exact accepted category strings:
    -   `Lab Report`
    -   `Prescription`
    -   `Scan`
5.  List files with `GET /appointments/{appointment_id}/files`.
6.  Download an authorized file with `GET /files/{file_id}/download`.

Example query value:

``` text
file_type=Lab%20Report
```

`file_type` is a category, not a file extension. Sending `Image` causes
`422 Invalid file_type` with the current validator. Accepted extensions
and MIME types depend on other upload validation in the code. Validate
file size, extension, MIME type, and content server-side; protect
medical files from public access.

## Email notifications

SMTP emails are sent only if SMTP is configured and the relevant
route/service calls the notification function. Depending on your
implementation, messages may go to patients for registration and
appointment changes, and to doctors for booking/change notifications.
Reminders require a scheduled job or another explicit trigger.

Example environment values (use the exact setting names read by
`app/config.py`):

``` dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-email-app-password
SMTP_FROM=your-email@example.com
```

For Gmail, use an App Password where required. Do not commit
credentials. A background task being scheduled does not guarantee
delivery; check application logs for SMTP errors.

## Level 8: WebSockets and live queue

This describes the required behavior; verify the code before treating it
as implemented.

  --------------------------------------------------------------------------------------------
  Type                    Endpoint                                     Purpose
  ----------------------- -------------------------------------------- -----------------------
  WebSocket               `/ws/queue/{doctor_id}?token=ACCESS_TOKEN`   Live doctor queue

  WebSocket               `/ws/notifications?token=ACCESS_TOKEN`       Private user
                                                                       notifications

  HTTP                    `PUT /doctors/me/call-next`                  Doctor advances queue
  --------------------------------------------------------------------------------------------

Queue updates should include the current token/patient, waiting count,
and for a patient their own token, queue position, and estimated wait.

``` text
Estimated waiting time = patients ahead × doctor's slot duration
```

Example: two patients ahead × 15-minute slots = about 30 minutes.

Broadcast updates after successful database commits when patients check
in, appointments are cancelled or marked no-show, the doctor calls next,
or a booking/reschedule changes the queue. Notify patients on booking,
cancellation, rescheduling, and when their turn is next:

`You are next, please be ready`

Security requirements: - Validate the access token before accepting the
WebSocket. - Reject invalid/expired tokens and authorize access to the
requested doctor's queue. - Deliver personal notifications only to the
authenticated user's connections. - Remove disconnected connections
safely. - For multiple server workers, use a shared broker such as
Redis; an in-memory manager only broadcasts within one process.

### Test with Postman

Connect to:

``` text
ws://localhost:8000/ws/queue/1?token=YOUR_ACCESS_TOKEN
```

Then call check-in or call-next from Swagger and confirm a live message
arrives.

### Test in browser console

Open Developer Tools → Console and run:

``` javascript
const ws = new WebSocket(
  "ws://localhost:8000/ws/queue/1?token=YOUR_ACCESS_TOKEN"
);

ws.onmessage = (event) => console.log("Queue update:", event.data);
ws.onclose = (event) => console.log("Closed:", event.code, event.reason);
ws.onerror = (event) => console.error("WebSocket error:", event);
```

Replace the placeholder with a valid access token. Never share real
tokens. Open another tab with another authorized user's token to test
simultaneous connections.

### Optional HTML page

If `static/queue_test.html` is served by FastAPI, open
`http://localhost:8000/queue-test`. The page should accept token and
doctor ID, connect/disconnect, and display incoming messages. The file
must be explicitly served by a route or static-file configuration.

## Installation and setup

### Prerequisites

-   Python 3.9+ (compatible with the project's dependencies)
-   MySQL Server
-   VS Code and Git (optional)

### 1. Open the project

Use your actual project path, for example:

``` powershell
cd C:\Users\indra\OneDrive\Desktop\Stackly-Tasks\hospital_appointment_booking123
```

### 2. Create and activate a virtual environment

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

``` bat
venv\Scripts\activate.bat
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create the database

Run in MySQL Workbench or MySQL CLI:

``` sql
CREATE DATABASE hospital_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Use the database name configured in `.env` if it differs.

### 5. Configure `.env`

Create `.env` from `.env.example` if available. Example only:

``` dotenv
DATABASE_URL=mysql+pymysql://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:3306/hospital_db
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
```

Your project may use `JWT_SECRET_KEY` instead of `SECRET_KEY` or another
database setting name. Match the variables read by `app/config.py` and
`app/database.py`. URL-encode special characters in database passwords
if needed. Never commit `.env`.

### 6. Create tables / apply migrations

If Alembic is configured:

``` powershell
alembic upgrade head
```

To create a new migration after a model change, review it before
applying:

``` powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

If the project creates tables another way, follow its existing
startup/database initialization logic. Ensure all models are imported
into Alembic metadata.

### 7. Create an admin account

If the repository contains `scripts/create_admin.py`, its module command
may be:

``` powershell
python -m scripts.create_admin
```

Inspect the script for its actual behavior and credentials. Do not
assume a default password; change development credentials before
deployment.

## Run the application

From the project root with the virtual environment active:

``` powershell
uvicorn app.main:app --reload
```

If your application module differs, adjust the import path.

-   Swagger: `http://127.0.0.1:8000/docs`
-   ReDoc: `http://127.0.0.1:8000/redoc`
-   OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Suggested API test order

1.  Register a patient.
2.  Log in as Admin and authorize Swagger.
3.  Create a department.
4.  Create a doctor with `POST /admin/doctors`.
5.  Add the doctor's schedule and leave if applicable.
6.  Log in as Doctor.
7.  Log in as Patient, check available slots, and book an appointment.
8.  Check in the appointment as Admin during the permitted time window.
9.  Call next as Doctor.
10. Create the consultation while the appointment is `In Consultation`.
11. Verify consultation details and upload/list/download an authorized
    file.
12. Test cancellation/rescheduling on separate eligible appointments.
13. Test that unauthorized roles cannot access restricted endpoints.
14. Test WebSocket updates if Level 8 is implemented.

Always use actual IDs returned by API responses and the request bodies
shown in Swagger.

## Troubleshooting

### `401 Unauthorized`

Check that the access token is present, valid, not expired, and is not a
refresh token. Log in again and re-authorize.

### `403 Forbidden`

The user may be authenticated but lacks the required role. Verify
`require_roles(...)` and ownership checks.

### `404 Not Found`

Confirm the record exists and use the actual ID.

### `409 Conflict` / slot conflict

The slot may already be booked or violate duplicate-booking rules.
Choose another available slot.

### `Appointment must be In Consultation`

Check in the patient as Admin, then call next as the assigned Doctor.
Create the consultation only after the status changes to
`In Consultation`. Save the current consultation before calling the next
patient if required by queue logic.

### Datetime comparison error

Do not compare timezone-aware and timezone-naive `datetime` objects. Use
a consistent timezone convention throughout schedule and booking
validation.

### `Invalid file_type`

Use exactly `Lab Report`, `Prescription`, or `Scan`. `Image` is rejected
by the current validator. File extensions are checked separately, if
that validation exists.

### SMTP timeout / email not received

Verify SMTP host, port, username, password, sender, and application
logs. Confirm the endpoint calls the notification function. A scheduled
background task is not proof that an email was delivered.

### WebSocket connection fails

Check server status, endpoint path, doctor ID, valid access token,
router registration, and token validation. In-memory broadcasts do not
reach clients connected to other worker processes.

## Security recommendations

-   Store password hashes, never plaintext passwords.
-   Keep `.env` and credentials out of Git; commit only `.env.example`
    with placeholders.
-   Validate role and record ownership on every protected endpoint.
-   Validate file size, extension, MIME type, and content; protect
    medical documents.
-   Do not log passwords, JWTs, reset tokens, or sensitive medical
    information.
-   Use HTTPS/WSS in production.
-   Use secure refresh-token handling if refresh tokens are implemented.
-   Do not expose one patient's appointments, consultations, or files to
    another patient.
-   Test authentication, role permissions, booking conflicts, queue
    transitions, and WebSocket disconnection behavior.

## Implementation status

This README is a project guide, not proof that every route or Level 8
feature is active. Confirm registered routes in Swagger and check the
source code for WebSocket authentication/broadcasting, call-next state
transitions, file validation, SMTP triggers, report permissions, and
consultation ownership before claiming production readiness.
