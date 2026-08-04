from __future__ import annotations

import pytest

from doc_harvester.core import ResourceRef
from doc_harvester.fetchers import (
    FetchError,
    FetchTooLargeError,
    HTTPFetcher,
    LocalFileFetcher,
    UnsupportedSchemeError,
    available_fetchers,
    create_fetcher,
)


class FakeResponse:
    def __init__(self, *, chunks=(), status_code=200, headers=None):
        self.chunks = tuple(chunks)
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.closed = False

    def iter_content(self, *, chunk_size):
        assert chunk_size > 0
        yield from self.chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get(self, uri, **options):
        self.calls.append((uri, options))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_http_fetcher_streams_content_and_preserves_resource_metadata():
    response = FakeResponse(
        chunks=(b"alpha", b"", b"beta"),
        headers={"content-length": "9", "content-type": "text/plain; charset=utf-8"},
    )
    session = FakeSession(response)
    fetcher = HTTPFetcher(session=session, timeout_seconds=4, max_bytes=10, chunk_size=3)
    resource = ResourceRef("https://example.com/docs/guide.txt?download=1")

    artifact = fetcher.fetch(resource)

    assert artifact.resource is resource
    assert artifact.content == b"alphabeta"
    assert artifact.media_type == "text/plain"
    assert artifact.filename == "guide.txt"
    assert artifact.metadata == {"status_code": 200, "bytes": 9}
    assert session.calls[0][0] == resource.uri
    assert session.calls[0][1]["stream"] is True
    assert response.closed is True


@pytest.mark.parametrize(
    "uri",
    ["ftp://example.com/file", "https:///missing-host", "https://[invalid/file"],
)
def test_http_fetcher_rejects_unsupported_or_incomplete_urls(uri):
    with pytest.raises(UnsupportedSchemeError):
        HTTPFetcher(session=FakeSession(None)).fetch(ResourceRef(uri))


def test_http_fetcher_rejects_embedded_credentials():
    with pytest.raises(FetchError, match="embedded credentials"):
        HTTPFetcher(session=FakeSession(None)).fetch(
            ResourceRef("https://user:password@example.com/file")
        )


@pytest.mark.parametrize(
    ("response", "max_bytes"),
    [
        (FakeResponse(chunks=(b"small",), headers={"Content-Length": "100"}), 10),
        (FakeResponse(chunks=(b"123456", b"78901")), 10),
    ],
)
def test_http_fetcher_enforces_declared_and_streamed_size_limits(response, max_bytes):
    with pytest.raises(FetchTooLargeError):
        HTTPFetcher(session=FakeSession(response), max_bytes=max_bytes).fetch(
            ResourceRef("https://example.com/large.bin")
        )
    assert response.closed is True


def test_http_fetcher_sanitizes_network_failure_messages():
    fetcher = HTTPFetcher(session=FakeSession(RuntimeError("secret token=abc")))

    with pytest.raises(FetchError) as caught:
        fetcher.fetch(ResourceRef("https://example.com/file?token=secret#fragment"))

    message = str(caught.value)
    assert message == "HTTP fetch failed for https://example.com/file: RuntimeError"
    assert "secret" not in message


def test_local_fetcher_reads_relative_paths_and_file_uris(tmp_path):
    source = tmp_path / "docs" / "guide.txt"
    source.parent.mkdir()
    source.write_text("hello", encoding="utf-8")
    fetcher = LocalFileFetcher(tmp_path)

    relative = fetcher.fetch(ResourceRef("docs/guide.txt"))
    absolute = fetcher.fetch(ResourceRef(source.as_uri()))

    assert relative.content == absolute.content == b"hello"
    assert relative.media_type == "text/plain"
    assert relative.filename == "guide.txt"
    assert relative.metadata == {"bytes": 5}


def test_local_fetcher_confines_paths_to_configured_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")

    with pytest.raises(FetchError, match="escapes"):
        LocalFileFetcher(root).fetch(ResourceRef("../outside.txt"))


def test_local_fetcher_rejects_remote_authorities_and_large_files(tmp_path):
    with pytest.raises(UnsupportedSchemeError, match="remote"):
        LocalFileFetcher(tmp_path).fetch(ResourceRef("file://server/share/file.txt"))

    source = tmp_path / "large.bin"
    source.write_bytes(b"12345")
    with pytest.raises(FetchTooLargeError):
        LocalFileFetcher(tmp_path, max_bytes=4).fetch(ResourceRef(str(source)))


def test_fetcher_factory_lists_and_builds_builtin_adapters(tmp_path):
    assert available_fetchers() == ("http", "local-file")
    assert isinstance(create_fetcher("HTTP", session=FakeSession(None)), HTTPFetcher)
    assert isinstance(create_fetcher("file", root=tmp_path), LocalFileFetcher)
    with pytest.raises(ValueError, match="unknown fetcher"):
        create_fetcher("object-storage")
