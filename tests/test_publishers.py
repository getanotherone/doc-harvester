import pytest

import doc_harvester.publishers.local as local_module

from doc_harvester.publishers import (
    ConfluencePublisher,
    LocalPublisher,
    NotionPublisher,
    PublishRequest,
    YandexWikiPublisher,
    available_publishers,
    create_publisher,
    register_publisher,
)


def test_local_publisher_dry_run_and_apply(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Documentation\n", encoding="utf-8")
    publisher = LocalPublisher(tmp_path / "published")
    request = PublishRequest(source, "guides/start")

    preview = publisher.publish(request)
    result = publisher.publish(request, dry_run=False)

    assert preview.status == "would_create"
    assert result.status == "published"
    assert (tmp_path / "published/guides/start.md").read_text() == "# Documentation\n"


def test_local_publisher_rejects_symlink_source_and_destination(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("content", encoding="utf-8")
    linked_source = tmp_path / "linked-source.md"
    linked_source.symlink_to(source)
    publisher = LocalPublisher(tmp_path / "published")

    with pytest.raises(FileNotFoundError):
        publisher.publish(PublishRequest(linked_source, "guides/start"))

    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "published").mkdir()
    (tmp_path / "published/linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        publisher.publish(PublishRequest(source, "linked/start"))


def test_local_publisher_atomic_failure_preserves_existing_destination(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.md"
    source.write_text("new", encoding="utf-8")
    destination = tmp_path / "published/guide.md"
    destination.parent.mkdir()
    destination.write_text("keep", encoding="utf-8")
    publisher = LocalPublisher(tmp_path / "published")

    def fail_copy(source_path, temporary_path):
        del source_path
        temporary_path.write_text("partial", encoding="utf-8")
        raise OSError("copy failed")

    monkeypatch.setattr(local_module.shutil, "copy2", fail_copy)
    with pytest.raises(OSError, match="copy failed"):
        publisher.publish(PublishRequest(source, "guide"), dry_run=False)

    assert destination.read_text(encoding="utf-8") == "keep"
    assert not list(destination.parent.glob(".guide.md.*.tmp"))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeYandexSession:
    def __init__(self):
        self.headers = {}
        self.posts = []

    def get(self, url, **kwargs):
        del url, kwargs
        return FakeResponse({"data": [{"id": 42}]})

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse({"id": 42})


def test_yandex_wiki_publisher_implements_generic_contract(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("content", encoding="utf-8")
    session = FakeYandexSession()
    publisher = YandexWikiPublisher("token", "org", session=session)
    request = PublishRequest(source, "docs/start", "Start")

    preview = publisher.publish(request)
    result = publisher.publish(request, dry_run=False)

    assert preview.status == "would_update"
    assert result.status == "updated"
    assert result.external_id == "42"
    assert session.posts


class FakeConfluenceSession:
    def __init__(self, pages=None):
        self.auth = None
        self.headers = {}
        self.pages = pages if pages is not None else []
        self.posts = []
        self.puts = []

    def get(self, url, **kwargs):
        if "/pages/" in url:
            page_id = url.rsplit("/", 1)[-1]
            page = next((page for page in self.pages if str(page["id"]) == page_id), None)
            return FakeResponse(page or {}, 200 if page else 404)
        return FakeResponse({"results": self.pages})

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse({"id": "created-page"})

    def put(self, url, **kwargs):
        self.puts.append((url, kwargs))
        return FakeResponse({"id": url.rsplit("/", 1)[-1]})


def test_confluence_updates_title_destination_with_versioned_storage_payload(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Guide", encoding="utf-8")
    session = FakeConfluenceSession(
        [{"id": "42", "title": "Guide", "parentId": "7", "version": {"number": 3}}]
    )
    publisher = ConfluencePublisher(
        "https://example.atlassian.net",
        "user@example.com",
        "token",
        "space",
        session=session,
        converter=lambda content: f"<h1>{content.removeprefix('# ')}</h1>",
    )

    preview = publisher.publish(PublishRequest(source, "title:Guide"))
    result = publisher.publish(PublishRequest(source, "title:Guide"), dry_run=False)

    assert preview.status == "would_update"
    assert result.status == "updated"
    assert session.auth == ("user@example.com", "token")
    payload = session.puts[0][1]["json"]
    assert payload["version"]["number"] == 4
    assert payload["body"] == {"representation": "storage", "value": "<h1>Guide</h1>"}


def test_confluence_creates_under_destination_parent(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("content", encoding="utf-8")
    session = FakeConfluenceSession()
    publisher = ConfluencePublisher(
        "https://example.atlassian.net/wiki/api/v2",
        "user@example.com",
        "token",
        "space",
        session=session,
        converter=lambda content: content,
    )

    result = publisher.publish(
        PublishRequest(source, "parent:7/New page"), dry_run=False, create_missing=True
    )

    assert result.status == "created"
    assert session.posts[0][1]["json"]["parentId"] == "7"


class FakeNotionSession:
    def __init__(self, existing=True):
        self.headers = {}
        self.existing = existing
        self.posts = []
        self.patches = []

    def get(self, url, **kwargs):
        del kwargs
        if url.endswith("/markdown"):
            return FakeResponse({"markdown": "existing"})
        return FakeResponse({"id": "page-id"}, 200 if self.existing else 404)

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse({"id": "new-page"})

    def patch(self, url, **kwargs):
        self.patches.append((url, kwargs))
        return FakeResponse({"id": "page-id"})


def test_notion_replaces_existing_page_with_native_markdown(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Native Markdown", encoding="utf-8")
    session = FakeNotionSession()
    publisher = NotionPublisher("token", session=session)

    result = publisher.publish(PublishRequest(source, "page:page-id"), dry_run=False)

    assert result.status == "updated"
    assert session.headers["Notion-Version"] == "2026-03-11"
    url, request = session.patches[-1]
    assert url.endswith("/pages/page-id/markdown")
    assert request["json"] == {
        "type": "replace_content",
        "replace_content": {"new_str": "# Native Markdown"},
    }


def test_notion_creates_child_page_from_parent_destination(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("content", encoding="utf-8")
    session = FakeNotionSession()
    publisher = NotionPublisher("token", session=session)

    preview = publisher.publish(PublishRequest(source, "parent:parent-id", "Guide"))
    result = publisher.publish(
        PublishRequest(source, "parent:parent-id", "Guide"),
        dry_run=False,
        create_missing=True,
    )

    assert preview.status == "missing"
    assert result.status == "created"
    assert session.posts[0][1]["json"]["markdown"] == "content"


def test_publisher_factory_supports_registration_and_lists_builtins(tmp_path):
    name = "test-doc-service"
    register_publisher(name, lambda **kwargs: LocalPublisher(kwargs["root"]))

    publisher = create_publisher(name, root=tmp_path)

    assert isinstance(publisher, LocalPublisher)
    assert {"local", "yandex-wiki", "confluence", "notion", name} <= set(
        available_publishers()
    )
    with pytest.raises(ValueError, match="already registered"):
        register_publisher(name, lambda **kwargs: LocalPublisher(kwargs["root"]))
    with pytest.raises(ValueError, match="built-in"):
        register_publisher("notion", lambda **kwargs: LocalPublisher(kwargs["root"]))
