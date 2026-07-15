"""Terms Risk API — FastAPI application."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse

from app.analyzer import analyze_policy
from app.cache import Cache
from app.cleaner import clean_html, text_hash
from app.discovery import API_TITLE, API_VERSION, build_discovery_openapi, well_known_x402
from app.fetcher import FetchError, fetch_url
from app.logger import RequestLogger
from app.models import ErrorResponse, TermsRiskRequest, TermsRiskResponse
from app.pricing import CACHED_PRICE_USD, DISCLAIMER, FRESH_PRICE_USD
from app.pricing_middleware import attach_pricing_context_middleware
from app.x402_config import setup_x402_middleware, x402_enabled, x402_skip_payment

load_dotenv()

CACHE_DB = os.getenv("CACHE_DB_PATH", "data/cache.sqlite")
LOG_DIR = os.getenv("LOG_DIR", "data/logs")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "12000"))
LLMS_TXT = Path(__file__).resolve().parent.parent / "llms.txt"

cache: Cache
request_logger: RequestLogger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global cache, request_logger
    cache = Cache(CACHE_DB)
    request_logger = RequestLogger(LOG_DIR)
    yield


app = FastAPI(
    title=API_TITLE,
    description="Paid API that analyzes Terms/Policy pages for use-case risk.",
    version=API_VERSION,
    lifespan=lifespan,
    openapi_url=None,  # custom x402scan discovery doc at GET /openapi.json
)

# x402 payment gate — must wrap routes (see app/x402_config.py)
setup_x402_middleware(app)
# Runs before x402 on incoming requests (Starlette: registered after = outermost)
attach_pricing_context_middleware(app)


@app.get("/")
def root() -> dict:
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "description": (
            "POST /terms-risk with a policy URL and use case to get structured "
            "risk analysis with evidence quotes."
        ),
        "pricing": {
            "cached_usd": CACHED_PRICE_USD,
            "fresh_usd": FRESH_PRICE_USD,
            "x402_enabled": x402_enabled(),
            "x402_skip_payment": x402_skip_payment(),
        },
        "disclaimer": DISCLAIMER,
        "discovery": {
            "openapi": "/openapi.json",
            "well_known": "/.well-known/x402",
            "llms_txt": "/llms.txt",
        },
        "latency_ms_typical": {
            "cached": "50-200",
            "fresh": "3000-15000",
            "fetch_timeout": int(TIMEOUT * 1000),
        },
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/llms.txt", include_in_schema=False)
def llms_txt() -> FileResponse:
    """Agent discovery file (llms.txt convention)."""
    return FileResponse(LLMS_TXT, media_type="text/plain; charset=utf-8")


@app.get("/.well-known/x402")
@app.get("/.well-known/x402.json")
def well_known(request: Request) -> dict:
    """x402scan compatibility discovery fan-out."""
    public_base = os.getenv("PUBLIC_BASE_URL")
    base = public_base.rstrip("/") if public_base else str(request.base_url).rstrip("/")
    return well_known_x402(base)


@app.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request) -> JSONResponse:
    """x402scan OpenAPI-first discovery document."""
    public_base = os.getenv("PUBLIC_BASE_URL")
    base = public_base.rstrip("/") if public_base else str(request.base_url).rstrip("/")
    return JSONResponse(build_discovery_openapi(base))


@app.get("/docs", include_in_schema=False)
def docs():
    """Interactive API reference (Swagger UI)."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title=API_TITLE)


@app.post(
    "/terms-risk",
    response_model=TermsRiskResponse,
    responses={
        400: {"model": ErrorResponse},
        402: {"description": "Payment Required"},
        502: {"model": ErrorResponse},
    },
)
async def terms_risk(body: TermsRiskRequest) -> TermsRiskResponse:
    """Analyze a Terms/Policy URL for a specific use case."""
    url = str(body.url)
    start = time.perf_counter()
    cached_hit = False

    try:
        final_url, html = await fetch_url(url, timeout=TIMEOUT)
        cleaned = clean_html(html, max_chars=MAX_TEXT_CHARS)
        if len(cleaned) < 50:
            raise FetchError("Could not extract enough readable text.", "empty_content")

        content_hash = text_hash(cleaned)
        cached_result = cache.get(body, content_hash)
        if cached_result:
            cached_hit = True
            cached_result.price_usd = CACHED_PRICE_USD
            result = cached_result
        else:
            analysis = analyze_policy(cleaned, final_url, body.use_case)
            result = cache.set(body, content_hash, analysis)
            result.cached = False
            result.price_usd = FRESH_PRICE_USD

        request_logger.log(
            url=final_url,
            use_case=body.use_case,
            cached=cached_hit,
            latency_ms=(time.perf_counter() - start) * 1000,
            success=True,
        )
        return result

    except FetchError as exc:
        request_logger.log(
            url=url,
            use_case=body.use_case,
            cached=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error_type=exc.error_type,
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=str(exc), error_type=exc.error_type, disclaimer=DISCLAIMER
            ).model_dump(),
        ) from exc
    except Exception as exc:
        request_logger.log(
            url=url,
            use_case=body.use_case,
            cached=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error_type="analysis_error",
        )
        raise HTTPException(
            status_code=502,
            detail=ErrorResponse(
                error=str(exc), error_type="analysis_error", disclaimer=DISCLAIMER
            ).model_dump(),
        ) from exc
