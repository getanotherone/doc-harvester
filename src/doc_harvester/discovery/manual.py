"""Manual resource discovery adapter."""

from __future__ import annotations

from urllib.parse import urldefrag, urlsplit

from doc_harvester.core import DiscoveryProvider, DiscoveryRequest, ResourceRef
from doc_harvester.media import guess_media_type


class ManualDiscoveryProvider(DiscoveryProvider):
    """Convert an explicit URI list into deduplicated resource references."""

    name = "manual"
    _ALLOWED_SCHEMES = {"", "file", "http", "https"}

    def discover(self, request: DiscoveryRequest) -> list[ResourceRef]:
        if not request.manual_uris:
            raise ValueError("manual discovery requires manual_uris")

        resources: list[ResourceRef] = []
        seen: set[str] = set()
        for raw_uri in request.manual_uris:
            uri = urldefrag(str(raw_uri).strip()).url
            if not uri:
                raise ValueError("manual resource uri cannot be empty")
            parsed = urlsplit(uri)
            if parsed.scheme.lower() not in self._ALLOWED_SCHEMES:
                raise ValueError(f"unsupported manual resource scheme: {parsed.scheme}")
            if parsed.username or parsed.password:
                raise ValueError("manual resource URLs must not contain embedded credentials")
            if uri in seen:
                continue
            seen.add(uri)
            media_type = guess_media_type(parsed.path)
            resources.append(ResourceRef(uri, source=self.name, media_type=media_type))
            if len(resources) >= request.limit:
                break
        return resources
