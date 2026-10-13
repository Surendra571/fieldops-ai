import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import request_id_ctx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Operational Metrics Collector
# ---------------------------------------------------------------------------
class MetricsCollector:
    """Thread-safe in-memory operational metrics collector."""

    def __init__(self, max_latency_samples: int = 1000):
        self.request_count: int = 0
        self.error_count: int = 0
        self.status_counts: dict[int, int] = defaultdict(int)
        self.method_counts: dict[str, int] = defaultdict(int)
        self.path_counts: dict[str, int] = defaultdict(int)
        self.latencies_ms: deque[float] = deque(maxlen=max_latency_samples)

    def record_request(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        self.request_count += 1
        self.status_counts[status_code] += 1
        self.method_counts[method] += 1
        # Normalize path to avoid high cardinality (strip query string)
        base_path = path.split("?")[0]
        self.path_counts[base_path] += 1
        self.latencies_ms.append(latency_ms)
        if status_code >= 400:
            self.error_count += 1

    def get_summary(self) -> dict:
        sorted_latencies = sorted(self.latencies_ms) if self.latencies_ms else [0.0]
        n = len(sorted_latencies)
        p50 = sorted_latencies[int(n * 0.50)] if n else 0.0
        p90 = sorted_latencies[int(n * 0.90)] if n else 0.0
        p95 = sorted_latencies[int(n * 0.95)] if n else 0.0
        p99 = sorted_latencies[min(int(n * 0.99), n - 1)] if n else 0.0
        avg = (sum(sorted_latencies) / n) if n else 0.0

        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate_pct": round((self.error_count / self.request_count * 100), 2)
            if self.request_count > 0
            else 0.0,
            "latency_ms": {
                "avg": round(avg, 2),
                "p50": round(p50, 2),
                "p90": round(p90, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
                "samples": n,
            },
            "status_breakdown": dict(self.status_counts),
            "top_paths": sorted(self.path_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        }


metrics_collector = MetricsCollector()


# ---------------------------------------------------------------------------
# 2. Request ID & Correlation Middleware
# ---------------------------------------------------------------------------
class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Extracts or generates an X-Request-ID correlation identifier,
    propagates it into contextvars for structured logging, and attaches
    it to all HTTP response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or f"req_{uuid.uuid4().hex[:12]}"
        )
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# 3. Request Latency & Observability Middleware
# ---------------------------------------------------------------------------
class RequestLatencyMiddleware(BaseHTTPMiddleware):
    """
    Measures request latency, attaches X-Process-Time-Ms header,
    updates operational metrics, and logs access entries.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        metrics_collector.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=duration_ms,
        )

        # Log request completion (suppress noisy health polling from spamming logs)
        if not (request.url.path.endswith("/health") or request.url.path.endswith("/ready")):
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} - {duration_ms:.2f}ms"
            )

        return response


# ---------------------------------------------------------------------------
# 4. In-Memory Sliding-Window Rate Limiting Middleware
# ---------------------------------------------------------------------------
class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window in-memory rate limiter per client IP.
    Returns standard RFC 7807 Problem Details HTTP 429 when rate is exceeded.
    """

    EXEMPT_PATHS = {
        "/api/v1/health",
        "/api/v1/ready",
        "/health",
        "/ready",
        "/metrics",
        "/api/v1/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # In-memory sliding window timestamps: client_ip -> deque of timestamps
    requests: dict[str, deque[float]] = defaultdict(deque)

    @classmethod
    def reset(cls) -> None:
        cls.requests.clear()

    def __init__(self, app):
        super().__init__(app)
        self.window_seconds: int = 60

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        client_history = self.requests[client_ip]

        # Purge timestamps outside the 60s sliding window
        while client_history and client_history[0] <= now - self.window_seconds:
            client_history.popleft()

        limit = settings.RATE_LIMIT_PER_MINUTE
        if len(client_history) >= limit:
            retry_after = max(1, int(self.window_seconds - (now - client_history[0])))
            logger.warning(
                "Rate limit exceeded for IP %s on %s (%d requests in 60s)",
                client_ip,
                request.url.path,
                len(client_history),
            )
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://errors.fieldops.ai/rate-limit-exceeded",
                    "title": "Rate Limit Exceeded",
                    "status": 429,
                    "detail": f"Rate limit of {limit} requests per minute exceeded. Try again in {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        client_history.append(now)
        return await call_next(request)
