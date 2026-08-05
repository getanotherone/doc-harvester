"""Bounded HTTP(S) fetcher adapter."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urljoin, urlsplit

import requests

from doc_harvester.core import FetchedArtifact, Fetcher, ResourceRef
from doc_harvester.fetchers.errors import (
    FetchError,
    FetchTooLargeError,
    RedirectBlockedError,
    UnsupportedSchemeError,
)
from doc_harvester.media import guess_media_type
from doc_harvester.security import sanitize_url_for_logging


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 64 * 1024
DEFAULT_USER_AGENT = "doc-harvester/0.1 (+https://github.com/getanotherone/doc-harvester)"
DEFAULT_MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class HTTPFetcher(Fetcher):
    """Fetch HTTP resources without loading an unbounded response into memory."""

    name = "http"

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout_seconds: float = 30.0,
        max_bytes: int = DEFAULT_MAX_BYTES,
        headers: Mapping[str, str] | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        redirect_validator: Callable[[str], bool] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_bytes < 1:
            raise ValueError("max_bytes must be at least 1")
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        if max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.chunk_size = chunk_size
        self.headers = {"User-Agent": DEFAULT_USER_AGENT, **dict(headers or {})}
        self.max_redirects = max_redirects
        self.redirect_validator = redirect_validator

    def set_redirect_validator(
        self, validator: Callable[[str], bool] | None
    ) -> None:
        """Set a caller policy evaluated before every redirect request."""
        self.redirect_validator = validator

    def fetch(self, resource: ResourceRef) -> FetchedArtifact:
        try:
            parsed = urlsplit(resource.uri)
            hostname = parsed.hostname
        except ValueError:
            raise UnsupportedSchemeError(
                "HTTPFetcher requires a valid absolute HTTP(S) resource"
            ) from None
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            raise UnsupportedSchemeError("HTTPFetcher supports only http and https resources")
        if parsed.username or parsed.password:
            raise FetchError("HTTP resource URLs must not contain embedded credentials")

        safe_uri = sanitize_url_for_logging(resource.uri)
        response = None
        current_uri = resource.uri
        redirects = 0
        try:
            while True:
                response = self.session.get(
                    current_uri,
                    headers=self.headers,
                    timeout=self.timeout_seconds,
                    stream=True,
                    allow_redirects=False,
                )
                status_code = int(response.status_code)
                if status_code not in _REDIRECT_STATUSES:
                    break
                location = self._header(response.headers, "location").strip()
                if not location:
                    raise FetchError(f"HTTP redirect is missing Location: {safe_uri}")
                candidate = urljoin(current_uri, location)
                redirect = self._validated_http_uri(candidate, safe_uri)
                if self.redirect_validator is not None and not self.redirect_validator(
                    redirect
                ):
                    raise RedirectBlockedError(f"HTTP redirect blocked for {safe_uri}")
                redirects += 1
                if redirects > self.max_redirects:
                    raise FetchError(f"HTTP redirect limit exceeded for {safe_uri}")
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                response = None
                current_uri = redirect
            if status_code >= 400:
                raise FetchError(f"HTTP {status_code} while fetching {safe_uri}")

            declared_size = self._content_length(response.headers)
            if declared_size is not None and declared_size > self.max_bytes:
                raise FetchTooLargeError(
                    f"HTTP resource exceeds {self.max_bytes} bytes: {safe_uri}"
                )

            content = bytearray()
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > self.max_bytes:
                    raise FetchTooLargeError(
                        f"HTTP resource exceeds {self.max_bytes} bytes: {safe_uri}"
                    )

            final_uri = str(getattr(response, "url", "") or current_uri)
            media_type = self._media_type(response.headers, resource)
            filename = unquote(PurePosixPath(urlsplit(final_uri).path).name)
            metadata = {"status_code": status_code, "bytes": len(content)}
            if final_uri != resource.uri:
                metadata["final_uri"] = final_uri
            return FetchedArtifact(
                resource=resource,
                content=bytes(content),
                media_type=media_type,
                filename=filename,
                metadata=metadata,
            )
        except FetchError:
            raise
        except Exception as error:
            raise FetchError(
                f"HTTP fetch failed for {safe_uri}: {type(error).__name__}"
            ) from None
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _validated_http_uri(candidate: str, safe_original: str) -> str:
        try:
            parsed = urlsplit(candidate)
            parsed.port
        except ValueError:
            raise FetchError(f"HTTP redirect target is invalid for {safe_original}") from None
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise FetchError(f"HTTP redirect target is invalid for {safe_original}")
        if parsed.username or parsed.password:
            raise FetchError(f"HTTP redirect target has credentials for {safe_original}")
        return candidate

    @staticmethod
    def _content_length(headers: Mapping[str, str]) -> int | None:
        raw = HTTPFetcher._header(headers, "content-length").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

    @staticmethod
    def _media_type(headers: Mapping[str, str], resource: ResourceRef) -> str:
        content_type = (
            HTTPFetcher._header(headers, "content-type").split(";", 1)[0].strip().lower()
        )
        if content_type:
            return content_type
        if resource.media_type:
            return resource.media_type
        return guess_media_type(urlsplit(resource.uri).path) or "application/octet-stream"

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        for key, value in headers.items():
            if str(key).lower() == name:
                return str(value)
        return ""
