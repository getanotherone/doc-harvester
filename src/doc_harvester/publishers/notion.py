"""Notion Markdown publisher adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from doc_harvester.publishers.base import Publisher, PublishRequest, PublishResult


@dataclass(frozen=True)
class NotionDestination:
    page_id: str = ""
    parent_id: str = ""


class NotionPublisher(Publisher):
    """Publish through Notion's native Markdown content API.

    Use ``page:<id>`` (or a bare page ID) to replace an existing page and
    ``parent:<id>`` to create a child page.
    """

    name = "notion"

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.notion.com/v1",
        api_version: str = "2026-03-11",
        session: Any | None = None,
    ) -> None:
        if not token:
            raise RuntimeError("NOTION_TOKEN is required for the Notion publisher")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": api_version,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    @staticmethod
    def parse_destination(destination: str) -> NotionDestination:
        value = destination.strip()
        if value.startswith("parent:"):
            return NotionDestination(parent_id=value.removeprefix("parent:").strip())
        if value.startswith("page:"):
            value = value.removeprefix("page:").strip()
        return NotionDestination(page_id=value)

    def _api(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        response = self.session.get(self._api(f"/pages/{page_id}"), timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def read_page_content(self, page_id: str) -> str | None:
        response = self.session.get(self._api(f"/pages/{page_id}/markdown"), timeout=120)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("markdown")

    def create_page(self, parent_id: str, title: str, content: str) -> dict[str, Any]:
        response = self.session.post(
            self._api("/pages"),
            json={
                "parent": {"page_id": parent_id},
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"type": "text", "text": {"content": title}}],
                    }
                },
                "markdown": content,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def update_page(self, page_id: str, title: str, content: str) -> dict[str, Any]:
        if title:
            title_response = self.session.patch(
                self._api(f"/pages/{page_id}"),
                json={
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [{"type": "text", "text": {"content": title}}],
                        }
                    }
                },
                timeout=60,
            )
            title_response.raise_for_status()
        response = self.session.patch(
            self._api(f"/pages/{page_id}/markdown"),
            json={
                "type": "replace_content",
                "replace_content": {"new_str": content},
            },
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
        destination = self.parse_destination(request.destination)
        if not destination.page_id and not destination.parent_id:
            raise ValueError("Notion destination cannot be empty")
        if destination.parent_id:
            status = "would_create" if create_missing else "missing"
            if dry_run or not create_missing:
                return PublishResult(self.name, request.destination, status)
            content = request.source.read_text(encoding="utf-8")
            created = self.create_page(
                destination.parent_id, request.title or request.source.stem, content
            )
            return PublishResult(
                self.name, request.destination, "created", str(created.get("id", ""))
            )

        page = self.get_page(destination.page_id)
        if dry_run:
            return PublishResult(
                self.name,
                request.destination,
                "would_update" if page else "missing",
                destination.page_id if page else "",
            )
        if not page:
            return PublishResult(self.name, request.destination, "missing")
        content = request.source.read_text(encoding="utf-8")
        self.update_page(destination.page_id, request.title, content)
        return PublishResult(self.name, request.destination, "updated", destination.page_id)
