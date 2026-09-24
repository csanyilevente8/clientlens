"""Tenant-scoped repository base (ADR-008, Approach B).

Every read/write is automatically constrained to a single tenant. The repository is
constructed bound to one tenant_id (resolved server-side from the JWT), and every query
injects `WHERE tenant_id = :tenant_id`. This makes "forgetting the tenant filter"
impossible for normal queries — the safe path is the default.

Java/Spring analog: an abstract `BaseRepository<T>` over the EntityManager, except the
tenant filter is baked in so callers cannot omit it.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base


class TenantScopedRepository[ModelT: Base]:
    """Generic CRUD repository scoped to a single tenant.

    Subclasses set `model` to their SQLAlchemy model class. All models used here must
    have a `tenant_id` column (enforced by convention: tenant-owned entities carry it).
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, id: str) -> ModelT | None:
        """Fetch one row by id, scoped to this tenant.

        Filters by BOTH id and tenant_id: requesting another tenant's row by guessing its
        id returns None, not the row (the §16 "don't trust GET /clients/{id}" defense).
        """
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == id,
                self.model.tenant_id == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[ModelT]:
        """List all rows for this tenant."""
        result = await self.session.execute(
            select(self.model).where(self.model.tenant_id == self.tenant_id)
        )
        return list(result.scalars().all())

    async def add(self, entity: ModelT) -> ModelT:
        """Persist a new entity, forcing its tenant_id to this repository's tenant.

        We OVERWRITE tenant_id rather than trust the caller's value (never trust input,
        §16 / Rule 5). flush() populates the generated id without committing — the caller
        (endpoint/service) owns the transaction boundary and commits.
        """
        entity.tenant_id = self.tenant_id
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, id: str) -> bool:
        """Delete a row by id if it belongs to this tenant. Returns True if deleted."""
        entity = await self.get(id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
