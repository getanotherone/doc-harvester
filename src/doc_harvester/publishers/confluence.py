"""Confluence Cloud publisher adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from doc_harvester.publishers.base import Publisher, PublishRequest, PublishResult


@dataclass(frozen=True)
class ConfluenceDestination:
    page_id: str = ""
    title: str = ""
    parent_id: str = ""


class ConfluencePublisher(Publisher):
    """Publish Markdown files to Confluence Cloud pages.

    Destinations support ``page:<id>``, ``title:<title>``, and
    ``parent:<parent-id>/<title>``. A bare destination is treated as a title.
    """

    name = "confluence"

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        space_id: str,
        *,
        parent_id: str = "",
        session: Any | None = None,
        converter: Any | None = None,
    ) -> None:
        if not base_url:
            raise RuntimeError("CONFLUENCE_BASE_URL is required for the Confluence publisher")
        if not email:
            raise RuntimeError("CONFLUENCE_EMAIL is required for the Confluence publisher")
        if not api_token:
            raise RuntimeError("CONFLUENCE_API_TOKEN is required for the Confluence publisher")
        if not space_id:
            raise RuntimeError("CONFLUENCE_SPACE_ID is required for the Confluence publisher")
        normalized_url = base_url.rstrip("/")
        self.base_url = (
            normalized_url
            if normalized_url.endswith("/wiki/api/v2")
            else f"{normalized_url}/wiki/api/v2"
        )
        self.space_id = space_id
        self.parent_id = parent_id
        self.session = session or requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self.converter = converter or self._markdown_to_storage

    @staticmethod
    def _markdown_to_storage(content: str) -> str:
        try:
            import markdown
        except ImportError as exc:
            raise RuntimeError(
                "Confluence publishing requires the optional 'confluence' extra"
            ) from exc
        return markdown.markdown(content, extensions=["extra", "sane_lists"])

    @staticmethod
    def parse_destination(destination: str) -> ConfluenceDestination:
        value = destination.strip()
        if value.startswith("page:"):
            return ConfluenceDestination(page_id=value.removeprefix("page:").strip())
        if value.startswith("title:"):
            return ConfluenceDestination(title=value.removeprefix("title:").strip())
        if value.startswith("parent:"):
            parent_and_title = value.removeprefix("parent:").split("/", 1)
            if len(parent_and_title) != 2 or not all(part.strip() for part in parent_and_title):
                raise ValueError("Confluence parent destination must be parent:<id>/<title>")
            return ConfluenceDestination(
                parent_id=parent_and_title[0].strip(), title=parent_and_title[1].strip()
            )
        return ConfluenceDestination(title=value)

    def _api(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_page(self, destination: ConfluenceDestination) -> dict[str, Any] | None:
        if destination.page_id:
            response = self.session.get(
                self._api(f"/pages/{destination.page_id}"),
                params={"body-format": "storage"},
                timeout=60,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

        response = self.session.get(
            self._api("/pages"),
            params={
                "space-id": self.space_id,
                "title": destination.title,
                "status": "current",
                "limit": 25,
            },
            timeout=60,
        )
        response.raise_for_status()
        pages = response.json().get("results", [])
        if destination.parent_id:
            pages = [page for page in pages if str(page.get("parentId", "")) == destination.parent_id]
        return pages[0] if pages else None

    def read_page_content(self, page_id: str) -> str | None:
        response = self.session.get(
            self._api(f"/pages/{page_id}"),
            params={"body-format": "storage"},
            timeout=60,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return ((response.json().get("body") or {}).get("storage") or {}).get("value")

    def create_page(self, title: str, content: str, parent_id: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {
            "spaceId": self.space_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": self.converter(content)},
        }
        effective_parent = parent_id or self.parent_id
        if effective_parent:
            payload["parentId"] = effective_parent
        response = self.session.post(self._api("/pages"), json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    def update_page(self, page: dict[str, Any], title: str, content: str) -> dict[str, Any]:
        page_id = str(page["id"])
        version = int((page.get("version") or {}).get("number", 0)) + 1
        response = self.session.put(
            self._api(f"/pages/{page_id}"),
            json={
                "id": page_id,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": self.converter(content)},
                "version": {"number": version, "message": "Updated by doc-harvester"},
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
        if not destination.page_id and not destination.title:
            raise ValueError("Confluence destination cannot be empty")
        page = self.get_page(destination)
        page_id = str(page["id"]) if page else ""
        if dry_run:
            status = "would_update" if page_id else "would_create" if create_missing else "missing"
            return PublishResult(self.name, request.destination, status, page_id)
        content = request.source.read_text(encoding="utf-8")
        title = request.title or destination.title or request.source.stem
        if page:
            updated = self.update_page(page, title, content)
            return PublishResult(
                self.name, request.destination, "updated", str(updated.get("id", page_id))
            )
        if not create_missing:
            return PublishResult(self.name, request.destination, "missing")
        if destination.page_id:
            return PublishResult(self.name, request.destination, "missing")
        created = self.create_page(title, content, destination.parent_id)
        return PublishResult(self.name, request.destination, "created", str(created.get("id", "")))
