"""Load CDP API credentials from environment or gitignored files."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_cdp_api_credentials() -> dict[str, str] | None:
    """
    Return CDP API key id/secret when configured.

    Reads CDP_API_KEY_ID / CDP_API_KEY_SECRET from the environment, or
    falls back to cdp_api_key.json (same layout as scripts/lib/cdp-credentials.mjs).
    """
    api_key_id = os.getenv("CDP_API_KEY_ID")
    api_key_secret = os.getenv("CDP_API_KEY_SECRET")

    key_file = ROOT / "cdp_api_key.json"
    if (not api_key_id or not api_key_secret) and key_file.is_file():
        key = json.loads(key_file.read_text(encoding="utf-8"))
        api_key_id = api_key_id or key.get("id")
        api_key_secret = api_key_secret or key.get("privateKey")

    if api_key_id and api_key_secret:
        return {"api_key_id": api_key_id, "api_key_secret": api_key_secret}
    return None
