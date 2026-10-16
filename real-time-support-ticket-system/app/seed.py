"""Create sample categories and one test user per role. Run after `alembic upgrade head`:

    python -m app.seed
"""
import asyncio

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import AsyncSessionLocal
from app.models import AgentProfile, Category, User
from app.models.enums import Availability, Role

CATEGORIES = [
    ("Billing", "Invoices, payments and refunds"),
    ("Technical", "Bugs, errors and how-to questions"),
    ("Account", "Login, profile and security"),
    ("Delivery", "Shipping and order tracking"),
]

# name, email, password, role, categories handled (agents only)
USERS = [
    ("Admin User", "admin@example.com", "Admin@123", Role.ADMIN, []),
    ("Alice Agent", "agent1@example.com", "Agent@123", Role.AGENT, ["Billing", "Account"]),
    ("Bob Agent", "agent2@example.com", "Agent@123", Role.AGENT, ["Technical", "Delivery"]),
    ("Carol Customer", "customer@example.com", "Customer@123", Role.CUSTOMER, []),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        cats = {}
        for name, desc in CATEGORIES:
            cat = (await db.execute(select(Category).where(Category.category_name == name))).scalar_one_or_none()
            if cat is None:
                cat = Category(category_name=name, description=desc, is_active=True)
                db.add(cat)
            cats[name] = cat
        await db.flush()

        for name, email, password, role, cat_names in USERS:
            exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if exists:
                print(f"skip (exists): {email}")
                continue
            user = User(name=name, email=email, hashed_password=hash_password(password), role=role, is_active=True)
            if role == Role.AGENT:
                user.agent_profile = AgentProfile(
                    availability=Availability.OFFLINE, max_open_tickets=10,
                    categories=[cats[c] for c in cat_names],
                )
            db.add(user)
            print(f"created {role.value}: {email} / {password}")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
