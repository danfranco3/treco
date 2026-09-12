from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class DemoModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.demo_mode and request.method in MUTATING_METHODS:
            from app.services.telemetry import record_metric
            await record_metric(
                "global", "demo_mode_block", 1, "count",
                dims={"method": request.method, "path": request.url.path},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "This is a read-only demo instance."},
            )
        return await call_next(request)
