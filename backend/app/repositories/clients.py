"""Client repository — tenant-scoped CRUD over the Client model."""

from app.models.clients import Client
from app.repositories.base import TenantScopedRepository


class ClientRepository(TenantScopedRepository[Client]):
    model = Client
