"""Worktree isolation — real git repositories, no mocks.

Each ticket run gets its own worktree under WORKTREES_ROOT on branch
treco/<ticket_id[:8]>; the worktree must never touch the parent repo's
checkout or a sibling ticket's worktree, and the branch must survive both
worktree removal and directory loss.
"""
import shutil
import subprocess
import uuid

import pytest

import app.services.worktree as worktree_mod
from app.services.worktree import (
    WorktreeError,
    create_worktree,
    is_git_repo,
    remove_worktree,
)


def _git(cwd, *args) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


@pytest.fixture(autouse=True)
def worktrees_root(tmp_path, monkeypatch):
    root = tmp_path / "worktrees"
    monkeypatch.setattr(worktree_mod, "WORKTREES_ROOT", root)
    return root


class TestCreateWorktree:
    @pytest.mark.asyncio
    async def test_branch_named_treco_slash_first_8_of_ticket_id(self, repo, worktrees_root):
        ticket_id = str(uuid.uuid4())
        path, branch = await create_worktree(str(repo), ticket_id)
        assert branch == f"treco/{ticket_id[:8]}"
        assert path == str(worktrees_root / ticket_id[:8])
        assert _git(path, "rev-parse", "--abbrev-ref", "HEAD") == branch

    @pytest.mark.asyncio
    async def test_existing_worktree_reused_not_recreated(self, repo):
        ticket_id = str(uuid.uuid4())
        first = await create_worktree(str(repo), ticket_id)
        second = await create_worktree(str(repo), ticket_id)
        assert first == second

    @pytest.mark.asyncio
    async def test_reattaches_after_worktree_dir_removed(self, repo):
        """The branch survives directory loss; a new create must reattach to it."""
        ticket_id = str(uuid.uuid4())
        path, branch = await create_worktree(str(repo), ticket_id)
        (worktree_mod.Path(path) / "work.txt").write_text("wip\n")
        _git(path, "add", ".")
        _git(path, "commit", "-m", "wip")
        wip_sha = _git(path, "rev-parse", "HEAD")

        shutil.rmtree(path)
        path2, branch2 = await create_worktree(str(repo), ticket_id)
        assert (path2, branch2) == (path, branch)
        assert _git(path2, "rev-parse", "HEAD") == wip_sha

    @pytest.mark.asyncio
    async def test_non_git_repo_raises_worktree_error(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(WorktreeError):
            await create_worktree(str(plain), str(uuid.uuid4()))


class TestWorktreeIsolation:
    @pytest.mark.asyncio
    async def test_worktree_changes_do_not_touch_parent_checkout(self, repo):
        ticket_id = str(uuid.uuid4())
        path, _ = await create_worktree(str(repo), ticket_id)

        (worktree_mod.Path(path) / "agent-output.txt").write_text("agent was here\n")
        (worktree_mod.Path(path) / "README.md").write_text("mutated\n")

        assert not (repo / "agent-output.txt").exists()
        assert (repo / "README.md").read_text() == "hello\n"
        assert _git(repo, "status", "--porcelain") == ""

    @pytest.mark.asyncio
    async def test_worktree_commit_does_not_move_parent_head(self, repo):
        parent_head = _git(repo, "rev-parse", "HEAD")
        ticket_id = str(uuid.uuid4())
        path, _ = await create_worktree(str(repo), ticket_id)
        (worktree_mod.Path(path) / "feature.py").write_text("x = 1\n")
        _git(path, "add", ".")
        _git(path, "commit", "-m", "agent commit")
        assert _git(repo, "rev-parse", "HEAD") == parent_head
        assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"

    @pytest.mark.asyncio
    async def test_sibling_ticket_worktrees_are_isolated(self, repo):
        id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
        path_a, _ = await create_worktree(str(repo), id_a)
        path_b, _ = await create_worktree(str(repo), id_b)
        assert path_a != path_b

        (worktree_mod.Path(path_a) / "only-a.txt").write_text("a\n")
        _git(path_a, "add", ".")
        _git(path_a, "commit", "-m", "a's work")

        assert not (worktree_mod.Path(path_b) / "only-a.txt").exists()
        assert _git(path_b, "status", "--porcelain") == ""


class TestRemoveWorktree:
    @pytest.mark.asyncio
    async def test_branch_survives_worktree_removal(self, repo):
        ticket_id = str(uuid.uuid4())
        path, branch = await create_worktree(str(repo), ticket_id)
        await remove_worktree(str(repo), path)
        assert not worktree_mod.Path(path).exists()
        branches = _git(repo, "branch", "--list", branch)
        assert branch in branches

    @pytest.mark.asyncio
    async def test_remove_nonexistent_worktree_does_not_raise(self, repo):
        await remove_worktree(str(repo), "/nonexistent/worktree/path")


class TestIsGitRepo:
    @pytest.mark.asyncio
    async def test_true_for_git_repo(self, repo):
        assert await is_git_repo(str(repo)) is True

    @pytest.mark.asyncio
    async def test_false_for_plain_directory(self, tmp_path):
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        assert await is_git_repo(str(plain)) is False

    @pytest.mark.asyncio
    async def test_false_for_missing_directory(self):
        assert await is_git_repo("/no/such/dir") is False


class TestImplementCreatesWorktree:
    @pytest.mark.asyncio
    async def test_implement_sets_worktree_path_and_branch_on_ticket(
        self, client, repo, worktrees_root, service_sessions, monkeypatch
    ):
        from app.core.config import settings
        from app.models.ticket import Ticket
        from app.models.workspace import Workspace
        from tests.shared import TestSessionLocal

        # No LLM key → the runner errors out immediately after spawn, which is
        # fine: the worktree is created by the route before the runner starts.
        monkeypatch.setattr(settings, "anthropic_api_key", None)

        async with TestSessionLocal() as db:
            db.add(Workspace(id="ws-repo", name="repo-ws", repo_path=str(repo)))
            ticket = Ticket(
                id=str(uuid.uuid4()), workspace_id="ws-repo", source="custom",
                title="Worktree ticket", status="open", body={},
                acceptance_criteria=[],
            )
            db.add(ticket)
            await db.commit()
            ticket_id = ticket.id

        r = await client.post(f"/api/tickets/{ticket_id}/implement", json={
            "method": "anthropic",
        })
        assert r.status_code == 200

        refreshed = (await client.get(f"/api/tickets/{ticket_id}")).json()
        assert refreshed["git_branch"] == f"treco/{ticket_id[:8]}"
        assert refreshed["worktree_path"] == str(worktrees_root / ticket_id[:8])
        assert worktree_mod.Path(refreshed["worktree_path"]).exists()
