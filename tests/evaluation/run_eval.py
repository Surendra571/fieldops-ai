import asyncio
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from typing import Any

sys.path.insert(0, os.path.abspath("."))

from app.agent.tools import AgentToolRegistry
from app.integrations.llm.mock_llm import MockLLMAdapter
from app.integrations.voice.mock_voice import MockSTTAdapter, MockTTSAdapter
from app.repositories.conversation_repo import ConversationRepository
from app.services.agent_service import AgentService
from tests.evaluation.eval_dataset import EVALUATION_DATASET


class MockMongoCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if "session_id" in query:
            return self.docs.get(query["session_id"])
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    async def insert_one(self, doc: dict[str, Any]) -> Any:
        self.docs[doc["session_id"]] = dict(doc)
        return type("Res", (), {"inserted_id": doc["session_id"]})()

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> Any:
        doc = await self.find_one(query)
        if not doc:
            return None
        if "$set" in update:
            doc.update(update["$set"])
        if "$push" in update:
            for k, push_item in update["$push"].items():
                if k not in doc:
                    doc[k] = []
                if isinstance(push_item, dict) and "$each" in push_item:
                    doc[k].extend(push_item["$each"])
                else:
                    doc[k].append(push_item)
        return None


class MockDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, MockMongoCollection] = {}

    def __getitem__(self, name: str) -> MockMongoCollection:
        if name not in self.collections:
            self.collections[name] = MockMongoCollection()
        return self.collections[name]


class MockCustomerService:
    def __init__(self) -> None:
        self.customers: dict[str, dict[str, Any]] = {}
        self.customer_repo = type(
            "Repo",
            (),
            {
                "get_by_phone": self._get_by_phone,
            },
        )()

    async def _get_by_phone(self, phone: str) -> dict[str, Any] | None:
        return self.customers.get(phone)

    async def create_customer(self, cust_in: Any) -> Any:
        cid = f"cust_{len(self.customers) + 1}"
        doc = {"id": cid, "phone": cust_in.phone, "full_name": cust_in.full_name}
        self.customers[cust_in.phone] = doc
        return type("CustRes", (), {"id": cid})()


class MockWorkOrderService:
    def __init__(self) -> None:
        self.work_orders: dict[str, dict[str, Any]] = {}
        self.work_order_repo = type(
            "Repo",
            (),
            {
                "get_by_id": self._get_by_id,
                "_serialize_doc": lambda doc: doc,
                "collection": type("Col", (), {"find_one": self._find_wo_doc})(),
            },
        )()

    async def _get_by_id(self, w_id: str) -> dict[str, Any] | None:
        return self.work_orders.get(w_id)

    async def _find_wo_doc(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for wo in self.work_orders.values():
            if all(wo.get(k) == v for k, v in query.items()):
                return wo
        return None

    async def create_work_order(self, wo_in: Any) -> Any:
        wo_id = f"wo_{len(self.work_orders) + 1}"
        wo_num = f"WO-2026-{1000 + len(self.work_orders)}"
        doc = {
            "id": wo_id,
            "work_order_number": wo_num,
            "status": "SUBMITTED",
            "category": str(wo_in.category),
            "priority": str(wo_in.priority),
        }
        self.work_orders[wo_id] = doc
        return type("WORes", (), doc)()


class MockAppointmentService:
    def __init__(self) -> None:
        self.appointment_repo = type("Repo", (), {"find_by_work_order": self._find_by_wo})()

    async def _find_by_wo(self, wo_id: str) -> list[dict[str, Any]]:
        return []

    async def get_available_slots(self, req: Any) -> Any:
        slot = type(
            "Slot",
            (),
            {
                "slot_id": "slot_1",
                "technician_id": "tech_1",
                "technician_name": "Dave Miller",
                "start_time": datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
                "end_time": datetime(2026, 10, 15, 10, 30, tzinfo=UTC),
            },
        )()
        return type("SlotsRes", (), {"available_slots": [slot]})()

    async def hold_slot(self, req: Any) -> Any:
        return type(
            "HoldRes",
            (),
            {
                "reservation_token": "token_123",
                "expires_at": datetime(2026, 10, 15, 9, 15, tzinfo=UTC),
            },
        )()

    async def confirm_booking(self, req: Any) -> Any:
        if not req.user_confirmed:
            raise ValueError("Confirmation required")
        return type(
            "ApptRes",
            (),
            {
                "id": "appt_1",
                "appointment_number": "APT-2026-1234",
                "status": "CONFIRMED",
                "scheduled_start": type("DT", (), {"isoformat": lambda: "2026-10-15T09:00:00Z"})(),
                "scheduled_end": type("DT", (), {"isoformat": lambda: "2026-10-15T10:30:00Z"})(),
            },
        )()

    async def reschedule_appointment(self, appt_id: str, req: Any) -> Any:
        return type(
            "ReschedRes",
            (),
            {
                "id": appt_id,
                "status": "RESCHEDULED",
                "scheduled_start": req.new_scheduled_start,
                "scheduled_end": req.new_scheduled_end,
            },
        )()


class MockDispatchService:
    async def match_candidates(self, req: Any) -> Any:
        cand = type(
            "Cand",
            (),
            {
                "technician_id": "tech_1",
                "technician_name": "Dave Miller",
                "overall_score": 0.92,
                "explanation": "Skilled and available in local service zone",
            },
        )()
        return type("MatchRes", (), {"candidates": [cand]})()


async def run_evaluation() -> dict[str, Any]:
    print("================================================================================")
    print("                    FIELDOPS AI - PHASE 4 EVALUATION BENCHMARK                  ")
    print("================================================================================")

    # Setup isolated test harness
    mock_db = MockDatabase()
    conv_repo = ConversationRepository(mock_db)  # type: ignore

    cust_svc = MockCustomerService()
    wo_svc = MockWorkOrderService()
    appt_svc = MockAppointmentService()
    disp_svc = MockDispatchService()

    tool_registry = AgentToolRegistry(
        customer_service=cust_svc,
        work_order_service=wo_svc,
        appointment_service=appt_svc,
        dispatch_service=disp_svc,
    )

    llm_adapter = MockLLMAdapter()
    stt_adapter = MockSTTAdapter()
    tts_adapter = MockTTSAdapter()

    agent_service = AgentService(
        conversation_repo=conv_repo,
        tool_registry=tool_registry,
        llm_adapter=llm_adapter,
        stt_adapter=stt_adapter,
        tts_adapter=tts_adapter,
    )

    total_scenarios = len(EVALUATION_DATASET)
    extraction_matches = 0
    completeness_scores = []
    tool_correctness_matches = 0
    tasks_completed = 0
    escalations_count = 0
    latencies_ms = []

    print(f"\nRunning {total_scenarios} evaluation benchmark scenarios...\n")

    for idx, scenario in enumerate(EVALUATION_DATASET, 1):
        session_id = f"eval_session_{scenario.id}"
        tools_called_in_scenario: list[str] = []
        last_resp = None
        turn_latencies = []

        for user_msg in scenario.user_inputs:
            start_time = time.perf_counter()
            resp = await agent_service.process_chat(
                session_id=session_id,
                customer_id=None,
                user_message=user_msg,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            turn_latencies.append(elapsed_ms)
            latencies_ms.append(elapsed_ms)
            tools_called_in_scenario.extend(resp.tools_invoked)
            last_resp = resp

        # 1. Extraction Accuracy
        draft = last_resp.extracted_draft if last_resp else None
        extracted_cat = draft.issue_category.value if (draft and draft.issue_category) else None
        has_addr = bool(draft and draft.service_address.value)

        cat_correct = (scenario.expected_issue_category is None) or (
            extracted_cat and scenario.expected_issue_category.lower() in extracted_cat.lower()
        )
        addr_correct = has_addr == scenario.expected_has_address

        if cat_correct and addr_correct:
            extraction_matches += 1
            extraction_status = "[PASS]"
        else:
            extraction_status = f"[FAIL: cat='{extracted_cat}' exp='{scenario.expected_issue_category}', addr={has_addr} exp={scenario.expected_has_address}]"

        # 2. Completeness Score
        completeness = draft.completeness_score if draft else 0.0
        completeness_scores.append(completeness)

        # 3. Tool Call Correctness
        expected_tools = set(scenario.expected_tool_calls)
        actual_tools = set(tools_called_in_scenario)
        tool_correct = expected_tools.issubset(actual_tools)
        if tool_correct:
            tool_correctness_matches += 1
            tool_status = "[PASS]"
        else:
            tool_status = "[FAIL]"

        # 4. Escalation
        if last_resp and last_resp.is_escalated:
            escalations_count += 1

        # 5. Task completion
        if scenario.expected_escalated:
            task_done = last_resp.is_escalated if last_resp else False
        elif scenario.expected_tool_calls:
            task_done = bool(actual_tools)
        else:
            task_done = bool(last_resp and last_resp.reply)

        if task_done:
            tasks_completed += 1

        avg_turn_ms = statistics.mean(turn_latencies) if turn_latencies else 0.0
        print(
            f"{idx:02d}. [{scenario.scenario_type.upper():<18}] {scenario.id:<12} | "
            f"Extraction: {extraction_status} | Tool: {tool_status} | "
            f"Completeness: {completeness:.0%} | Latency: {avg_turn_ms:.1f}ms"
        )

    # Metrics Summary
    extraction_accuracy = (extraction_matches / total_scenarios) * 100.0
    avg_completeness = (
        statistics.mean(completeness_scores) if completeness_scores else 0.0
    ) * 100.0
    tool_accuracy = (tool_correctness_matches / total_scenarios) * 100.0
    task_completion_rate = (tasks_completed / total_scenarios) * 100.0
    escalation_rate = (escalations_count / total_scenarios) * 100.0
    sorted_lats = sorted(latencies_ms) if latencies_ms else [0.0]
    p50_latency = sorted_lats[int(len(sorted_lats) * 0.50)]
    p95_latency = sorted_lats[min(int(len(sorted_lats) * 0.95), len(sorted_lats) - 1)]
    avg_latency = statistics.mean(latencies_ms) if latencies_ms else 0.0

    print("\n================================================================================")
    print("                             BENCHMARK RESULTS SUMMARY                          ")
    print("================================================================================")
    print(f"Total Scenarios Evaluated       : {total_scenarios}")
    print(f"Extraction Accuracy             : {extraction_accuracy:.1f}%")
    print(f"Required-Field Completeness     : {avg_completeness:.1f}%")
    print(f"Tool-Call Correctness           : {tool_accuracy:.1f}%")
    print(f"Task Completion Rate            : {task_completion_rate:.1f}%")
    print(
        f"Escalation Rate                 : {escalation_rate:.1f}% ({escalations_count}/{total_scenarios})"
    )
    print(f"Latency Avg                     : {avg_latency:.2f} ms")
    print(f"Latency P50                     : {p50_latency:.2f} ms")
    print(f"Latency P95                     : {p95_latency:.2f} ms")
    print("================================================================================\n")

    return {
        "total_scenarios": total_scenarios,
        "extraction_accuracy": extraction_accuracy,
        "required_field_completeness": avg_completeness,
        "tool_call_correctness": tool_accuracy,
        "task_completion_rate": task_completion_rate,
        "escalation_rate": escalation_rate,
        "latency_avg_ms": avg_latency,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
    }


if __name__ == "__main__":
    asyncio.run(run_evaluation())
