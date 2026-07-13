"""MinIO client wrapper for document storage."""

from __future__ import annotations

import io
import logging

from minio import Minio

from doc_proc.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # Ensure bucket exists
        if not _client.bucket_exists(settings.minio_bucket):
            _client.make_bucket(settings.minio_bucket)
            logger.info("Created MinIO bucket: %s", settings.minio_bucket)
    return _client


def upload_file(
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload file to MinIO. Returns object path."""
    client = get_minio_client()
    client.put_object(
        settings.minio_bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def download_file(object_name: str) -> bytes:
    """Download file from MinIO."""
    client = get_minio_client()
    response = client.get_object(settings.minio_bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(object_name: str) -> None:
    """Delete file from MinIO."""
    client = get_minio_client()
    client.remove_object(settings.minio_bucket, object_name)


def get_file_size(object_name: str) -> int:
    """Get file size in bytes without downloading."""
    client = get_minio_client()
    stat = client.stat_object(settings.minio_bucket, object_name)
    return stat.size
