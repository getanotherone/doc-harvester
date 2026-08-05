"""Built-in crawler selection."""

from __future__ import annotations

from typing import Any

from doc_harvester.core import Crawler
from doc_harvester.crawlers.html import HTMLCrawler


def available_crawlers() -> tuple[str, ...]:
    return ("html",)


def create_crawler(name: str, **options: Any) -> Crawler:
    normalized = name.strip().lower()
    if normalized in {"html", "web"}:
        return HTMLCrawler(**options)
    raise ValueError(
        f"unknown crawler '{name}'; available crawlers: {', '.join(available_crawlers())}"
    )
