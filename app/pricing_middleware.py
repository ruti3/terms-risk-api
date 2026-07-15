"""Attach cache-aware pricing context before x402 payment verification."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


def _cache_has_entry(url: str, use_case: str) -> bool:
    try:
        from app import main

        if getattr(main, "cache", None) is not None:
            return main.cache.has_entry(url, use_case)
    except Exception:
        logger.debug("cache lookup for pricing failed", exc_info=True)
    return False


async def _pricing_context_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path.rstrip("/") == "/terms-risk":
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive  # noqa: SLF001 — Starlette body replay pattern

        try:
            data = json.loads(body)
            url = str(data.get("url", ""))
            use_case = str(data.get("use_case", ""))
            request.state.x402_pricing_tier = (
                "cached" if url and use_case and _cache_has_entry(url, use_case) else "fresh"
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            request.state.x402_pricing_tier = "fresh"

    return await call_next(request)


def attach_pricing_context_middleware(app: FastAPI) -> None:
    """Register middleware that runs before x402 (add after PaymentMiddlewareASGI)."""
    app.middleware("http")(_pricing_context_middleware)
