from fastapi import APIRouter

from app.api.routes import agents, events, fs, init, tickets, workspaces

api_router = APIRouter()
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(init.router, prefix="/init", tags=["init"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(fs.router, prefix="/fs", tags=["fs"])
