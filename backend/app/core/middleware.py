import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextvars import ContextVar
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return request_id_ctx_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_ctx_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx_var.reset(token)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int, excluded_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.excluded_paths = excluded_paths or set()
        self._history: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        request_id = get_request_id() or request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client_host = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60

        with self._lock:
            hits = self._history[client_host]
            while hits and hits[0] < window_start:
                hits.popleft()

            if len(hits) >= self.requests_per_minute:
                retry_after = int(max(1, 60 - (now - hits[0])))
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "type": "rate_limit",
                            "message": "Rate limit exceeded",
                            "request_id": request_id,
                        }
                    },
                    headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
                )

            hits.append(now)

        return await call_next(request)
