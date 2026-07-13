"""Yandex Wiki publisher adapter."""

from __future__ import annotations

from typing import Any, Optional

import requests

from doc_harvester.publishers.base import Publisher, PublishRequest, PublishResult


class YandexWikiPublisher(Publisher):
    name = "yandex-wiki"

    def __init__(
        self,
        token: str,
        cloud_org_id: str,
        base_url: str = "https://api.wiki.yandex.net",
        *,
        session: Any | None = None,
    ) -> None:
        if not token:
            raise RuntimeError("YANDEX_WIKI_TOKEN is required for the Yandex Wiki publisher")
        if not cloud_org_id:
            raise RuntimeError("YANDEX_WIKI_CLOUD_ORG_ID is required for the Yandex Wiki publisher")
        self.cloud_org_id = cloud_org_id
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"OAuth {token}",
                "X-Org-Id": cloud_org_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _api(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_page_by_slug(self, slug: str) -> Optional[dict[str, Any]]:
        response = self.session.get(self._api("/v1/pages"), params={"slug": slug}, timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("id"):
            return payload
        data = payload.get("data") or []
        return data[0] if data else None

    def read_page_content(self, page_id: int) -> Optional[str]:
        response = self.session.get(
            self._api(f"/v1/pages/{page_id}"), params={"fields": "content"}, timeout=60
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("content")

    def create_page(self, slug: str, title: str, content: str) -> dict[str, Any]:
        response = self.session.post(
            self._api("/v1/pages"),
            json={"slug": slug, "title": title, "content": content, "page_type": "wysiwyg"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def update_page(self, page_id: str, title: str, content: str) -> dict[str, Any]:
        response = self.session.post(
            self._api(f"/v1/pages/{page_id}"),
            json={"title": title, "content": content},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def publish(
        self,
        request: PublishRequest,
        *,
        dry_run: bool = True,
        create_missing: bool = False,
    ) -> PublishResult:
        if not request.source.is_file():
            raise FileNotFoundError(request.source)
        content = request.source.read_text(encoding="utf-8")
        page = self.get_page_by_slug(request.destination)
        page_id = str(page["id"]) if page else ""
        if dry_run:
            status = "would_update" if page_id else "would_create" if create_missing else "missing"
            return PublishResult(self.name, request.destination, status, page_id)
        if page_id:
            self.update_page(page_id, request.title or request.source.stem, content)
            return PublishResult(self.name, request.destination, "updated", page_id)
        if not create_missing:
            return PublishResult(self.name, request.destination, "missing")
        created = self.create_page(request.destination, request.title or request.source.stem, content)
        return PublishResult(self.name, request.destination, "created", str(created.get("id", "")))
