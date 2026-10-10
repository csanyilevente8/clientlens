"""Meeting repository — tenant-scoped CRUD over the Meeting model."""

from sqlalchemy import select

from app.models.meetings import Meeting
from app.repositories.base import TenantScopedRepository


class MeetingRepository(TenantScopedRepository[Meeting]):
    model = Meeting

    async def list_by_client(self, client_id: str) -> list[Meeting]:
        """List this tenant's meetings for one client, newest first.

        Stays tenant-scoped (tenant_id AND client_id) so it cannot cross tenants — a
        client_id from another tenant simply matches nothing.
        """
        result = await self.session.execute(
            select(Meeting)
            .where(Meeting.tenant_id == self.tenant_id, Meeting.client_id == client_id)
            .order_by(Meeting.occurred_at.desc())
        )
        return list(result.scalars().all())
