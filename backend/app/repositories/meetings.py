"""Meeting repository — tenant-scoped CRUD over the Meeting model."""

from app.models.meetings import Meeting
from app.repositories.base import TenantScopedRepository


class MeetingRepository(TenantScopedRepository[Meeting]):
    model = Meeting
