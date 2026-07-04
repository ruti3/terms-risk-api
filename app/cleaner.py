"""Extract readable text from HTML policy pages."""

from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup, Comment
from readability import Document

# Tags stripped before readability extraction
REMOVE_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "iframe", "svg")

# Common cookie-banner class/id fragments (best-effort)
BANNER_PATTERNS = re.compile(
    r"cookie|consent|gdpr|banner|popup|modal",
    re.IGNORECASE,
)

DEFAULT_MAX_CHARS = 12_000


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tag_attrs(el) -> dict:
    """Return tag attrs dict, handling tags where attrs is None."""
    attrs = getattr(el, "attrs", None)
    return attrs if isinstance(attrs, dict) else {}


def _remove_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for el in soup.find_all(True):
        attrs = _tag_attrs(el)
        class_val = attrs.get("class") or []
        if isinstance(class_val, str):
            class_val = [class_val]
        attr_text = " ".join(
            filter(None, [str(attrs.get("id", "")), " ".join(class_val)])
        )
        if BANNER_PATTERNS.search(attr_text):
            el.decompose()


def clean_html(html: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """
    Return cleaned plain text suitable for model analysis.

    Uses BeautifulSoup to strip noise, then readability-lxml for main content.
    """
    soup = BeautifulSoup(html, "lxml")
    _remove_noise(soup)

    doc = Document(str(soup))
    title = doc.title() or ""
    summary_html = doc.summary(html_partial=True)
    summary_soup = BeautifulSoup(summary_html, "lxml")
    body_text = summary_soup.get_text(separator="\n", strip=True)

    parts = [p for p in (title.strip(), body_text) if p]
    text = "\n\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    if len(text) > max_chars:
        # Keep head + tail so evidence from intro and restrictions sections may survive
        head = text[: max_chars // 2]
        tail = text[-(max_chars // 2) :]
        text = f"{head}\n\n[... truncated ...]\n\n{tail}"

    return text.strip()
