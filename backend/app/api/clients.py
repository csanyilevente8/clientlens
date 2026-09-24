"""Client CRUD endpoints — all tenant-scoped via the ClientRepository dependency.

Note what these handlers do NOT do: they never read or set tenant_id. The repository
(bound to the caller's tenant) enforces isolation, so an endpoint cannot accidentally
touch another tenant's data (ADR-008, Approach B).
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClientRepoDep, SessionDep
from app.models.clients import Client
from app.schemas.clients import ClientCreate, ClientResponse

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate, repo: ClientRepoDep, session: SessionDep
) -> Client:
    client = Client(name=payload.name)  # tenant_id set by the repository
    created = await repo.add(client)
    await session.commit()  # endpoint owns the transaction boundary
    # refresh to load server-generated columns (created_at/updated_at) within the async
    # context — otherwise building the response triggers a lazy load and MissingGreenlet.
    await session.refresh(created)
    return created


@router.get("", response_model=list[ClientResponse])
async def list_clients(repo: ClientRepoDep) -> list[Client]:
    return await repo.list()


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str, repo: ClientRepoDep) -> Client:
    client = await repo.get(client_id)
    if client is None:
        # 404 for both "not found" and "belongs to another tenant" — do not reveal
        # that the id exists in a different tenant.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: str, repo: ClientRepoDep, session: SessionDep) -> None:
    deleted = await repo.delete(client_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    await session.commit()
