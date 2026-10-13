"""
FieldOps AI — Production Load Testing & Performance Benchmark Suite
Stated Target Concurrency: 20 concurrent workers
Target Request Volume: 500 requests across realistic operational mix

Measures:
- Latency percentiles: Min, Average, P50, P90, P95, P99, Max
- Throughput (requests / second)
- HTTP Status Code breakdown & Error Rate (%)
- Resource / Latency bottlenecks
"""

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


@dataclass
class RequestResult:
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    error: str | None = None


@dataclass
class LoadTestSummary:
    target_concurrency: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    throughput_rps: float
    error_rate_pct: float
    latencies_ms: dict[str, float] = field(default_factory=dict)
    endpoint_breakdown: dict[str, Any] = field(default_factory=dict)
    status_code_counts: dict[int, int] = field(default_factory=dict)


# Realistic payload generators
def generate_duration_payload() -> dict[str, Any]:
    categories = ["HVAC", "PLUMBING", "ELECTRICAL", "APPLIANCE"]
    return {
        "category": random.choice(categories),
        "equipment_type": "Carrier 3-Ton Heat Pump",
        "equipment_age_years": round(random.uniform(1.0, 15.0), 1),
        "urgency": random.choice(["ROUTINE", "HIGH", "EMERGENCY"]),
        "technician_experience_years": round(random.uniform(1.0, 10.0), 1),
        "technician_active_jobs_count": random.randint(0, 4),
        "historical_jobs_completed": random.randint(5, 50),
        "distance_km": round(random.uniform(2.0, 35.0), 1),
        "estimated_duration_minutes": random.choice([45, 60, 90, 120]),
    }


def generate_risk_payload() -> dict[str, Any]:
    return {
        "category": random.choice(["HVAC", "PLUMBING", "ELECTRICAL"]),
        "customer_total_jobs": random.randint(1, 10),
        "customer_no_show_history_count": random.choice([0, 0, 0, 1, 2]),
        "scheduled_hour_of_day": random.randint(8, 18),
        "scheduled_day_of_week": random.randint(0, 6),
        "travel_distance_km": round(random.uniform(3.0, 40.0), 1),
        "technician_experience_years": round(random.uniform(1.0, 12.0), 1),
        "urgency": random.choice(["ROUTINE", "HIGH"]),
        "lead_time_hours": round(random.uniform(2.0, 72.0), 1),
    }


async def execute_task(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    endpoint_type: str,
) -> RequestResult:
    start = time.perf_counter()
    endpoint = ""
    method = "GET"
    status_code = 0
    err_msg = None

    try:
        if endpoint_type == "health":
            endpoint = "/api/v1/health"
            res = await client.get(f"{base_url}{endpoint}")
            status_code = res.status_code
        elif endpoint_type == "ready":
            endpoint = "/api/v1/ready"
            res = await client.get(f"{base_url}{endpoint}")
            status_code = res.status_code
        elif endpoint_type == "metrics":
            endpoint = "/api/v1/metrics"
            res = await client.get(f"{base_url}{endpoint}")
            status_code = res.status_code
        elif endpoint_type == "work_orders":
            endpoint = "/api/v1/work-orders?page=1&page_size=10"
            res = await client.get(f"{base_url}{endpoint}", headers=headers)
            status_code = res.status_code
        elif endpoint_type == "technicians":
            endpoint = "/api/v1/technicians?page=1&page_size=10"
            res = await client.get(f"{base_url}{endpoint}", headers=headers)
            status_code = res.status_code
        elif endpoint_type == "ml_duration":
            endpoint = "/api/v1/ml/predict/duration"
            method = "POST"
            res = await client.post(
                f"{base_url}{endpoint}",
                headers=headers,
                json=generate_duration_payload(),
            )
            status_code = res.status_code
        elif endpoint_type == "ml_risk":
            endpoint = "/api/v1/ml/predict/risk"
            method = "POST"
            res = await client.post(
                f"{base_url}{endpoint}",
                headers=headers,
                json=generate_risk_payload(),
            )
            status_code = res.status_code
        elif endpoint_type == "ml_drift":
            endpoint = "/api/v1/ml/monitoring/drift"
            res = await client.get(f"{base_url}{endpoint}", headers=headers)
            status_code = res.status_code
        else:
            endpoint = "/api/v1/health"
            res = await client.get(f"{base_url}{endpoint}")
            status_code = res.status_code
    except Exception as exc:
        err_msg = str(exc)

    latency_ms = (time.perf_counter() - start) * 1000.0
    return RequestResult(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        latency_ms=latency_ms,
        error=err_msg,
    )


async def run_load_test(
    base_url: str = "http://localhost:8000",
    concurrency: int = 20,
    total_requests: int = 500,
    client: httpx.AsyncClient | None = None,
    auth_token: str | None = None,
) -> LoadTestSummary:
    """
    Executes concurrent load test with weighted operational request mix:
    - Health / Readiness Probes: 15%
    - Operational Metrics: 10%
    - Work Orders Retrieval: 25%
    - Technician Roster: 15%
    - ML Duration Prediction: 20%
    - ML Risk Prediction & Drift: 15%
    """
    request_pool = (
        ["health"] * 10
        + ["ready"] * 5
        + ["metrics"] * 10
        + ["work_orders"] * 25
        + ["technicians"] * 15
        + ["ml_duration"] * 20
        + ["ml_risk"] * 10
        + ["ml_drift"] * 5
    )

    # Prepare auth header
    if not auth_token:
        from app.core.security import create_access_token

        auth_token = create_access_token(subject="perf-tester-id", role="DISPATCHER")
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    # Distribute tasks
    task_types = [random.choice(request_pool) for _ in range(total_requests)]
    queue: asyncio.Queue = asyncio.Queue()
    for t in task_types:
        queue.put_nowait(t)

    results: list[RequestResult] = []
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=15.0)

    start_wall = time.perf_counter()

    async def worker():
        while not queue.empty():
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            res = await execute_task(client, base_url, headers, item)
            results.append(res)
            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)

    duration = time.perf_counter() - start_wall
    if own_client:
        await client.aclose()

    # Calculate statistics
    successful = [r for r in results if 200 <= r.status_code < 400]
    failed = [r for r in results if r.status_code >= 400 or r.error is not None]
    latencies = sorted([r.latency_ms for r in results])
    n = len(latencies)

    status_counts: dict[int, int] = {}
    for r in results:
        status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1

    endpoint_stats: dict[str, dict[str, Any]] = {}
    for r in results:
        ep = r.endpoint.split("?")[0]
        if ep not in endpoint_stats:
            endpoint_stats[ep] = {"count": 0, "errors": 0, "latencies": []}
        endpoint_stats[ep]["count"] += 1
        endpoint_stats[ep]["latencies"].append(r.latency_ms)
        if r.status_code >= 400 or r.error:
            endpoint_stats[ep]["errors"] += 1

    summary = LoadTestSummary(
        target_concurrency=concurrency,
        total_requests=len(results),
        successful_requests=len(successful),
        failed_requests=len(failed),
        duration_seconds=round(duration, 3),
        throughput_rps=round(len(results) / duration, 1) if duration > 0 else 0.0,
        error_rate_pct=round(len(failed) / len(results) * 100.0, 2) if results else 0.0,
        latencies_ms={
            "min": round(latencies[0], 2) if n else 0.0,
            "avg": round(sum(latencies) / n, 2) if n else 0.0,
            "p50": round(latencies[int(n * 0.50)], 2) if n else 0.0,
            "p90": round(latencies[int(n * 0.90)], 2) if n else 0.0,
            "p95": round(latencies[int(n * 0.95)], 2) if n else 0.0,
            "p99": round(latencies[min(int(n * 0.99), n - 1)], 2) if n else 0.0,
            "max": round(latencies[-1], 2) if n else 0.0,
        },
        status_code_counts=status_counts,
        endpoint_breakdown={
            ep: {
                "requests": data["count"],
                "errors": data["errors"],
                "avg_latency_ms": round(sum(data["latencies"]) / len(data["latencies"]), 2),
                "p95_latency_ms": round(
                    sorted(data["latencies"])[int(len(data["latencies"]) * 0.95)], 2
                )
                if data["latencies"]
                else 0.0,
            }
            for ep, data in endpoint_stats.items()
        },
    )
    return summary


def print_report(summary: LoadTestSummary) -> None:
    print("\n" + "=" * 70)
    print("FIELDOPS AI — PRODUCTION LOAD TEST RESULTS")
    print("=" * 70)
    print(f"Target Concurrency:      {summary.target_concurrency} concurrent workers")
    print(f"Total Requests:          {summary.total_requests}")
    print(f"Successful Requests:     {summary.successful_requests}")
    print(f"Failed Requests:         {summary.failed_requests}")
    print(f"Total Duration:          {summary.duration_seconds:.2f} seconds")
    print(f"Throughput:              {summary.throughput_rps:.1f} req/sec")
    print(f"Error Rate:              {summary.error_rate_pct:.2f}%")
    print("-" * 70)
    print("LATENCY PERCENTILES (ms):")
    print(f"  Min:  {summary.latencies_ms.get('min'):.2f} ms")
    print(f"  Avg:  {summary.latencies_ms.get('avg'):.2f} ms")
    print(f"  P50:  {summary.latencies_ms.get('p50'):.2f} ms")
    print(f"  P90:  {summary.latencies_ms.get('p90'):.2f} ms")
    print(f"  P95:  {summary.latencies_ms.get('p95'):.2f} ms")
    print(f"  P99:  {summary.latencies_ms.get('p99'):.2f} ms")
    print(f"  Max:  {summary.latencies_ms.get('max'):.2f} ms")
    print("-" * 70)
    print("STATUS CODES:")
    for code, count in sorted(summary.status_code_counts.items()):
        print(f"  HTTP {code}: {count} requests ({count / summary.total_requests * 100:.1f}%)")
    print("-" * 70)
    print(f"{'ENDPOINT':<35} {'REQS':<8} {'ERR':<6} {'AVG (ms)':<10} {'P95 (ms)'}")
    for ep, data in summary.endpoint_breakdown.items():
        print(
            f"{ep:<35} {data['requests']:<8} {data['errors']:<6} {data['avg_latency_ms']:<10.2f} {data['p95_latency_ms']:.2f}"
        )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FieldOps AI Load Testing")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=500, help="Total requests")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument(
        "--inprocess", action="store_true", help="Run against in-process ASGI app with test DB"
    )
    parser.add_argument(
        "--disable-rate-limit",
        action="store_true",
        help="Disable rate limiting to test raw system capacity",
    )
    args = parser.parse_args()

    async def _main():
        if args.disable_rate_limit:
            from app.core.config import settings

            settings.RATE_LIMIT_ENABLED = False

        if args.inprocess:
            from datetime import UTC, datetime

            import mongomock
            from mongomock_motor import AsyncMongoMockClient

            from app.core.database import db_manager, get_database
            from app.core.security import hash_password
            from app.main import app
            from app.scripts.init_db import init_indexes

            mongomock.SERVER_VERSION = "7.0.0"
            mock_client = AsyncMongoMockClient()
            db = mock_client["fieldops_loadtest"]
            await init_indexes(db)
            db_manager.client = mock_client
            db_manager.db = db
            app.dependency_overrides[get_database] = lambda: db

            # Seed a dispatcher user
            now = datetime.now(UTC)
            user_doc = {
                "email": "loadtester@fieldops.ai",
                "full_name": "Load Test Runner",
                "hashed_password": hash_password("Pass123!"),
                "role": "DISPATCHER",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            res = await db["users"].insert_one(user_doc)
            user_id = str(res.inserted_id)

            from app.core.security import create_access_token

            auth_token = create_access_token(subject=user_id, role="DISPATCHER")

            from httpx import ASGITransport

            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await run_load_test(
                    base_url="http://test",
                    concurrency=args.concurrency,
                    total_requests=args.requests,
                    client=client,
                    auth_token=auth_token,
                )
        else:
            return await run_load_test(
                base_url=args.url,
                concurrency=args.concurrency,
                total_requests=args.requests,
            )

    summary = asyncio.run(_main())
    if args.json:
        print(json.dumps(summary.__dict__, indent=2))
    else:
        print_report(summary)
