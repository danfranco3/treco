from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _require_local(request: Request) -> None:
    host = (request.client.host if request.client else "") or ""
    if host not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="fs endpoints only accessible from localhost")


class DirEntry(BaseModel):
    name: str
    path: str
    is_git_repo: bool


class BrowseResponse(BaseModel):
    path: str
    entries: list[DirEntry]


@router.get("/browse", response_model=BrowseResponse)
async def browse(request: Request, path: str | None = None) -> BrowseResponse:
    _require_local(request)
    target = Path(path) if path else Path.home()
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {target}")

    entries: list[DirEntry] = []
    try:
        children = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {target}")

    for child in children:
        try:
            if not child.is_dir():
                continue
            entries.append(
                DirEntry(
                    name=child.name,
                    path=str(child),
                    is_git_repo=(child / ".git").exists(),
                )
            )
        except PermissionError:
            continue

    return BrowseResponse(path=str(target), entries=entries)
