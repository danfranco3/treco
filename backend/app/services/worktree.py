"""Git worktree isolation — one worktree + branch per ticket run.

Worktrees live under ~/.treco/worktrees so a runaway agent command can only
damage its own copy, never the shared workspace repo.
"""
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WORKTREES_ROOT = Path.home() / ".treco" / "worktrees"


class WorktreeError(RuntimeError):
    pass


async def _git(repo_path: str, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", repo_path, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace").strip()
    if proc.returncode != 0:
        raise WorktreeError(f"git {' '.join(args)} failed: {output[:500]}")
    return output


async def is_git_repo(repo_path: str) -> bool:
    try:
        await _git(repo_path, "rev-parse", "--git-dir")
        return True
    except (WorktreeError, FileNotFoundError):
        return False


async def create_worktree(repo_path: str, ticket_id: str) -> tuple[str, str]:
    """Create (or reuse) a worktree for this ticket. Returns (path, branch)."""
    slug = ticket_id[:8]
    branch = f"treco/{slug}"
    path = WORKTREES_ROOT / slug
    if path.exists():
        return str(path), branch
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await _git(repo_path, "worktree", "add", str(path), "-b", branch)
    except WorktreeError:
        # branch survives worktree removal — reattach instead of -b; prune
        # first, or git refuses when the old dir was deleted unregistered
        await _git(repo_path, "worktree", "prune")
        await _git(repo_path, "worktree", "add", str(path), branch)
    return str(path), branch


async def remove_worktree(repo_path: str, worktree_path: str) -> None:
    """Remove a ticket worktree. The branch is kept for PR/merge flows."""
    try:
        await _git(repo_path, "worktree", "remove", "--force", worktree_path)
    except WorktreeError as e:
        logger.warning("Worktree cleanup failed for %s: %s", worktree_path, e)
