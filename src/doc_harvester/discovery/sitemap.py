"""Sitemap and robots.txt discovery adapter."""

from __future__ import annotations

import gzip
import io
import mimetypes
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit, urlunsplit

from doc_harvester.core import DiscoveryProvider, DiscoveryRequest, Fetcher, ResourceRef
from doc_harvester.fetchers import FetchError, HTTPFetcher


class SitemapDiscoveryProvider(DiscoveryProvider):
    """Discover same-origin pages from sitemap files and sitemap indexes."""

    name = "sitemap"

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        max_sitemaps: int = 20,
        max_xml_bytes: int = 10 * 1024 * 1024,
        include_robots: bool = True,
        same_origin_only: bool = True,
    ) -> None:
        if max_sitemaps < 1:
            raise ValueError("max_sitemaps must be at least 1")
        if max_xml_bytes < 1:
            raise ValueError("max_xml_bytes must be at least 1")
        self.fetcher = fetcher or HTTPFetcher(max_bytes=max_xml_bytes)
        self.max_sitemaps = max_sitemaps
        self.max_xml_bytes = max_xml_bytes
        self.include_robots = include_robots
        self.same_origin_only = same_origin_only

    def discover(self, request: DiscoveryRequest) -> list[ResourceRef]:
        root_uri = request.root_uri.strip()
        parsed_root = urlsplit(root_uri)
        if parsed_root.scheme.lower() not in {"http", "https"} or not parsed_root.netloc:
            raise ValueError("sitemap discovery requires an absolute HTTP(S) root_uri")
        if parsed_root.username or parsed_root.password:
            raise ValueError("sitemap root_uri must not contain embedded credentials")

        origin = urlunsplit((parsed_root.scheme, parsed_root.netloc, "", "", ""))
        candidates = self._initial_candidates(root_uri, origin)
        if self.include_robots:
            robots_uri = f"{origin}/robots.txt"
            robots = self._fetch_optional(robots_uri)
            if robots is not None:
                candidates.extend(self._robots_sitemaps(robots.content, robots_uri))

        queue = self._deduplicate(candidates)
        queued = set(queue)
        discovered: list[ResourceRef] = []
        seen_pages: set[str] = set()
        processed = 0

        while queue and processed < self.max_sitemaps and len(discovered) < request.limit:
            sitemap_uri = queue.pop(0)
            if self.same_origin_only and not self._same_origin(origin, sitemap_uri):
                continue
            processed += 1
            artifact = self._fetch_optional(sitemap_uri)
            if artifact is None:
                continue
            try:
                xml_text = self._decode_xml(artifact, sitemap_uri)
            except (FetchError, OSError, EOFError):
                continue
            page_uris, child_sitemaps = self._parse_xml(xml_text, sitemap_uri)

            for child in child_sitemaps:
                if self._is_safe_http_uri(child) and child not in queued:
                    queued.add(child)
                    queue.append(child)

            for uri in page_uris:
                if not self._is_safe_http_uri(uri):
                    continue
                if self.same_origin_only and not self._same_origin(origin, uri):
                    continue
                if uri in seen_pages:
                    continue
                seen_pages.add(uri)
                media_type = mimetypes.guess_type(urlsplit(uri).path)[0] or ""
                discovered.append(ResourceRef(uri, source=self.name, media_type=media_type))
                if len(discovered) >= request.limit:
                    break

        return discovered

    @staticmethod
    def _initial_candidates(root_uri: str, origin: str) -> list[str]:
        path = urlsplit(root_uri).path.lower()
        if path.endswith((".xml", ".xml.gz", ".gz")):
            return [root_uri]
        return [
            f"{origin}/sitemap.xml",
            f"{origin}/sitemap_index.xml",
            f"{origin}/sitemap.xml.gz",
        ]

    def _fetch_optional(self, uri: str):
        try:
            return self.fetcher.fetch(ResourceRef(uri, source=self.name))
        except FetchError:
            return None

    @staticmethod
    def _robots_sitemaps(content: bytes, robots_uri: str) -> list[str]:
        result: list[str] = []
        text = content.decode("utf-8-sig", errors="replace")
        for line in text.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().lower() == "sitemap" and value.strip():
                result.append(urljoin(robots_uri, value.strip()))
        return result

    def _decode_xml(self, artifact, uri: str) -> str:
        compressed = uri.lower().endswith(".gz") or artifact.media_type in {
            "application/gzip",
            "application/x-gzip",
        }
        if compressed:
            with gzip.GzipFile(fileobj=io.BytesIO(artifact.content)) as archive:
                content = archive.read(self.max_xml_bytes + 1)
        else:
            content = artifact.content
        if len(content) > self.max_xml_bytes:
            raise FetchError(f"sitemap exceeds {self.max_xml_bytes} decoded bytes")
        return content.decode("utf-8-sig", errors="replace")

    @staticmethod
    def _parse_xml(xml_text: str, sitemap_uri: str) -> tuple[list[str], list[str]]:
        lowered = xml_text.lower()
        if "<!doctype" in lowered or "<!entity" in lowered:
            return [], []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return [], []
        root_name = SitemapDiscoveryProvider._local_name(root.tag)
        locations: list[str] = []
        for element in root.iter():
            if SitemapDiscoveryProvider._local_name(element.tag) == "loc" and element.text:
                locations.append(urljoin(sitemap_uri, element.text.strip()))
        if root_name == "sitemapindex":
            return [], locations
        if root_name == "urlset":
            return locations, []
        return [], []

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    @staticmethod
    def _same_origin(origin: str, candidate: str) -> bool:
        expected = urlsplit(origin)
        actual = urlsplit(candidate)
        try:
            actual_port = actual.port or SitemapDiscoveryProvider._default_port(actual.scheme)
            expected_port = expected.port or SitemapDiscoveryProvider._default_port(expected.scheme)
        except ValueError:
            return False
        return (actual.scheme.lower(), actual.hostname or "", actual_port) == (
            expected.scheme.lower(),
            expected.hostname or "",
            expected_port,
        )

    @staticmethod
    def _is_safe_http_uri(candidate: str) -> bool:
        try:
            parsed = urlsplit(candidate)
            parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    @staticmethod
    def _default_port(scheme: str) -> int | None:
        return {"http": 80, "https": 443}.get(scheme.lower())

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))
