from fastapi import APIRouter

from app.api.routes import (
    agents,
    events,
    init,
    integrations,
    meta,
    telemetry,
    tickets,
    tools,
    traces,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(init.router, prefix="/init", tags=["init"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(traces.router, prefix="/traces", tags=["traces"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
