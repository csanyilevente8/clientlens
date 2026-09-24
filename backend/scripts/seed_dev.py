"""Throwaway dev seed: insert one tenant + one user so login can be tested.

Run from backend/:  uv run python -m scripts.seed_dev
Idempotent-ish: skips if the tenant slug already exists.
NOT for production — dev convenience only.
"""

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.roles import Role
from app.models.tenants import Tenant
from app.models.users import User


async def main() -> None:
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(Tenant).where(Tenant.slug == "acme"))
        ).scalar_one_or_none()
        if existing:
            print("Tenant 'acme' already exists; skipping seed.")
            return

        tenant = Tenant(name="Acme Wealth Advisors", slug="acme")
        session.add(tenant)
        await session.flush()  # assigns tenant.id without committing yet

        user = User(
            tenant_id=tenant.id,
            email="advisor@acme.com",
            role=Role.ADVISOR,
            hashed_password=hash_password("secret123"),
        )
        session.add(user)
        await session.commit()
        print(f"Seeded tenant={tenant.slug} user={user.email} (password: secret123)")


if __name__ == "__main__":
    asyncio.run(main())
