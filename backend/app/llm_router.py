"""LLMRouter: Groq → Gemini → OpenRouter with fallback on 429/errors."""
import json
import httpx
from typing import Any
from app.config import settings


class LLMError(Exception):
    pass


async def _call_openai_compat(base_url: str, api_key: str, model: str, messages: list, extra_headers: dict = {}) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
    payload = {"model": model, "messages": messages, "response_format": {"type": "json_object"}, "temperature": 0.1}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        if resp.status_code == 429:
            raise LLMError("rate_limited")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini(messages: list, model: str) -> str:
    # Convert OpenAI messages to Gemini format
    parts = []
    for m in messages:
        parts.append({"text": m["content"]})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={settings.GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 429:
            raise LLMError("rate_limited")
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def chat_json(messages: list[dict], retries: int = 2) -> Any:
    """Call LLM, return parsed JSON. Falls back through providers."""
    providers = []

    if settings.GROQ_API_KEY and settings.GROQ_LLM_MODEL:
        providers.append(("groq", lambda: _call_openai_compat(
            "https://api.groq.com/openai/v1", settings.GROQ_API_KEY, settings.GROQ_LLM_MODEL, messages
        )))

    if settings.GEMINI_API_KEY and settings.GEMINI_MODEL:
        providers.append(("gemini", lambda: _call_gemini(messages, settings.GEMINI_MODEL)))

    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_MODEL:
        providers.append(("openrouter", lambda: _call_openai_compat(
            "https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL, messages,
            extra_headers={"HTTP-Referer": "https://vaanimanthan.local"}
        )))

    if not providers:
        raise LLMError("No LLM provider configured. Set GROQ_API_KEY in .env")

    last_error = None
    for name, call_fn in providers:
        for attempt in range(retries):
            try:
                raw = await call_fn()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    # Retry once on invalid JSON
                    if attempt < retries - 1:
                        continue
                    raise LLMError(f"Invalid JSON from {name}: {raw[:200]}")
            except LLMError as e:
                last_error = e
                break  # try next provider
            except Exception as e:
                last_error = e
                if attempt == retries - 1:
                    break

    raise LLMError(f"All LLM providers failed. Last error: {last_error}")
