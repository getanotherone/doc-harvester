"""S3 and S3-compatible object storage adapter."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from doc_harvester.storage.base import StorageProvider


class S3Storage(StorageProvider):
    name = "s3"

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            try:
                import boto3
            except ImportError as error:
                raise RuntimeError("Install S3 support with: pip install 'doc-harvester[s3]'") from error
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        self.client = client

    def _key(self, destination: str) -> str:
        parts = PurePosixPath(destination.strip("/")).parts
        if ".." in parts:
            raise ValueError(f"invalid S3 destination: {destination}")
        return "/".join(part for part in (self.prefix, *parts) if part)

    def exists(self, destination: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(destination))
            return True
        except Exception as error:
            response = getattr(error, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def put_bytes(self, data: bytes, destination: str, *, overwrite: bool = True) -> None:
        if not overwrite and self.exists(destination):
            raise FileExistsError(destination)
        self.client.put_object(Bucket=self.bucket, Key=self._key(destination), Body=data)

    def put_file(self, source: str | Path, destination: str, *, overwrite: bool = True) -> None:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        if not overwrite and self.exists(destination):
            raise FileExistsError(destination)
        self.client.upload_file(str(source_path), self.bucket, self._key(destination))
