"""Public storage provider API."""

from doc_harvester.storage.base import StorageProvider, StorageResult
from doc_harvester.storage.factory import create_storage
from doc_harvester.storage.local import LocalStorage
from doc_harvester.storage.s3 import S3Storage
from doc_harvester.storage.yandex import YandexDiskStorage

__all__ = [
    "LocalStorage",
    "S3Storage",
    "StorageProvider",
    "StorageResult",
    "YandexDiskStorage",
    "create_storage",
]
