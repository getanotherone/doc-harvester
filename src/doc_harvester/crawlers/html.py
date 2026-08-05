"""Bounded, robots-aware HTML crawler."""

from __future__ import annotations

import fnmatch
import time
import urllib.robotparser
from html.parser import HTMLParser
from typing import Any, Callable, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

from doc_harvester.core import Crawler, CrawlPolicy, Fetcher, ResourceRef
from doc_harvester.fetchers import FetchError, HTTPFetcher, RedirectBlockedError
from doc_harvester.media import guess_media_type


DEFAULT_MAX_HTML_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ROBOTS_BYTES = 512 * 1024
DEFAULT_MAX_LINKS_PER_PAGE = 1000
DEFAULT_USER_AGENT = "doc-harvester"
_HTML_MEDIA_TYPES = {"text/html", "application/xhtml+xml"}
_SUPPORTED_LINK_MEDIA_TYPES = {
    "application/pdf",
    "application/xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/xml",
}


class _LinkParser(HTMLParser):
    def __init__(self, max_links: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_links = max_links
        self.links: list[str] = []
        self.truncated = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                if len(self.links) >= self.max_links:
                    self.truncated = True
                    return
                self.links.append(value)
                return


class HTMLCrawler(Crawler):
    """Breadth-first HTTP(S) traversal with conservative default boundaries."""

    name = "html"

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        robots_fetcher: Fetcher | None = None,
        max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
        max_robots_bytes: int = DEFAULT_MAX_ROBOTS_BYTES,
        max_links_per_page: int = DEFAULT_MAX_LINKS_PER_PAGE,
        user_agent: str = DEFAULT_USER_AGENT,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_html_bytes < 1:
            raise ValueError("max_html_bytes must be at least 1")
        if max_robots_bytes < 1:
            raise ValueError("max_robots_bytes must be at least 1")
        if max_links_per_page < 1:
            raise ValueError("max_links_per_page must be at least 1")
        if not user_agent.strip():
            raise ValueError("crawler user_agent cannot be empty")
        self.fetcher = fetcher or HTTPFetcher(max_bytes=max_html_bytes)
        self.robots_fetcher = robots_fetcher or (
            HTTPFetcher(max_bytes=max_robots_bytes) if fetcher is None else self.fetcher
        )
        self.max_html_bytes = max_html_bytes
        self.max_robots_bytes = max_robots_bytes
        self.max_links_per_page = max_links_per_page
        self.user_agent = user_agent.strip()
        self.sleeper = sleeper
        self.last_report: dict[str, Any] = {}

    def crawl(
        self,
        seeds: Sequence[ResourceRef],
        policy: CrawlPolicy,
    ) -> list[ResourceRef]:
        normalized_seeds = self._normalize_seeds(seeds)
        allowed_origins = {self._origin(uri) for uri in normalized_seeds}
        allowed_domains = self._allowed_domains(policy.allowed_domains)
        for configured_fetcher in {id(self.fetcher): self.fetcher, id(self.robots_fetcher): self.robots_fetcher}.values():
            configure_redirects = getattr(configured_fetcher, "set_redirect_validator", None)
            if not callable(configure_redirects):
                continue
            configure_redirects(
                lambda target: (
                    (normalized := self._normalize_uri(target)) is not None
                    and self._allowed(normalized, allowed_origins, allowed_domains)
                )
            )
        queue = [(uri, 0) for uri in normalized_seeds]
        queued = set(normalized_seeds)
        results: list[ResourceRef] = []
        result_uris: set[str] = set()
        robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        robots_delays: dict[str, float] = {}
        requested_origins: set[str] = set()
        report: dict[str, Any] = {
            "schema_version": 1,
            "seed_count": len(normalized_seeds),
            "fetched_pages": 0,
            "discovered_count": 0,
            "skipped_robots": 0,
            "skipped_filtered": 0,
            "skipped_unsupported": 0,
            "failed_fetches": 0,
            "blocked_redirects": 0,
            "truncated": False,
        }
        limit_hit = False

        while (
            queue
            and len(results) < policy.max_pages
            and report["fetched_pages"] < policy.max_pages
        ):
            uri, depth = queue.pop(0)
            if depth > policy.max_depth:
                continue
            if not self._allowed(uri, allowed_origins, allowed_domains):
                report["skipped_filtered"] += 1
                continue
            if self._matches(uri, policy.exclude_patterns):
                report["skipped_filtered"] += 1
                continue
            if policy.respect_robots_txt:
                rules, robots_delay = self._robots(
                    uri, robots_cache, robots_delays, requested_origins
                )
                if rules is None or not rules.can_fetch(self.user_agent, uri):
                    report["skipped_robots"] += 1
                    continue
            else:
                robots_delay = 0.0

            origin = self._origin(uri)
            if origin in requested_origins:
                delay = max(policy.delay_seconds, robots_delay)
                if delay:
                    self.sleeper(delay)
            requested_origins.add(origin)
            try:
                artifact = self.fetcher.fetch(
                    ResourceRef(uri, source=self.name, media_type=guess_media_type(uri))
                )
            except RedirectBlockedError:
                report["blocked_redirects"] += 1
                continue
            except FetchError:
                report["failed_fetches"] += 1
                continue
            if len(artifact.content) > self.max_html_bytes:
                report["failed_fetches"] += 1
                continue
            report["fetched_pages"] += 1

            final_uri = self._normalize_uri(str(artifact.metadata.get("final_uri") or uri))
            if final_uri is None or not self._allowed(
                final_uri, allowed_origins, allowed_domains
            ):
                report["blocked_redirects"] += 1
                continue
            media_type = artifact.media_type.split(";", 1)[0].strip().lower()
            if self._included(final_uri, policy.include_patterns):
                self._append_result(
                    results,
                    result_uris,
                    final_uri,
                    media_type or guess_media_type(final_uri),
                    depth,
                )
                if len(results) >= policy.max_pages:
                    break
            if media_type not in _HTML_MEDIA_TYPES or depth >= policy.max_depth:
                continue

            links, links_truncated = self._links(artifact.content, final_uri)
            limit_hit = limit_hit or links_truncated
            for link in links:
                if link in queued or link in result_uris:
                    continue
                if not self._allowed(link, allowed_origins, allowed_domains):
                    report["skipped_filtered"] += 1
                    continue
                if self._matches(link, policy.exclude_patterns):
                    report["skipped_filtered"] += 1
                    continue
                linked_media_type = guess_media_type(urlsplit(link).path)
                if linked_media_type and linked_media_type not in _HTML_MEDIA_TYPES:
                    if linked_media_type not in _SUPPORTED_LINK_MEDIA_TYPES:
                        report["skipped_unsupported"] += 1
                        continue
                    if policy.respect_robots_txt:
                        rules, _ = self._robots(
                            link, robots_cache, robots_delays, requested_origins
                        )
                        if rules is None or not rules.can_fetch(self.user_agent, link):
                            report["skipped_robots"] += 1
                            continue
                    if self._included(link, policy.include_patterns):
                        self._append_result(
                            results,
                            result_uris,
                            link,
                            linked_media_type,
                            depth + 1,
                        )
                        if len(results) >= policy.max_pages:
                            limit_hit = True
                            break
                    continue
                queued.add(link)
                queue.append((link, depth + 1))

        report["discovered_count"] = len(results)
        report["truncated"] = limit_hit or bool(queue)
        self.last_report = report
        return results

    def _robots(
        self,
        uri: str,
        cache: dict[str, urllib.robotparser.RobotFileParser | None],
        delays: dict[str, float],
        requested_origins: set[str],
    ) -> tuple[urllib.robotparser.RobotFileParser | None, float]:
        origin = self._origin(uri)
        if origin in cache:
            return cache[origin], delays[origin]
        robots_uri = f"{origin}/robots.txt"
        parser = urllib.robotparser.RobotFileParser(robots_uri)
        try:
            artifact = self.robots_fetcher.fetch(
                ResourceRef(robots_uri, source=self.name)
            )
            requested_origins.add(origin)
            final_uri = self._normalize_uri(
                str(artifact.metadata.get("final_uri") or robots_uri)
            )
            if final_uri is None or self._origin(final_uri) != origin:
                cache[origin] = None
                delays[origin] = 0.0
                return None, 0.0
            if len(artifact.content) > self.max_robots_bytes:
                cache[origin] = None
                delays[origin] = 0.0
                return None, 0.0
            parser.parse(artifact.content.decode("utf-8-sig", errors="replace").splitlines())
        except FetchError as error:
            if "HTTP 404" not in str(error) and "HTTP 410" not in str(error):
                cache[origin] = None
                delays[origin] = 0.0
                return None, 0.0
            parser.parse(["User-agent: *", "Disallow:"])
        delay = parser.crawl_delay(self.user_agent) or parser.crawl_delay("*") or 0.0
        cache[origin] = parser
        delays[origin] = float(delay)
        return parser, float(delay)

    def _links(self, content: bytes, base_uri: str) -> tuple[list[str], bool]:
        parser = _LinkParser(self.max_links_per_page)
        try:
            parser.feed(content.decode("utf-8", errors="replace"))
        except Exception:
            return [], False
        links: list[str] = []
        seen: set[str] = set()
        for raw_link in parser.links:
            normalized = self._normalize_uri(urljoin(base_uri, raw_link))
            if normalized is not None and normalized not in seen:
                seen.add(normalized)
                links.append(normalized)
        return links, parser.truncated

    @staticmethod
    def _normalize_seeds(seeds: Sequence[ResourceRef]) -> list[str]:
        normalized: list[str] = []
        for seed in seeds:
            uri = HTMLCrawler._normalize_uri(seed.uri)
            if uri is None:
                raise ValueError("crawler seeds must be absolute HTTP(S) URLs")
            if uri not in normalized:
                normalized.append(uri)
        if not normalized:
            raise ValueError("crawler requires at least one seed")
        return normalized

    @staticmethod
    def _normalize_uri(value: str) -> str | None:
        try:
            parsed = urlsplit(value.strip())
            port = parsed.port
        except (TypeError, ValueError):
            return None
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        if scheme not in {"http", "https"} or not hostname:
            return None
        if parsed.username or parsed.password:
            return None
        default_port = 80 if scheme == "http" else 443
        host = f"[{hostname}]" if ":" in hostname else hostname
        netloc = host if port in {None, default_port} else f"{host}:{port}"
        return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _origin(uri: str) -> str:
        parsed = urlsplit(uri)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @staticmethod
    def _allowed_domains(values: Sequence[str]) -> set[str]:
        domains: set[str] = set()
        for value in values:
            candidate = value.strip().lower().rstrip(".")
            if not candidate or "/" in candidate or ":" in candidate:
                raise ValueError("allowed domains must be hostnames without scheme or port")
            domains.add(candidate)
        return domains

    @staticmethod
    def _allowed(uri: str, origins: set[str], domains: set[str]) -> bool:
        parsed = urlsplit(uri)
        if domains:
            return (parsed.hostname or "").lower().rstrip(".") in domains
        return HTMLCrawler._origin(uri) in origins

    @staticmethod
    def _matches(uri: str, patterns: Sequence[str]) -> bool:
        return any(fnmatch.fnmatchcase(uri, pattern) for pattern in patterns)

    @staticmethod
    def _included(uri: str, patterns: Sequence[str]) -> bool:
        return not patterns or HTMLCrawler._matches(uri, patterns)

    @staticmethod
    def _append_result(
        results: list[ResourceRef],
        seen: set[str],
        uri: str,
        media_type: str,
        depth: int,
    ) -> None:
        if uri in seen:
            return
        seen.add(uri)
        results.append(
            ResourceRef(uri, source=HTMLCrawler.name, media_type=media_type, metadata={"depth": depth})
        )
