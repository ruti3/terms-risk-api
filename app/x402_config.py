"""
x402 payment middleware configuration.

Uses the official x402 Python SDK for 402 challenges and Bazaar discovery.
Set X402_ENABLED=true and X402_PAY_TO to enforce payment in production.

Local dev without wallet: X402_SKIP_PAYMENT=true
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.discovery import RESPONSE_EXAMPLE, X_GUIDANCE
from app.pricing import CACHED_PRICE_USD, FRESH_PRICE_USD

if TYPE_CHECKING:
    from fastapi import FastAPI
    from x402.http.types import HTTPRequestContext

# Defaults — Base Sepolia testnet (supported by https://x402.org/facilitator).
# For Base mainnet production, set X402_NETWORK=eip155:8453 and CDP facilitator.
DEFAULT_NETWORK = "eip155:84532"
DEFAULT_FACILITATOR = "https://x402.org/facilitator"
CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"


def x402_enabled() -> bool:
    return os.getenv("X402_ENABLED", "false").lower() in ("1", "true", "yes")


def x402_skip_payment() -> bool:
    return os.getenv("X402_SKIP_PAYMENT", "false").lower() in ("1", "true", "yes")


def _terms_risk_price(context: HTTPRequestContext) -> str:
    """$0.01 when url+use_case exists in cache, else $0.03."""
    request = getattr(context.adapter, "_request", None)
    tier = getattr(request.state, "x402_pricing_tier", "fresh") if request else "fresh"
    if tier == "cached":
        return f"${CACHED_PRICE_USD:.2f}"
    return f"${FRESH_PRICE_USD:.2f}"


def _build_facilitator():
    from x402.http import HTTPFacilitatorClient

    from app.cdp_credentials import load_cdp_api_credentials

    facilitator_url = os.getenv("X402_FACILITATOR_URL", DEFAULT_FACILITATOR).rstrip("/")
    creds = load_cdp_api_credentials()
    needs_cdp_auth = "cdp.coinbase.com" in facilitator_url

    if needs_cdp_auth and creds:
        from cdp.x402 import create_facilitator_config

        config = create_facilitator_config(creds["api_key_id"], creds["api_key_secret"])
        if facilitator_url != config["url"]:
            config = {**config, "url": facilitator_url}
        return HTTPFacilitatorClient(config)

    if needs_cdp_auth and not creds:
        raise RuntimeError(
            "X402_FACILITATOR_URL points at CDP but CDP_API_KEY_ID / "
            "CDP_API_KEY_SECRET are not configured."
        )

    return HTTPFacilitatorClient({"url": facilitator_url})


def _build_routes() -> dict:
    from x402.extensions.bazaar import OutputConfig, declare_discovery_extension
    from x402.http.types import PaymentOption, RouteConfig

    pay_to = os.getenv("X402_PAY_TO", "")
    if not pay_to:
        # Placeholder for discovery probes — replace with your wallet
        pay_to = "0x0000000000000000000000000000000000000001"

    network = os.getenv("X402_NETWORK", DEFAULT_NETWORK)

    extensions = declare_discovery_extension(
        input={
            "url": "https://www.cloudflare.com/website-terms/",
            "use_case": "Can I scrape and commercially reuse public listings?",
        },
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Terms/Policy page URL",
                },
                "use_case": {
                    "type": "string",
                    "minLength": 3,
                    "description": "What you want to do with the site content",
                },
            },
            "required": ["url", "use_case"],
        },
        body_type="json",
        output=OutputConfig(
            example=RESPONSE_EXAMPLE,
            schema={
                "type": "object",
                "properties": {
                    "risk_level": {"type": "string"},
                    "confidence": {"type": "number"},
                    "summary": {"type": "string"},
                    "cached": {"type": "boolean"},
                    "cache_age_days": {"type": "integer"},
                },
            },
        ),
    )

    return {
        "POST /terms-risk": RouteConfig(
            accepts=PaymentOption(
                scheme="exact",
                pay_to=pay_to,
                price=_terms_risk_price,
                network=network,
            ),
            description=X_GUIDANCE[:200],
            mime_type="application/json",
            service_name="Terms Risk API",
            tags=["terms", "policy", "legal", "risk"],
            extensions=extensions,
        ),
    }


def setup_x402_middleware(app: FastAPI) -> None:
    """
    Attach x402 PaymentMiddlewareASGI when X402_ENABLED=true.

    Skipped when X402_SKIP_PAYMENT=true (local testing without wallet).
    """
    if not x402_enabled() or x402_skip_payment():
        return

    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.mechanisms.evm.exact import ExactEvmServerScheme
    from x402.server import x402ResourceServer

    network = os.getenv("X402_NETWORK", DEFAULT_NETWORK)

    facilitator = _build_facilitator()
    server = x402ResourceServer(facilitator)
    server.register(network, ExactEvmServerScheme())

    routes = _build_routes()
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
