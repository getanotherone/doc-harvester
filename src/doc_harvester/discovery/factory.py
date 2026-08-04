"""Built-in discovery-provider selection."""

from __future__ import annotations

from typing import Any

from doc_harvester.core import DiscoveryProvider
from doc_harvester.discovery.manual import ManualDiscoveryProvider
from doc_harvester.discovery.sitemap import SitemapDiscoveryProvider


def available_discovery_providers() -> tuple[str, ...]:
    return ("manual", "sitemap")


def create_discovery_provider(name: str, **options: Any) -> DiscoveryProvider:
    normalized = name.strip().lower()
    if normalized == "manual":
        return ManualDiscoveryProvider(**options)
    if normalized == "sitemap":
        return SitemapDiscoveryProvider(**options)
    raise ValueError(
        "unknown discovery provider "
        f"'{name}'; available providers: {', '.join(available_discovery_providers())}"
    )
