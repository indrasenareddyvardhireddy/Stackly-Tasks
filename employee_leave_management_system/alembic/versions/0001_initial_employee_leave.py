"""initial employee leave management schema

Revision ID: 0001_initial_employee_leave
Revises:
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "0001_initial_employee_leave"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    # =========================================================
    # USERS TABLE
    # =========================================================

    op.create_table(
        "users",

        sa.Column(
            "user_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False
        ),

        sa.Column(
            "username",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "email",
            sa.String(length=150),
            nullable=False
        ),

        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False
        ),

        sa.Column(
            "role",
            sa.Enum(
                "Admin",
                "HR",
                "Employee",
                name="user_role"
            ),
            nullable=False
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.PrimaryKeyConstraint("user_id"),

        sa.UniqueConstraint(
            "username",
            name="uq_users_username"
        ),

        sa.UniqueConstraint(
            "email",
            name="uq_users_email"
        )
    )

    op.create_index(
        "ix_users_username",
        "users",
        ["username"],
        unique=True
    )

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True
    )


    # =========================================================
    # DEPARTMENTS TABLE
    # =========================================================

    op.create_table(
        "departments",

        sa.Column(
            "department_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False
        ),

        sa.Column(
            "department_name",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.PrimaryKeyConstraint("department_id"),

        sa.UniqueConstraint(
            "department_name",
            name="uq_departments_department_name"
        )
    )

    op.create_index(
        "ix_departments_department_name",
        "departments",
        ["department_name"],
        unique=True
    )


    # =========================================================
    # EMPLOYEES TABLE
    # =========================================================

    op.create_table(
        "employees",

        sa.Column(
            "employee_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "employee_code",
            sa.String(length=50),
            nullable=False
        ),

        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False
        ),

        sa.Column(
            "email",
            sa.String(length=150),
            nullable=False
        ),

        sa.Column(
            "phone",
            sa.String(length=10),
            nullable=False
        ),

        sa.Column(
            "department_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "designation",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "salary",
            sa.Numeric(12, 2),
            nullable=False
        ),

        sa.Column(
            "date_of_joining",
            sa.Date(),
            nullable=False
        ),

        sa.Column(
            "employment_type",
            sa.Enum(
                "Full-Time",
                "Part-Time",
                "Intern",
                "Contract",
                name="employment_type"
            ),
            nullable=False
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_employees_user"
        ),

        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.department_id"],
            name="fk_employees_department"
        ),

        sa.PrimaryKeyConstraint("employee_id"),

        sa.UniqueConstraint(
            "employee_code",
            name="uq_employees_employee_code"
        ),

        sa.UniqueConstraint(
            "email",
            name="uq_employees_email"
        ),

        sa.UniqueConstraint(
            "user_id",
            name="uq_employees_user_id"
        )
    )

    op.create_index(
        "ix_employees_employee_code",
        "employees",
        ["employee_code"],
        unique=True
    )

    op.create_index(
        "ix_employees_email",
        "employees",
        ["email"],
        unique=True
    )

    op.create_index(
        "ix_employees_user_id",
        "employees",
        ["user_id"],
        unique=True
    )

    op.create_index(
        "ix_employees_department_id",
        "employees",
        ["department_id"],
        unique=False
    )


    # =========================================================
    # LEAVE REQUESTS TABLE
    # =========================================================

    op.create_table(
        "leave_requests",

        sa.Column(
            "leave_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False
        ),

        sa.Column(
            "employee_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "leave_type",
            sa.Enum(
                "Sick",
                "Casual",
                "Earned",
                name="leave_type"
            ),
            nullable=False
        ),

        sa.Column(
            "start_date",
            sa.Date(),
            nullable=False
        ),

        sa.Column(
            "end_date",
            sa.Date(),
            nullable=False
        ),

        sa.Column(
            "total_days",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "reason",
            sa.String(length=500),
            nullable=False
        ),

        sa.Column(
            "status",
            sa.Enum(
                "Pending",
                "Approved",
                "Rejected",
                "Cancelled",
                name="leave_status"
            ),
            nullable=False,
            server_default="Pending"
        ),

        sa.Column(
            "rejection_reason",
            sa.String(length=500),
            nullable=True
        ),

        sa.Column(
            "approved_by",
            sa.Integer(),
            nullable=True
        ),

        sa.Column(
            "approved_at",
            sa.DateTime(),
            nullable=True
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.employee_id"],
            name="fk_leave_employee"
        ),

        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.user_id"],
            name="fk_leave_approved_by"
        ),

        sa.PrimaryKeyConstraint("leave_id")
    )

    op.create_index(
        "ix_leave_requests_employee_id",
        "leave_requests",
        ["employee_id"],
        unique=False
    )

    op.create_index(
        "ix_leave_requests_status",
        "leave_requests",
        ["status"],
        unique=False
    )

    op.create_index(
        "ix_leave_requests_leave_type",
        "leave_requests",
        ["leave_type"],
        unique=False
    )


def downgrade():

    # Drop in reverse dependency order

    op.drop_index(
        "ix_leave_requests_leave_type",
        table_name="leave_requests"
    )

    op.drop_index(
        "ix_leave_requests_status",
        table_name="leave_requests"
    )

    op.drop_index(
        "ix_leave_requests_employee_id",
        table_name="leave_requests"
    )

    op.drop_table("leave_requests")

    op.drop_index(
        "ix_employees_department_id",
        table_name="employees"
    )

    op.drop_index(
        "ix_employees_user_id",
        table_name="employees"
    )

    op.drop_index(
        "ix_employees_email",
        table_name="employees"
    )

    op.drop_index(
        "ix_employees_employee_code",
        table_name="employees"
    )

    op.drop_table("employees")

    op.drop_index(
        "ix_departments_department_name",
        table_name="departments"
    )

    op.drop_table("departments")

    op.drop_index(
        "ix_users_email",
        table_name="users"
    )

    op.drop_index(
        "ix_users_username",
        table_name="users"
    )

    op.drop_table("users")