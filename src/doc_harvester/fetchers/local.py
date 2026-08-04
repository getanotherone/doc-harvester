"""Root-confined local-file fetcher adapter."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

from doc_harvester.core import FetchedArtifact, Fetcher, ResourceRef
from doc_harvester.fetchers.errors import FetchError, FetchTooLargeError, UnsupportedSchemeError
from doc_harvester.fetchers.http import DEFAULT_MAX_BYTES


class LocalFileFetcher(Fetcher):
    """Read plain paths or local file URIs below a configured root directory."""

    name = "local-file"

    def __init__(self, root: str | Path = ".", *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be at least 1")
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = max_bytes

    def fetch(self, resource: ResourceRef) -> FetchedArtifact:
        try:
            path = self._resolve(resource.uri)
            if not path.is_file():
                raise FetchError(f"local resource is not a file: {path.name or '<root>'}")
            size = path.stat().st_size
            if size > self.max_bytes:
                raise FetchTooLargeError(
                    f"local resource exceeds {self.max_bytes} bytes: {path.name}"
                )
            with path.open("rb") as source:
                content = source.read(self.max_bytes + 1)
            if len(content) > self.max_bytes:
                raise FetchTooLargeError(
                    f"local resource exceeds {self.max_bytes} bytes: {path.name}"
                )
        except FetchError:
            raise
        except (OSError, RuntimeError) as error:
            raise FetchError(f"local fetch failed: {type(error).__name__}") from None
        media_type = resource.media_type or mimetypes.guess_type(path.name)[0]
        return FetchedArtifact(
            resource=resource,
            content=content,
            media_type=media_type or "application/octet-stream",
            filename=path.name,
            metadata={"bytes": len(content)},
        )

    def _resolve(self, uri: str) -> Path:
        parsed = urlsplit(uri)
        if parsed.scheme and parsed.scheme.lower() != "file":
            raise UnsupportedSchemeError("LocalFileFetcher supports paths and file URIs")
        if parsed.scheme.lower() == "file":
            if parsed.netloc not in {"", "localhost"}:
                raise UnsupportedSchemeError("remote file URI authorities are not supported")
            if parsed.query or parsed.fragment:
                raise FetchError("file URIs must not contain query parameters or fragments")
            candidate = Path(unquote(parsed.path)).expanduser()
        else:
            candidate = Path(uri).expanduser()

        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise FetchError("local resource escapes the configured fetch root")
        return resolved
