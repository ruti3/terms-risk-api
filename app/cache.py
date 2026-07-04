"""SQLite cache for analysis results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import AnalysisResult, TermsRiskRequest, TermsRiskResponse
from app.pricing import CACHED_PRICE_USD, DISCLAIMER

# Fields stored in result_json (analysis only — metadata computed at response time)
_PAYLOAD_EXCLUDE = frozenset(
    {"cached", "disclaimer", "price_usd", "generated_at", "cache_age_days"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_age_days(generated_at: str) -> int:
    """Whole days between generated_at and now (UTC)."""
    generated = datetime.fromisoformat(generated_at)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, (now - generated).days)


def _cache_key(url: str, use_case: str) -> str:
    return f"{url.strip().lower()}|{use_case.strip().lower()}"


class Cache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    cleaned_text_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def get(
        self, request: TermsRiskRequest, cleaned_text_hash: str
    ) -> TermsRiskResponse | None:
        key = _cache_key(str(request.url), request.use_case)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        if row["cleaned_text_hash"] != cleaned_text_hash:
            return None  # page changed — re-analyze

        generated_at = row["updated_at"]
        data = json.loads(row["result_json"])
        return TermsRiskResponse(
            **data,
            cached=True,
            generated_at=generated_at,
            cache_age_days=_cache_age_days(generated_at),
            disclaimer=DISCLAIMER,
            price_usd=CACHED_PRICE_USD,
        )

    def set(
        self,
        request: TermsRiskRequest,
        cleaned_text_hash: str,
        analysis: AnalysisResult,
    ) -> TermsRiskResponse:
        key = _cache_key(str(request.url), request.use_case)
        now = _utc_now()
        response = TermsRiskResponse(
            url=str(request.url),
            use_case=request.use_case,
            **analysis.model_dump(),
            cached=False,
            generated_at=now,
            cache_age_days=0,
            disclaimer=DISCLAIMER,
            price_usd=None,  # set by caller for fresh hits
        )
        payload = response.model_dump(exclude=_PAYLOAD_EXCLUDE)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache (cache_key, url, use_case, cleaned_text_hash,
                                   result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    cleaned_text_hash = excluded.cleaned_text_hash,
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    str(request.url),
                    request.use_case,
                    cleaned_text_hash,
                    json.dumps(payload),
                    now,
                    now,
                ),
            )
        return response
