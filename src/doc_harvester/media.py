"""Portable media-type inference for built-in adapters."""

from __future__ import annotations

import mimetypes
from pathlib import PurePath


_PORTABLE_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


def guess_media_type(path: str) -> str:
    """Return a stable known type before consulting the host MIME database."""
    suffix = PurePath(path).suffix.lower()
    if suffix in _PORTABLE_TYPES:
        return _PORTABLE_TYPES[suffix]
    return mimetypes.guess_type(path)[0] or ""

