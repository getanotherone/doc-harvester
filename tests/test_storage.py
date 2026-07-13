from pathlib import Path

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


def test_storage_factory_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.delenv("DOC_HARVESTER_STORAGE", raising=False)
    storage = create_storage(root=tmp_path)
    assert isinstance(storage, LocalStorage)


def test_yandex_storage_requires_credentials(monkeypatch):
    monkeypatch.delenv("YANDEX_DISK_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="YANDEX_DISK_TOKEN"):
        create_storage("yandex")
