"""Built-in fetcher selection."""

from __future__ import annotations

from typing import Any

from doc_harvester.core import Fetcher
from doc_harvester.fetchers.http import HTTPFetcher
from doc_harvester.fetchers.local import LocalFileFetcher


def available_fetchers() -> tuple[str, ...]:
    return ("http", "local-file")


def create_fetcher(name: str, **options: Any) -> Fetcher:
    normalized = name.strip().lower()
    if normalized == "http":
        return HTTPFetcher(**options)
    if normalized in {"file", "local", "local-file"}:
        return LocalFileFetcher(**options)
    raise ValueError(
        f"unknown fetcher '{name}'; available fetchers: {', '.join(available_fetchers())}"
    )
