"""Publisher factory backed by environment variables."""

from __future__ import annotations

import os

from doc_harvester.publishers.base import Publisher
from doc_harvester.publishers.local import LocalPublisher
from doc_harvester.publishers.yandex_wiki import YandexWikiPublisher


def create_publisher(name: str | None = None, **overrides) -> Publisher:
    provider = (name or os.environ.get("DOC_HARVESTER_PUBLISHER", "local")).strip().lower()
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
    raise ValueError(f"unknown publisher: {provider}")
