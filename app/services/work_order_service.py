import random
from datetime import UTC, datetime

from app.core.exceptions import (
    EntityNotFoundException,
    IdempotencyConflictException,
    IdempotencyPayloadMismatchException,
)
from app.domain.state_machine import WorkOrderStateMachine
from app.repositories.audit_repo import AuditRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.work_order_repo import WorkOrderRepository
from app.schemas.common import PaginatedResponse
from app.schemas.outbox import OutboxEventCreate, OutboxEventType
from app.schemas.work_order import (
    WorkOrderCategory,
    WorkOrderCreate,
    WorkOrderPriority,
    WorkOrderResponse,
    WorkOrderStatus,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)


class WorkOrderService:
    def __init__(
        self,
        work_order_repo: WorkOrderRepository,
        customer_repo: CustomerRepository,
        audit_repo: AuditRepository,
        idempotency_repo: IdempotencyRepository,
        outbox_repo: OutboxRepository | None = None,
    ):
        self.work_order_repo = work_order_repo
        self.customer_repo = customer_repo
        self.audit_repo = audit_repo
        self.idempotency_repo = idempotency_repo
        self.outbox_repo = outbox_repo or OutboxRepository(work_order_repo.db)

    @staticmethod
    def _generate_wo_number() -> str:
        year = datetime.now(UTC).year
        rand_num = random.randint(10000, 99999)
        return f"WO-{year}-{rand_num}"

    async def create_work_order(self, wo_in: WorkOrderCreate) -> WorkOrderResponse:
        key = wo_in.idempotency_key
        payload_data = wo_in.model_dump(mode="json", exclude={"idempotency_key"})
        request_hash = self.idempotency_repo.compute_request_hash(payload_data)

        # 1. Handle idempotency lock if key provided
        if key:
            acquired, existing = await self.idempotency_repo.acquire(
                key=key, scope="work_order_create", request_hash=request_hash
            )
            if not acquired and existing:
                if existing.get("status") == "COMPLETED":
                    # Check for payload mismatch
                    if existing.get("request_hash") != request_hash:
                        raise IdempotencyPayloadMismatchException(key)
                    # Return original cached response
                    return WorkOrderResponse(**existing["response_body"])
                elif existing.get("status") == "PENDING":
                    raise IdempotencyConflictException(key)

        try:
            # 2. Verify customer existence
            customer = await self.customer_repo.get_by_id(wo_in.customer_id)
            if not customer:
                raise EntityNotFoundException("Customer", wo_in.customer_id)

            doc_data = wo_in.model_dump()
            if not doc_data.get("idempotency_key"):
                doc_data.pop("idempotency_key", None)
            doc_data["work_order_number"] = self._generate_wo_number()
            doc_data["status"] = WorkOrderStatus.SUBMITTED.value
            doc_data["predicted_by_ml"] = False
            now = datetime.now(UTC)
            initial_transition = {
                "transition_id": f"tr_{int(now.timestamp() * 1000)}",
                "from_status": WorkOrderStatus.DRAFT.value,
                "to_status": WorkOrderStatus.SUBMITTED.value,
                "actor": "API_CLIENT",
                "timestamp": now,
                "reason": "Initial work order creation",
            }
            doc_data["audit_trail"] = [initial_transition]

            created = await self.work_order_repo.create(doc_data)

            # 3. Log audit event
            await self.audit_repo.log_event(
                entity_type="WorkOrder",
                entity_id=created["id"],
                action="CREATE",
                actor_role="CLIENT",
                changes={"status": WorkOrderStatus.SUBMITTED.value},
            )

            response_obj = WorkOrderResponse(**created)

            # 4. Commit idempotency record with cached result
            if key:
                await self.idempotency_repo.commit(
                    key=key,
                    scope="work_order_create",
                    response_code=201,
                    response_body=response_obj.model_dump(mode="json"),
                )

            return response_obj

        except Exception:
            if key:
                await self.idempotency_repo.release(key=key, scope="work_order_create")
            raise

    async def get_work_order(self, work_order_id: str) -> WorkOrderResponse:
        doc = await self.work_order_repo.get_by_id(work_order_id)
        if not doc:
            raise EntityNotFoundException("WorkOrder", work_order_id)
        return WorkOrderResponse(**doc)

    async def list_work_orders(
        self,
        status: WorkOrderStatus | None = None,
        priority: WorkOrderPriority | None = None,
        category: WorkOrderCategory | None = None,
        customer_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedResponse[WorkOrderResponse]:
        skip = (page - 1) * limit
        filter_query = {}
        if status:
            filter_query["status"] = status.value
        if priority:
            filter_query["priority"] = priority.value
        if category:
            filter_query["category"] = category.value
        if customer_id:
            filter_query["customer_id"] = customer_id

        if search and search.strip():
            items, total = await self.work_order_repo.search(
                search_term=search.strip(),
                base_filter=filter_query if filter_query else None,
                skip=skip,
                limit=limit,
            )
        else:
            items, total = await self.work_order_repo.get_many(filter_query, skip=skip, limit=limit)

        total_pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[WorkOrderResponse(**item) for item in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def transition_status(
        self, work_order_id: str, status_in: WorkOrderStatusUpdate
    ) -> WorkOrderResponse:
        current_wo = await self.get_work_order(work_order_id)
        current_status = WorkOrderStatus(current_wo.status)
        new_status = status_in.new_status

        # Validate domain state machine
        WorkOrderStateMachine.validate_transition(current_status, new_status)

        actor = status_in.actor_id or "DISPATCHER"
        updated = await self.work_order_repo.append_audit_transition(
            work_order_id=work_order_id,
            from_status=current_status.value,
            to_status=new_status.value,
            actor=actor,
            reason=status_in.reason,
        )

        await self.audit_repo.log_event(
            entity_type="WorkOrder",
            entity_id=work_order_id,
            action="TRANSITION_STATUS",
            actor_id=status_in.actor_id,
            changes={"from": current_status.value, "to": new_status.value},
            metadata={"reason": status_in.reason},
        )

        # Stage transactional outbox events based on transition
        try:
            cust = await self.customer_repo.get_by_id(current_wo.customer_id)
            if new_status == WorkOrderStatus.COMPLETED and cust:
                phone = (
                    cust.get("phone", "") if isinstance(cust, dict) else getattr(cust, "phone", "")
                )
                email = (
                    cust.get("email", "") if isinstance(cust, dict) else getattr(cust, "email", "")
                )
                pref_chan = (
                    cust.get("preferred_channel", "SMS")
                    if isinstance(cust, dict)
                    else getattr(cust, "preferred_channel", "SMS")
                )
                cust_name = (
                    cust.get("full_name") or cust.get("name")
                    if isinstance(cust, dict)
                    else getattr(cust, "full_name", getattr(cust, "name", "Valued Customer"))
                )
                # 1. Customer notification
                await self.outbox_repo.stage_event(
                    OutboxEventCreate(
                        event_type=OutboxEventType.NOTIFICATION_WORK_ORDER_COMPLETED,
                        aggregate_type="WorkOrder",
                        aggregate_id=work_order_id,
                        payload={
                            "to_phone": phone,
                            "to_email": email,
                            "channel": pref_chan or "SMS",
                            "context": {
                                "customer_name": cust_name,
                                "work_order_number": current_wo.work_order_number,
                                "category": current_wo.category,
                                "completion_notes": status_in.reason
                                or "Service completed successfully.",
                            },
                        },
                        idempotency_key=f"wo_complete_notif_{work_order_id}",
                    )
                )
                # 2. CRM synchronization
                await self.outbox_repo.stage_event(
                    OutboxEventCreate(
                        event_type=OutboxEventType.CRM_SYNC_WORK_ORDER,
                        aggregate_type="WorkOrder",
                        aggregate_id=work_order_id,
                        payload={
                            "internal_work_order_id": work_order_id,
                            "work_order_number": current_wo.work_order_number,
                            "customer_id": current_wo.customer_id,
                            "category": current_wo.category,
                            "priority": current_wo.priority,
                            "status": new_status.value,
                            "description": current_wo.description,
                            "assigned_technician_id": current_wo.assigned_technician_id,
                        },
                        idempotency_key=f"crm_sync_wo_{work_order_id}_completed",
                    )
                )
        except Exception:
            pass

        return WorkOrderResponse(**updated)  # type: ignore

    async def update_work_order(
        self, work_order_id: str, wo_in: WorkOrderUpdate
    ) -> WorkOrderResponse:
        current = await self.get_work_order(work_order_id)
        update_data = wo_in.model_dump(exclude_unset=True)
        if not update_data:
            return current

        updated = await self.work_order_repo.update(work_order_id, update_data)

        await self.audit_repo.log_event(
            entity_type="WorkOrder",
            entity_id=work_order_id,
            action="UPDATE",
            changes=update_data,
        )

        return WorkOrderResponse(**updated)  # type: ignore
