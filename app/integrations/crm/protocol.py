from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CRMCustomerPayload:
    internal_customer_id: str
    name: str
    email: str | None
    phone: str
    service_address: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CRMWorkOrderPayload:
    internal_work_order_id: str
    work_order_number: str
    customer_id: str
    category: str
    priority: str
    status: str
    description: str
    assigned_technician_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CRMSyncResult:
    success: bool
    provider: str
    external_record_id: str
    record_type: str
    error_message: str | None = None


class CRMProviderProtocol(Protocol):
    """
    Provider-independent interface for bidirectional CRM synchronization (e.g. HubSpot, Salesforce).
    """

    async def sync_customer(self, payload: CRMCustomerPayload) -> CRMSyncResult:
        """Upsert customer contact in external CRM."""
        ...

    async def sync_work_order(self, payload: CRMWorkOrderPayload) -> CRMSyncResult:
        """Upsert work order / service deal / ticket in external CRM."""
        ...
