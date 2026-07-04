"""OpenAI structured analysis of policy text."""

from __future__ import annotations

import os

from openai import OpenAI

from app.models import AnalysisResult

SYSTEM_PROMPT = """\
You analyze Terms of Service, Privacy Policies, and license pages.

Given policy text and a user's use case, return structured JSON only.

Rules:
- Base answers only on the provided policy text.
- Use "unclear" when the text does not clearly support true/false.
- risk_level: low / medium / high / unclear for the specific use case.
- confidence: 0.0–1.0 reflecting how explicit the policy is.
- evidence: 1–5 short direct quotes from the text with brief reasons.
- summary: 1–3 sentences, plain English.
- This is NOT legal advice."""


def analyze_policy(
    policy_text: str,
    url: str,
    use_case: str,
    *,
    model: str | None = None,
) -> AnalysisResult:
    """Call OpenAI with structured output matching AnalysisResult."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    user_content = (
        f"URL: {url}\n\n"
        f"Use case: {use_case}\n\n"
        f"Policy text:\n{policy_text}"
    )

    response = client.responses.parse(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=user_content,
        text_format=AnalysisResult,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("Model returned no structured output.")
    return parsed
