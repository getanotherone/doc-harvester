"""Credential-free built-in discovery adapters."""

from doc_harvester.discovery.factory import (
    available_discovery_providers,
    create_discovery_provider,
)
from doc_harvester.discovery.manual import ManualDiscoveryProvider
from doc_harvester.discovery.sitemap import SitemapDiscoveryProvider

__all__ = [
    "ManualDiscoveryProvider",
    "SitemapDiscoveryProvider",
    "available_discovery_providers",
    "create_discovery_provider",
]
