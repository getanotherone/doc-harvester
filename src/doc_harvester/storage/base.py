"""Backward-compatible storage provider contract."""

from doc_harvester.core import StorageBackend, StorageResult


class StorageProvider(StorageBackend):
    """Compatibility name for the universal :class:`StorageBackend` contract."""
