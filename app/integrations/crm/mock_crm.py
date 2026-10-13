import uuid
from typing import Any

from app.integrations.crm.protocol import (
    CRMCustomerPayload,
    CRMSyncResult,
    CRMWorkOrderPayload,
)


class MockCRMAdapter:
    """
    Deterministic in-memory CRM adapter for tests and local development.
    """

    def __init__(self):
        self.customers: dict[str, dict[str, Any]] = {}
        self.work_orders: dict[str, dict[str, Any]] = {}
        self._simulate_failure: bool = False
        self._failure_reason: str = "Simulated CRM upstream failure"
        self._fail_count_remaining: int = 0

    def simulate_failures(self, count: int, reason: str = "Simulated CRM error"):
        self._fail_count_remaining = count
        self._failure_reason = reason

    def clear(self):
        self.customers.clear()
        self.work_orders.clear()
        self._fail_count_remaining = 0

    async def sync_customer(self, payload: CRMCustomerPayload) -> CRMSyncResult:
        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return CRMSyncResult(
                success=False,
                provider="mock_hubspot",
                external_record_id="",
                record_type="Contact",
                error_message=self._failure_reason,
            )

        crm_id = f"crm_cust_{uuid.uuid4().hex[:10]}"
        self.customers[payload.internal_customer_id] = {
            "crm_id": crm_id,
            "name": payload.name,
            "email": payload.email,
            "phone": payload.phone,
            "address": payload.service_address,
            "metadata": payload.metadata or {},
        }
        return CRMSyncResult(
            success=True,
            provider="mock_hubspot",
            external_record_id=crm_id,
            record_type="Contact",
        )

    async def sync_work_order(self, payload: CRMWorkOrderPayload) -> CRMSyncResult:
        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return CRMSyncResult(
                success=False,
                provider="mock_hubspot",
                external_record_id="",
                record_type="Ticket",
                error_message=self._failure_reason,
            )

        crm_id = f"crm_ticket_{uuid.uuid4().hex[:10]}"
        self.work_orders[payload.internal_work_order_id] = {
            "crm_id": crm_id,
            "work_order_number": payload.work_order_number,
            "category": payload.category,
            "priority": payload.priority,
            "status": payload.status,
            "description": payload.description,
            "metadata": payload.metadata or {},
        }
        return CRMSyncResult(
            success=True,
            provider="mock_hubspot",
            external_record_id=crm_id,
            record_type="Ticket",
        )
