from app.core.config import settings
from app.integrations.crm.hubspot_crm import HubSpotCRMAdapter
from app.integrations.crm.mock_crm import MockCRMAdapter
from app.integrations.crm.protocol import (
    CRMCustomerPayload,
    CRMProviderProtocol,
    CRMSyncResult,
    CRMWorkOrderPayload,
)

_mock_crm_instance: MockCRMAdapter | None = None


def get_crm_provider() -> CRMProviderProtocol:
    global _mock_crm_instance
    if settings.CRM_PROVIDER == "hubspot":
        return HubSpotCRMAdapter()
    if _mock_crm_instance is None:
        _mock_crm_instance = MockCRMAdapter()
    return _mock_crm_instance


__all__ = [
    "CRMCustomerPayload",
    "CRMProviderProtocol",
    "CRMSyncResult",
    "CRMWorkOrderPayload",
    "HubSpotCRMAdapter",
    "MockCRMAdapter",
    "get_crm_provider",
]
