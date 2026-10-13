import logging

import httpx

from app.integrations.crm.protocol import (
    CRMCustomerPayload,
    CRMProviderProtocol,
    CRMSyncResult,
    CRMWorkOrderPayload,
)

logger = logging.getLogger(__name__)


class HubSpotCRMAdapter(CRMProviderProtocol):
    """
    HubSpot CRM integration adapter via REST API v3.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    async def sync_customer(self, payload: CRMCustomerPayload) -> CRMSyncResult:
        if not self.api_key:
            return CRMSyncResult(
                success=False,
                provider="hubspot",
                external_record_id="",
                record_type="Contact",
                error_message="HubSpot API key not configured.",
            )

        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "properties": {
                "email": payload.email or "",
                "firstname": payload.name,
                "phone": payload.phone,
                "address": payload.service_address,
                "fieldops_customer_id": payload.internal_customer_id,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    return CRMSyncResult(
                        success=True,
                        provider="hubspot",
                        external_record_id=res_json.get("id", ""),
                        record_type="Contact",
                    )
                return CRMSyncResult(
                    success=False,
                    provider="hubspot",
                    external_record_id="",
                    record_type="Contact",
                    error_message=f"HubSpot error {resp.status_code}: {resp.text}",
                )
        except Exception as exc:
            return CRMSyncResult(
                success=False,
                provider="hubspot",
                external_record_id="",
                record_type="Contact",
                error_message=f"HubSpot sync failed: {str(exc)}",
            )

    async def sync_work_order(self, payload: CRMWorkOrderPayload) -> CRMSyncResult:
        if not self.api_key:
            return CRMSyncResult(
                success=False,
                provider="hubspot",
                external_record_id="",
                record_type="Ticket",
                error_message="HubSpot API key not configured.",
            )

        url = "https://api.hubapi.com/crm/v3/objects/tickets"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "properties": {
                "subject": f"[{payload.category}] {payload.work_order_number}",
                "content": payload.description,
                "hs_ticket_priority": payload.priority,
                "hs_pipeline_stage": payload.status,
                "fieldops_work_order_id": payload.internal_work_order_id,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    return CRMSyncResult(
                        success=True,
                        provider="hubspot",
                        external_record_id=res_json.get("id", ""),
                        record_type="Ticket",
                    )
                return CRMSyncResult(
                    success=False,
                    provider="hubspot",
                    external_record_id="",
                    record_type="Ticket",
                    error_message=f"HubSpot ticket error {resp.status_code}: {resp.text}",
                )
        except Exception as exc:
            return CRMSyncResult(
                success=False,
                provider="hubspot",
                external_record_id="",
                record_type="Ticket",
                error_message=f"HubSpot ticket sync failed: {str(exc)}",
            )
