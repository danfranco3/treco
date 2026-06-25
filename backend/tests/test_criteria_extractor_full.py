"""Tests for criteria_extractor: LLM paths, normalize, extract_json, fallback."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.criteria_extractor import (
    _build_prompt,
    _extract_json,
    _normalize_criteria,
    _parse_checkboxes,
    create_criterion,
    extract_criteria,
)


class TestCreateCriterion:
    def test_has_all_fields(self):
        c = create_criterion("Do the thing")
        assert c["text"] == "Do the thing"
        assert c["done"] is False
        assert "id" in c

    def test_done_flag_respected(self):
        c = create_criterion("Step", done=True)
        assert c["done"] is True

    def test_id_is_valid_uuid(self):
        c = create_criterion("X")
        uuid.UUID(c["id"])  # raises if invalid


class TestBuildPrompt:
    def test_contains_title_and_description(self):
        p = _build_prompt("Fix login", "Users can't log in on mobile")
        assert "Fix login" in p
        assert "Users can't log in on mobile" in p


class TestExtractJson:
    def test_extracts_array_from_text(self):
        text = 'Here is the result: [{"id": "1", "text": "Do X", "done": false}] done.'
        result = _extract_json(text)
        assert result.startswith("[")
        assert "Do X" in result

    def test_raises_on_no_array(self):
        with pytest.raises(ValueError, match="No JSON array"):
            _extract_json("No array here, just text.")

    def test_handles_multiline_array(self):
        text = '[\n  {"id": "1", "text": "A", "done": false}\n]'
        result = _extract_json(text)
        assert json.loads(result)[0]["text"] == "A"


class TestNormalizeCriteria:
    def test_adds_missing_ids(self):
        raw = json.dumps([{"text": "Do X", "done": False}])
        result = _normalize_criteria(raw)
        assert "id" in result[0]
        uuid.UUID(result[0]["id"])

    def test_preserves_existing_ids(self):
        existing_id = str(uuid.uuid4())
        raw = json.dumps([{"id": existing_id, "text": "Do X", "done": False}])
        result = _normalize_criteria(raw)
        assert result[0]["id"] == existing_id

    def test_adds_done_default(self):
        raw = json.dumps([{"id": str(uuid.uuid4()), "text": "X"}])
        result = _normalize_criteria(raw)
        assert result[0]["done"] is False

    def test_empty_array(self):
        assert _normalize_criteria("[]") == []


class TestExtractCriteria:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_description(self):
        result = await extract_criteria("My ticket", None)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_empty_description(self):
        result = await extract_criteria("My ticket", "")
        assert result == []

    @pytest.mark.asyncio
    async def test_falls_back_to_checkboxes_on_llm_error(self):
        desc = "- [ ] Step one\n- [ ] Step two"
        with patch("app.services.criteria_extractor.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "fake-key"
            with patch(
                "app.services.criteria_extractor._extract_with_anthropic",
                side_effect=Exception("LLM down"),
            ):
                result = await extract_criteria("Title", desc)
        assert len(result) == 2
        assert result[0]["text"] == "Step one"

    @pytest.mark.asyncio
    async def test_uses_anthropic_when_configured(self):
        fake_criteria = [{"id": str(uuid.uuid4()), "text": "Criterion A", "done": False}]
        with patch("app.services.criteria_extractor.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = "fake-key"
            with patch(
                "app.services.criteria_extractor._extract_with_anthropic",
                new_callable=AsyncMock,
                return_value=fake_criteria,
            ):
                result = await extract_criteria("Title", "Some description")
        assert result == fake_criteria

    @pytest.mark.asyncio
    async def test_uses_openai_when_configured(self):
        fake_criteria = [{"id": str(uuid.uuid4()), "text": "Criterion B", "done": False}]
        with patch("app.services.criteria_extractor.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = "fake-openai-key"
            mock_settings.anthropic_api_key = None
            with patch(
                "app.services.criteria_extractor._extract_with_openai",
                new_callable=AsyncMock,
                return_value=fake_criteria,
            ):
                result = await extract_criteria("Title", "Some description")
        assert result == fake_criteria

    @pytest.mark.asyncio
    async def test_falls_back_to_checkboxes_when_no_llm_configured(self):
        desc = "- [ ] Must work\n- [x] Already done"
        with patch("app.services.criteria_extractor.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = None
            result = await extract_criteria("Title", desc)
        assert len(result) == 2
        assert result[1]["done"] is True
