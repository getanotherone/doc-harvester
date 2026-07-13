"""Storage provider factory backed by environment variables."""

from __future__ import annotations

import os

from doc_harvester.storage.base import StorageProvider
from doc_harvester.storage.local import LocalStorage
from doc_harvester.storage.s3 import S3Storage
from doc_harvester.storage.yandex import YandexDiskStorage


def create_storage(name: str | None = None, **overrides) -> StorageProvider:
    provider = (name or os.environ.get("DOC_HARVESTER_STORAGE", "local")).strip().lower()
    if provider == "local":
        root = overrides.get("root") or os.environ.get("DOC_HARVESTER_LOCAL_STORAGE_ROOT", "storage")
        return LocalStorage(root)
    if provider == "yandex":
        return YandexDiskStorage(overrides.get("token"))
    if provider == "s3":
        bucket = overrides.get("bucket") or os.environ.get("S3_BUCKET", "")
        return S3Storage(
            bucket,
            prefix=overrides.get("prefix") or os.environ.get("S3_PREFIX", ""),
            endpoint_url=overrides.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL"),
            region=overrides.get("region") or os.environ.get("S3_REGION"),
            access_key=overrides.get("access_key") or os.environ.get("AWS_ACCESS_KEY_ID"),
            secret_key=overrides.get("secret_key") or os.environ.get("AWS_SECRET_ACCESS_KEY"),
            client=overrides.get("client"),
        )
    raise ValueError(f"unknown storage provider: {provider}")
