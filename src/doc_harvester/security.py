"""Security helpers shared by command-line and crawler logging."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>]+")


def sanitize_url_for_logging(value: str) -> str:
    """Remove credentials, query parameters, and fragments from a URL before logging."""
    raw = str(value or "").strip()
    if not raw:
        return ""

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.split("?", 1)[0].split("#", 1)[0]

    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def sanitize_text_for_logging(value: object) -> str:
    """Redact credentials, queries, and fragments from URLs embedded in log text."""
    text = str(value)
    return _URL_IN_TEXT.sub(
        lambda match: sanitize_url_for_logging(match.group(0)),
        text,
    )
