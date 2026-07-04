"""Pydantic models for Terms Risk API."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field, HttpUrl

TriState = Union[bool, Literal["unclear"]]
RiskLevel = Literal["low", "medium", "high", "unclear"]


class TermsRiskRequest(BaseModel):
    url: HttpUrl
    use_case: str = Field(..., min_length=3, max_length=2000)


class EvidenceItem(BaseModel):
    quote: str
    reason: str


class AnalysisResult(BaseModel):
    """Structured analysis from the model (no url/use_case/cached)."""

    risk_level: RiskLevel
    scraping_allowed: TriState
    commercial_use_allowed: TriState
    redistribution_allowed: TriState
    requires_attribution: TriState
    requires_official_api: TriState
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class TermsRiskResponse(BaseModel):
    url: str
    use_case: str
    risk_level: RiskLevel
    scraping_allowed: TriState
    commercial_use_allowed: TriState
    redistribution_allowed: TriState
    requires_attribution: TriState
    requires_official_api: TriState
    confidence: float
    summary: str
    evidence: list[EvidenceItem]
    cached: bool
    generated_at: str  # ISO-8601 UTC when this analysis was produced
    cache_age_days: int  # 0 for fresh; days since generated_at for cache hits
    disclaimer: str
    price_usd: float | None = None


class ErrorResponse(BaseModel):
    error: str
    error_type: str
    disclaimer: str
