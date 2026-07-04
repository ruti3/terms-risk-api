"""JSON request logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


class RequestLogger:
    def __init__(self, log_dir: str | Path) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        url: str,
        use_case: str,
        cached: bool,
        latency_ms: float,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        domain = urlparse(url).netloc or "unknown"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "domain": domain,
            "use_case": use_case,
            "cached": cached,
            "latency_ms": round(latency_ms, 1),
            "success": success,
            "error_type": error_type,
        }
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.log_dir / f"requests-{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
