"""
x402scan discovery metadata (OpenAPI-first + /.well-known/x402).

Spec: https://x402scan.com/discovery/spec
"""

from __future__ import annotations

from typing import Any

from app.models import TermsRiskRequest, TermsRiskResponse
from app.pricing import CACHED_PRICE_USD, DISCLAIMER, FRESH_PRICE_USD

API_TITLE = "Terms Risk API"
API_VERSION = "0.1.0"
API_CONTACT_EMAIL = "ruuthi@gmail.com"

X_GUIDANCE = (
    "Analyzes a Terms of Service, Privacy Policy, or license URL against a "
    "specific use case. Returns structured risk fields, evidence quotes, and "
    "cache metadata (generated_at, cache_age_days, price_usd) so agents can "
    "decide whether to pay for a fresh analysis. "
    "Typical latency: 50-200ms cached, 3-15s fresh (includes fetch + LLM). "
    "Fetch timeout: 15s. "
    f"{DISCLAIMER}"
)

# Example for Bazaar / OpenAPI output documentation
RESPONSE_EXAMPLE: dict[str, Any] = {
    "url": "https://www.cloudflare.com/website-terms/",
    "use_case": "Can I scrape and commercially reuse public listings?",
    "risk_level": "high",
    "scraping_allowed": False,
    "commercial_use_allowed": False,
    "redistribution_allowed": False,
    "requires_attribution": True,
    "requires_official_api": False,
    "confidence": 0.88,
    "summary": "The terms likely restrict automated access and commercial reuse.",
    "evidence": [
        {
            "quote": "Automated access is prohibited.",
            "reason": "This directly restricts scraping.",
        }
    ],
    "cached": False,
    "generated_at": "2026-07-04T19:00:00+00:00",
    "cache_age_days": 0,
    "disclaimer": DISCLAIMER,
    "price_usd": FRESH_PRICE_USD,
}

REQUEST_SCHEMA = TermsRiskRequest.model_json_schema()
RESPONSE_SCHEMA = TermsRiskResponse.model_json_schema()
ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "error": {"type": "string"},
        "error_type": {"type": "string"},
        "disclaimer": {"type": "string"},
    },
    "required": ["error", "error_type", "disclaimer"],
}

ERROR_EXAMPLES: dict[str, dict[str, Any]] = {
    "invalid_url": {
        "error": "URL must use http or https.",
        "error_type": "invalid_url",
        "disclaimer": DISCLAIMER,
    },
    "timeout": {
        "error": "Request timed out after 15.0s.",
        "error_type": "timeout",
        "disclaimer": DISCLAIMER,
    },
    "blocked": {
        "error": "Access to the page was blocked.",
        "error_type": "blocked",
        "disclaimer": DISCLAIMER,
    },
    "empty_content": {
        "error": "Could not extract enough readable text.",
        "error_type": "empty_content",
        "disclaimer": DISCLAIMER,
    },
    "analysis_error": {
        "error": "OpenAI analysis failed.",
        "error_type": "analysis_error",
        "disclaimer": DISCLAIMER,
    },
}


def _payment_info() -> dict[str, Any]:
    """OpenAPI x-payment-info extension for paid operations."""
    return {
        "price": {
            "mode": "dynamic",
            "currency": "USD",
            "min": f"{CACHED_PRICE_USD:.2f}",
            "max": f"{FRESH_PRICE_USD:.2f}",
        },
        "protocols": [{"x402": {}}],
    }


def build_discovery_openapi(base_url: str) -> dict[str, Any]:
    """
    OpenAPI 3.1 document with x402scan-required extensions.

    Served at GET /openapi.json — takes precedence over FastAPI's default.
    """
    resource_url = f"{base_url.rstrip('/')}/terms-risk"

    # NOTE:
    # Pydantic v2 emits JSON Schemas with `$defs` *inside* the model schema object
    # while `$ref` pointers may still be written as `#/$defs/...` (document-root).
    # Some discovery validators (including `@agentcash/discovery`) dereference
    # JSON pointers assuming `$defs` exists at the OpenAPI document root.
    # Hoist `$defs` to the top-level so refs like `#/$defs/EvidenceItem` resolve.
    response_schema = dict(RESPONSE_SCHEMA)
    response_defs = response_schema.pop("$defs", {})

    return {
        "openapi": "3.1.0",
        "info": {
            "title": API_TITLE,
            "version": API_VERSION,
            "description": (
                "Paid API that fetches a policy page and returns structured "
                "legal-risk analysis for a specific use case."
            ),
            "contact": {
                "email": API_CONTACT_EMAIL,
            },
            "x-guidance": X_GUIDANCE,
        },
        "x-discovery": {
            "ownershipProofs": [],  # add wallet signatures when available
        },
        "servers": [{"url": base_url.rstrip("/")}],
        "paths": {
            "/terms-risk": {
                "post": {
                    "operationId": "analyzeTermsRisk",
                    "summary": "Analyze Terms of Service for use-case risk",
                    "description": X_GUIDANCE,
                    "tags": ["terms", "policy", "legal"],
                    # Explicitly mark as public from an OpenAPI auth perspective.
                    # x402 payment gating is represented via `x-payment-info`.
                    "security": [],
                    "x-payment-info": _payment_info(),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": REQUEST_SCHEMA,
                                "example": {
                                    "url": "https://www.cloudflare.com/website-terms/",
                                    "use_case": (
                                        "Can I scrape and commercially reuse "
                                        "public listings?"
                                    ),
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Structured risk analysis",
                            "content": {
                                "application/json": {
                                    "schema": RESPONSE_SCHEMA,
                                    "example": RESPONSE_EXAMPLE,
                                }
                            },
                        },
                        "402": {"description": "Payment Required (x402)"},
                        "400": {
                            "description": "Invalid URL or fetch error",
                            "content": {
                                "application/json": {
                                    "schema": ERROR_SCHEMA,
                                    "examples": {
                                        k: {"value": v} for k, v in ERROR_EXAMPLES.items()
                                        if k != "analysis_error"
                                    },
                                }
                            },
                        },
                        "502": {
                            "description": "Analysis error",
                            "content": {
                                "application/json": {
                                    "schema": ERROR_SCHEMA,
                                    "example": ERROR_EXAMPLES["analysis_error"],
                                }
                            },
                        },
                    },
                }
            },
            "/health": {
                "get": {
                    "operationId": "healthCheck",
                    "summary": "Health check",
                    "responses": {"200": {"description": "OK"}},
                    # Liveness probe should be callable without auth.
                    "security": [],
                }
            },
        },
        "components": {
            "schemas": {
                "TermsRiskRequest": REQUEST_SCHEMA,
                "TermsRiskResponse": response_schema,
            }
        },
        # JSON Schema `$defs` for any `#/$defs/...` refs in component schemas.
        "$defs": response_defs,
        "x402": {
            "resources": [resource_url],
        },
    }


def well_known_x402(base_url: str) -> dict[str, Any]:
    """Payload for GET /.well-known/x402 (compatibility fan-out)."""
    resource = f"{base_url.rstrip('/')}/terms-risk"
    return {
        "version": 1,
        "resources": [resource],
        "instructions": (
            "POST /terms-risk with JSON body {url, use_case}. "
            f"Pricing: ${CACHED_PRICE_USD:.2f} cached, ${FRESH_PRICE_USD:.2f} fresh. "
            f"{DISCLAIMER}"
        ),
    }
