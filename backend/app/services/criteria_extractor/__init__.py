import json
import re
import uuid
from typing import Any

from app.core.config import settings


def create_criterion(text: str, done: bool = False) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "text": text, "done": done}


async def extract_criteria(title: str, description: str | None) -> list[dict]:
    """Return list of {id, text, done} dicts extracted from ticket text via LLM."""
    if not description:
        return []

    prompt = _build_prompt(title, description)

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return await _extract_with_anthropic(prompt)
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return await _extract_with_openai(prompt)

    # Fallback: parse markdown checkboxes from description directly
    return _parse_checkboxes(description)


def _build_prompt(title: str, description: str) -> str:
    return f"""Extract acceptance criteria from this ticket as a JSON array.
Each item: {{"id": "<uuid>", "text": "<criterion>", "done": false}}
Return ONLY valid JSON array, no explanation.

Title: {title}
Description: {description}"""


async def _extract_with_anthropic(prompt: str) -> list[dict]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text
    criteria = json.loads(_extract_json(raw))
    for c in criteria:
        if not c.get("id"):
            c["id"] = str(uuid.uuid4())
        c.setdefault("done", False)
    return criteria


async def _extract_with_openai(prompt: str) -> list[dict]:
    import openai

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    raw = response.choices[0].message.content
    criteria = json.loads(_extract_json(raw))
    for c in criteria:
        if not c.get("id"):
            c["id"] = str(uuid.uuid4())
        c.setdefault("done", False)
    return criteria


def _extract_json(text: str) -> str:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in LLM response: {text[:200]}")
    return match.group(0)


def _parse_checkboxes(description: str) -> list[dict]:
    criteria = []
    for line in description.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            done = stripped.startswith("- [x]")
            criteria.append(create_criterion(stripped[5:].strip(), done))
    return criteria
