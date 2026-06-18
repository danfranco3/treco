"""Unit tests for auth service: key generation and agent resolution."""
import hashlib
import secrets
import uuid

import pytest
from fastapi import HTTPException

from app.models.agent import Agent
from app.services.auth import generate_api_key, resolve_agent
from tests.shared import TestSessionLocal


class TestGenerateApiKey:
    def test_returns_tuple(self):
        result = generate_api_key()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_raw_key_has_prefix(self):
        raw_key, _ = generate_api_key()
        assert raw_key.startswith("treco_")

    def test_hash_is_sha256_of_raw(self):
        raw_key, key_hash = generate_api_key()
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        assert key_hash == expected

    def test_hash_length_is_64(self):
        _, key_hash = generate_api_key()
        assert len(key_hash) == 64

    def test_keys_are_unique(self):
        keys = {generate_api_key()[0] for _ in range(20)}
        assert len(keys) == 20

    def test_raw_key_is_not_hash(self):
        raw_key, key_hash = generate_api_key()
        assert raw_key != key_hash


class TestResolveAgent:
    @pytest.mark.asyncio
    async def test_resolves_agent_by_raw_key(self):
        raw_key = "treco_" + secrets.token_urlsafe(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        agent_id = str(uuid.uuid4())

        async with TestSessionLocal() as db:
            agent = Agent(
                id=agent_id,
                workspace_id="ws1",
                name="test-agent",
                api_key_hash=key_hash,
                status="idle",
            )
            db.add(agent)
            await db.commit()

            resolved = await resolve_agent(raw_key, db)
            assert resolved.id == agent_id

    @pytest.mark.asyncio
    async def test_raises_401_for_unknown_key(self):
        async with TestSessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                await resolve_agent("treco_totally_bogus_key_xyz", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_for_hash_passed_as_key(self):
        raw_key = "treco_" + secrets.token_urlsafe(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        async with TestSessionLocal() as db:
            db.add(Agent(
                id=str(uuid.uuid4()),
                workspace_id="ws1",
                name="hash-agent",
                api_key_hash=key_hash,
                status="idle",
            ))
            await db.commit()

            # passing the hash directly should NOT resolve (hash of hash != hash)
            with pytest.raises(HTTPException) as exc_info:
                await resolve_agent(key_hash, db)
        assert exc_info.value.status_code == 401
