from doc_harvester.publishers import LocalPublisher, PublishRequest, YandexWikiPublisher


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


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
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
    session = FakeSession()
    publisher = YandexWikiPublisher("token", "org", session=session)
    request = PublishRequest(source, "docs/start", "Start")

    preview = publisher.publish(request)
    result = publisher.publish(request, dry_run=False)

    assert preview.status == "would_update"
    assert result.status == "updated"
    assert result.external_id == "42"
    assert session.posts
