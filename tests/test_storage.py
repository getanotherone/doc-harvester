from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from doc_harvester.storage import LocalStorage, S3Storage, create_storage


def test_local_storage_upload_tree_and_path_safety(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("alpha", encoding="utf-8")
    (source / ".secret").write_text("ignore", encoding="utf-8")
    (source / "nested").mkdir()
    (source / "nested" / "b.txt").write_text("beta", encoding="utf-8")
    storage = LocalStorage(tmp_path / "store")

    result = storage.upload_tree(source, "dataset")

    assert result.files_uploaded == 2
    assert result.bytes_uploaded == 9
    assert (tmp_path / "store/dataset/a.txt").read_text() == "alpha"
    assert not (tmp_path / "store/dataset/.secret").exists()
    with pytest.raises(ValueError, match="escapes"):
        storage.put_bytes(b"bad", "../outside")


def test_local_storage_respects_no_overwrite(tmp_path):
    storage = LocalStorage(tmp_path / "store")
    storage.put_bytes(b"first", "value.bin")
    with pytest.raises(FileExistsError):
        storage.put_bytes(b"second", "value.bin", overwrite=False)


def test_upload_tree_preflights_all_conflicts_before_writing(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("new-a", encoding="utf-8")
    (source / "z.txt").write_text("new-z", encoding="utf-8")
    storage = LocalStorage(tmp_path / "store")
    storage.put_bytes(b"keep-z", "dataset/z.txt")

    with pytest.raises(FileExistsError, match="already contains"):
        storage.upload_tree(source, "dataset", overwrite=False)

    assert not (tmp_path / "store/dataset/a.txt").exists()
    assert (tmp_path / "store/dataset/z.txt").read_bytes() == b"keep-z"


def test_upload_tree_rejects_symbolic_links(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    (source / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="symbolic link"):
        LocalStorage(tmp_path / "store").upload_tree(source, "dataset")


def test_upload_tree_rejects_symbolic_link_root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "source-alias"
    alias.symlink_to(source, target_is_directory=True)

    with pytest.raises(ValueError, match="source directory is a symbolic link"):
        LocalStorage(tmp_path / "store").upload_tree(alias, "dataset")


@pytest.mark.parametrize("layout", ["target-inside-source", "source-inside-target"])
def test_local_storage_rejects_overlapping_source_and_target_trees(tmp_path, layout):
    if layout == "target-inside-source":
        source = tmp_path / "dataset"
        source.mkdir()
        storage = LocalStorage(source)
        destination = "stored-copy"
    else:
        storage = LocalStorage(tmp_path / "storage")
        source = tmp_path / "storage/source"
        source.mkdir()
        destination = ""
    (source / "value.txt").write_text("value", encoding="utf-8")

    with pytest.raises(ValueError, match="trees overlap"):
        storage.upload_tree(source, destination)


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def upload_file(self, source, bucket, key):
        self.objects[(bucket, key)] = Path(source).read_bytes()

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            error = RuntimeError("not found")
            error.response = {"Error": {"Code": "404"}}
            raise error
        return {}


def test_s3_compatible_storage_uses_bucket_and_prefix(tmp_path):
    client = FakeS3Client()
    storage = S3Storage("docs", prefix="rag", client=client)
    source = tmp_path / "chunk.json"
    source.write_bytes(b"{}")

    storage.put_file(source, "items/chunk.json")

    assert storage.exists("items/chunk.json")
    assert client.objects[("docs", "rag/items/chunk.json")] == b"{}"


def test_s3_storage_passes_temporary_session_credentials(monkeypatch):
    captured = {}
    fake_client = FakeS3Client()

    def build_client(service, **options):
        captured.update({"service": service, **options})
        return fake_client

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=build_client))

    storage = S3Storage(
        "docs",
        endpoint_url="https://objects.example.test",
        region="test-1",
        access_key="temporary-access",
        secret_key="temporary-secret",
        session_token="temporary-session",
    )

    assert storage.client is fake_client
    assert captured == {
        "service": "s3",
        "endpoint_url": "https://objects.example.test",
        "region_name": "test-1",
        "aws_access_key_id": "temporary-access",
        "aws_secret_access_key": "temporary-secret",
        "aws_session_token": "temporary-session",
    }


def test_storage_factory_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.delenv("DOC_HARVESTER_STORAGE", raising=False)
    storage = create_storage(root=tmp_path)
    assert isinstance(storage, LocalStorage)


def test_storage_factory_prefers_universal_s3_environment(monkeypatch):
    client = FakeS3Client()
    monkeypatch.setenv("DOC_HARVESTER_S3_BUCKET", "universal-bucket")
    monkeypatch.setenv("DOC_HARVESTER_S3_PREFIX", "review")
    monkeypatch.setenv("S3_BUCKET", "legacy-bucket")

    storage = create_storage("s3", client=client)

    assert storage.bucket == "universal-bucket"
    assert storage.prefix == "review"


def test_yandex_storage_requires_credentials(monkeypatch):
    monkeypatch.delenv("YANDEX_DISK_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="YANDEX_DISK_TOKEN"):
        create_storage("yandex")
