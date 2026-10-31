"""MemoryAgent: embeds decisions and retrieves top-N similar past decisions."""
import numpy as np
from typing import Optional
from app.config import settings
from app import models


async def embed_text(text: str) -> list[float]:
    """Embed using Gemini when configured; retrieval falls back to TF-IDF on failure."""
    if settings.GEMINI_API_KEY and settings.GEMINI_EMBED_MODEL:
        try:
            return await _gemini_embed(text)
        except Exception:
            return []
    return []  # empty signals TF-IDF fallback at retrieval time


async def _gemini_embed(text: str) -> list[float]:
    import httpx
    url = f"https://generativelanguage.googleapis.com/v1beta/{settings.GEMINI_EMBED_MODEL}:embedContent?key={settings.GEMINI_API_KEY}"
    payload = {"model": settings.GEMINI_EMBED_MODEL, "content": {"parts": [{"text": text}]}}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _tfidf_cosine(query: str, candidates: list[str]) -> list[float]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    if not candidates:
        return []
    docs = [query] + candidates
    try:
        vec = TfidfVectorizer().fit_transform(docs)
    except ValueError:
        return [0.0] * len(candidates)
    arr = vec.toarray()
    query_vec = arr[0]
    scores = []
    for i in range(1, len(arr)):
        denom = np.linalg.norm(query_vec) * np.linalg.norm(arr[i])
        scores.append(float(np.dot(query_vec, arr[i]) / denom) if denom else 0.0)
    return scores


def retrieve_similar(
    new_statement: str,
    new_embedding: list[float],
    past_decisions: list[models.Decision],
    top_n: int = 5,
) -> list[models.Decision]:
    """Return top-N similar past decisions."""
    if not past_decisions:
        return []

    use_gemini = bool(new_embedding) and all(d.embedding for d in past_decisions)

    if use_gemini:
        scored = []
        for d in past_decisions:
            if d.embedding:
                score = _cosine(new_embedding, d.embedding)
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_n]]
    else:
        # TF-IDF fallback
        statements = [d.statement for d in past_decisions]
        scores = _tfidf_cosine(new_statement, statements)
        paired = sorted(zip(scores, past_decisions), key=lambda x: x[0], reverse=True)
        return [d for _, d in paired[:top_n]]
