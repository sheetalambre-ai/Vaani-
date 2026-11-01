"""MemoryAgent: embeds decisions and retrieves top-N similar past decisions."""
from collections import Counter
import math
import re
from app.config import settings
from app import models
from app.provider_http import provider_post

_TOKEN = re.compile(r"(?u)\b\w\w+\b")


async def embed_text(text: str) -> list[float]:
    """Embed using Gemini when configured; retrieval falls back to TF-IDF on failure."""
    embeddings = await embed_texts([text])
    return embeddings[0] if embeddings else []


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple decisions in one Gemini request, preserving TF-IDF fallback."""
    if not texts:
        return []
    if not settings.GEMINI_API_KEY or not settings.GEMINI_EMBED_MODEL:
        return [[] for _ in texts]

    model = settings.GEMINI_EMBED_MODEL or "gemini-embedding-001"
    # Keep old Vercel environment values working: text-embedding-004 now
    # returns 404, so route that legacy name to Google's current stable model.
    if model.removeprefix("models/") == "text-embedding-004":
        model = "gemini-embedding-001"
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:batchEmbedContents"
    payload = {
        "requests": [
            {"model": model_path, "content": {"parts": [{"text": text}]}}
            for text in texts
        ]
    }
    try:
        response = await provider_post(
            url,
            timeout=30,
            json=payload,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        )
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
        if len(embeddings) != len(texts):
            raise ValueError("Gemini returned an incomplete embedding batch")
        vectors = [item["values"] for item in embeddings]
        print(f"Gemini embeddings succeeded: model={model_path}, count={len(vectors)}, dimensions={len(vectors[0]) if vectors else 0}")
        return vectors
    except Exception:
        # A retired/unavailable model or invalid credentials cannot be fixed by
        # retrying the same request once per decision; use the existing local
        # TF-IDF retrieval path instead.
        return [[] for _ in texts]


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity without loading a numerical-computing runtime."""
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _tfidf_cosine(query: str, candidates: list[str]) -> list[float]:
    """Small-corpus TF-IDF cosine fallback implemented with the standard library."""
    if not candidates:
        return []

    docs = [_TOKEN.findall(text.lower()) for text in [query, *candidates]]
    document_frequency = Counter(token for doc in docs for token in set(doc))
    if not document_frequency:
        return [0.0] * len(candidates)

    doc_count = len(docs)
    idf = {
        token: math.log((1 + doc_count) / (1 + count)) + 1
        for token, count in document_frequency.items()
    }

    def weighted_vector(tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        return {token: frequency * idf[token] for token, frequency in counts.items()}

    vectors = [weighted_vector(doc) for doc in docs]
    query_vector = vectors[0]
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scores = []
    for vector in vectors[1:]:
        norm = math.sqrt(sum(value * value for value in vector.values()))
        dot = sum(value * vector.get(token, 0.0) for token, value in query_vector.items())
        scores.append(dot / (query_norm * norm) if query_norm and norm else 0.0)
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

    use_gemini = (
        bool(new_embedding)
        and all(d.embedding and len(d.embedding) == len(new_embedding) for d in past_decisions)
    )

    if use_gemini:
        scored = []
        for d in past_decisions:
            if d.embedding:
                score = _cosine(new_embedding, d.embedding)
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_n]]

    statements = [d.statement for d in past_decisions]
    scores = _tfidf_cosine(new_statement, statements)
    paired = sorted(zip(scores, past_decisions), key=lambda x: x[0], reverse=True)
    return [d for _, d in paired[:top_n]]
