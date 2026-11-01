"""Short-lived HTTP connection pool shared by provider calls in one request."""
from contextvars import ContextVar
from contextlib import asynccontextmanager
from typing import Optional
import httpx


_request_client: ContextVar[Optional[httpx.AsyncClient]] = ContextVar(
    "provider_http_client", default=None
)


@asynccontextmanager
async def provider_http_session():
    """Reuse keep-alive connections across AI calls in a meeting request."""
    async with httpx.AsyncClient(
        timeout=20,
        limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=30),
    ) as client:
        token = _request_client.set(client)
        try:
            yield
        finally:
            _request_client.reset(token)


async def provider_post(url: str, *, timeout: float = 20, **kwargs) -> httpx.Response:
    """POST with the request-scoped pool, or a one-off client outside requests."""
    client = _request_client.get()
    if client is not None:
        return await client.post(url, timeout=timeout, **kwargs)
    async with httpx.AsyncClient(timeout=timeout) as temporary_client:
        return await temporary_client.post(url, **kwargs)
