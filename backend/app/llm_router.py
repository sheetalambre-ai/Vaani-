"""LLMRouter: Groq → Gemini → OpenRouter with fallback on 429/errors."""
import json
import httpx
from urllib.parse import urlsplit
from typing import Any
from app.config import settings
from app.provider_http import provider_post


class LLMError(Exception):
    pass


def _provider_error(response: httpx.Response, provider: str, secret: str = "") -> LLMError:
    """Summarize provider failures without leaking request URLs or credentials."""
    message = ""
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        pass
    if secret:
        message = message.replace(secret, "[redacted]")
    message = " ".join(message.split())[:240]
    detail = f"{provider} returned HTTP {response.status_code}"
    return LLMError(f"{detail}: {message}" if message else detail)


async def _call_openai_compat(base_url: str, api_key: str, model: str, messages: list, extra_headers: dict = {}) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
    payload = {"model": model, "messages": messages, "response_format": {"type": "json_object"}, "temperature": 0.1}
    resp = await provider_post(f"{base_url}/chat/completions", json=payload, headers=headers)
    if resp.status_code == 429:
        raise LLMError("rate_limited")
    if not resp.is_success:
        provider = urlsplit(base_url).hostname or "LLM provider"
        raise _provider_error(resp, provider, api_key)
    return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini(messages: list, model: str) -> str:
    # Gemini separates system instructions from role-tagged conversation turns.
    system_text = "\n\n".join(
        m["content"] for m in messages if m.get("role") in {"system", "developer"}
    )
    contents = [
        {"role": "model" if m.get("role") == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages if m.get("role") not in {"system", "developer"}
    ]
    payload = {
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
    resp = await provider_post(url, json=payload, headers={"x-goog-api-key": settings.GEMINI_API_KEY})
    if resp.status_code == 429:
        raise LLMError("rate_limited")
    if not resp.is_success:
        raise _provider_error(resp, "Gemini", settings.GEMINI_API_KEY)
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

    failures = []
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
                failures.append(f"{name}: {e}")
                break  # try next provider
            except Exception as e:
                failures.append(f"{name}: {type(e).__name__}")
                if attempt == retries - 1:
                    break

    raise LLMError("All LLM providers failed. " + "; ".join(failures))
