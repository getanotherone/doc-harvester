# Providers

## Storage

All storage adapters implement `StorageProvider`:

- `LocalStorage` copies artifacts below a configured filesystem root.
- `YandexDiskStorage` adapts the existing Yandex Disk API implementation.
- `S3Storage` supports AWS S3 and compatible services such as MinIO through an optional
  `boto3` installation.

The contract exposes `exists`, `put_bytes`, `put_file`, and `upload_tree`. Provider
factories read environment variables only when the corresponding provider is selected, so
local extraction never requires cloud credentials.

```python
from doc_harvester.storage import create_storage

storage = create_storage("local", root="storage")
result = storage.upload_tree("datasets/example", "examples/latest")
print(result.to_dict())
```

## Publishers

Publishers accept a `PublishRequest` and return a `PublishResult`. Publication is dry-run
by default. Callers must explicitly disable dry-run before external state changes.

```python
from pathlib import Path

from doc_harvester.publishers import PublishRequest, create_publisher

publisher = create_publisher("local", root="published")
preview = publisher.publish(PublishRequest(Path("README.md"), "docs/readme"))
```

The local adapter writes Markdown below its configured root. The Yandex Wiki adapter can
update existing pages and optionally create missing pages.

## Adding a provider

Implement the relevant abstract base class, expose the adapter through its factory, keep
credentials provider-specific, and add contract tests. Imports of optional vendor SDKs
must be lazy so local-only use remains dependency-light.
