"""CRM client selection by configuration.

The rest of the app calls get_crm_client() and does not care about the concrete type.
Currently there is one implementation (HTTP, pointed at the mock or a real CRM via
CRM_BASE_URL); a different vendor SDK would be a new module + a branch here.

Not lru_cached: the HTTP client owns an httpx.AsyncClient (a resource with a lifecycle),
so callers construct and close it explicitly rather than sharing a process-wide singleton.
"""

from app.core.config import get_settings
from app.integrations.crm.base import CRMClient
from app.integrations.crm.http import HTTPCRMClient


def get_crm_client() -> CRMClient:
    return HTTPCRMClient(get_settings().crm_base_url)
