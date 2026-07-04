"""Fetch policy pages over HTTP."""

from __future__ import annotations

import httpx
from urllib.parse import urlparse

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 15.0


class FetchError(Exception):
    def __init__(self, message: str, error_type: str) -> None:
        super().__init__(message)
        self.error_type = error_type


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("URL must use http or https.", "invalid_url")
    if not parsed.netloc:
        raise FetchError("URL is missing a host.", "invalid_url")


async def fetch_url(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """
    Fetch *url* and return (final_url, html).

    Raises FetchError with a clear error_type on failure.
    """
    _validate_url(url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise FetchError(f"Request timed out after {timeout}s.", "timeout") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Could not reach URL: {exc}", "network_error") from exc

    if response.status_code in (401, 403):
        raise FetchError("Access to the page was blocked.", "blocked")
    if response.status_code == 404:
        raise FetchError("Page not found.", "not_found")
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} from origin.", "http_error")

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text/" not in content_type:
        raise FetchError(
            f"Expected HTML content, got {content_type or 'unknown'}.",
            "non_html",
        )

    # httpx may not decode binary; ensure str
    text = response.text
    if not text.strip():
        raise FetchError("Empty response body.", "empty_response")

    return str(response.url), text
