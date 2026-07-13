"""Publisher factory backed by environment variables and plugin entry points."""

from __future__ import annotations

import os
from importlib.metadata import entry_points
from typing import Any, Callable

from doc_harvester.publishers.base import Publisher
from doc_harvester.publishers.confluence import ConfluencePublisher
from doc_harvester.publishers.local import LocalPublisher
from doc_harvester.publishers.notion import NotionPublisher
from doc_harvester.publishers.yandex_wiki import YandexWikiPublisher

PublisherFactory = Callable[..., Publisher]
PUBLISHER_ENTRY_POINT_GROUP = "doc_harvester.publishers"
BUILTIN_PUBLISHERS = frozenset({"local", "yandex-wiki", "confluence", "notion"})
_registered_publishers: dict[str, PublisherFactory] = {}


def _normalize_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("publisher name cannot be empty")
    return normalized


def register_publisher(name: str, factory: PublisherFactory, *, replace: bool = False) -> None:
    """Register an in-process publisher factory for applications and tests."""
    normalized = _normalize_name(name)
    if normalized in BUILTIN_PUBLISHERS:
        raise ValueError(f"cannot replace built-in publisher: {normalized}")
    if normalized in _registered_publishers and not replace:
        raise ValueError(f"publisher already registered: {normalized}")
    _registered_publishers[normalized] = factory


def _publisher_entry_points() -> dict[str, Any]:
    discovered: dict[str, Any] = {}
    for entry_point in entry_points(group=PUBLISHER_ENTRY_POINT_GROUP):
        discovered[_normalize_name(entry_point.name)] = entry_point
    return discovered


def available_publishers() -> tuple[str, ...]:
    names = set(BUILTIN_PUBLISHERS)
    names.update(_registered_publishers)
    names.update(_publisher_entry_points())
    return tuple(sorted(names))


def create_publisher(name: str | None = None, **overrides: Any) -> Publisher:
    provider = _normalize_name(name or os.environ.get("DOC_HARVESTER_PUBLISHER", "local"))
    if provider == "local":
        root = overrides.get("root") or os.environ.get("DOC_HARVESTER_PUBLISH_ROOT", "published")
        return LocalPublisher(root)
    if provider == "yandex-wiki":
        return YandexWikiPublisher(
            token=overrides.get("token") or os.environ.get("YANDEX_WIKI_TOKEN", ""),
            cloud_org_id=overrides.get("cloud_org_id")
            or os.environ.get("YANDEX_WIKI_CLOUD_ORG_ID", ""),
            base_url=overrides.get("base_url")
            or os.environ.get("YANDEX_WIKI_API_BASE", "https://api.wiki.yandex.net"),
            session=overrides.get("session"),
        )
    if provider == "confluence":
        return ConfluencePublisher(
            base_url=overrides.get("base_url") or os.environ.get("CONFLUENCE_BASE_URL", ""),
            email=overrides.get("email") or os.environ.get("CONFLUENCE_EMAIL", ""),
            api_token=overrides.get("api_token")
            or os.environ.get("CONFLUENCE_API_TOKEN", ""),
            space_id=overrides.get("space_id") or os.environ.get("CONFLUENCE_SPACE_ID", ""),
            parent_id=overrides.get("parent_id")
            or os.environ.get("CONFLUENCE_PARENT_PAGE_ID", ""),
            session=overrides.get("session"),
            converter=overrides.get("converter"),
        )
    if provider == "notion":
        return NotionPublisher(
            token=overrides.get("token") or os.environ.get("NOTION_TOKEN", ""),
            base_url=overrides.get("base_url")
            or os.environ.get("NOTION_API_BASE", "https://api.notion.com/v1"),
            api_version=overrides.get("api_version")
            or os.environ.get("NOTION_API_VERSION", "2026-03-11"),
            session=overrides.get("session"),
        )
    custom_factory = _registered_publishers.get(provider)
    if custom_factory:
        return custom_factory(**overrides)
    publisher_entry_point = _publisher_entry_points().get(provider)
    if publisher_entry_point:
        return publisher_entry_point.load()(**overrides)
    raise ValueError(f"unknown publisher: {provider}")
