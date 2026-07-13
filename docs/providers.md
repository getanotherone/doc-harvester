# Providers

Provider adapters keep extraction and chunking independent from infrastructure choices.
Credentials are read only when their provider is selected.

## Storage

All storage adapters implement `StorageProvider`:

- `LocalStorage` copies artifacts below a configured filesystem root.
- `YandexDiskStorage` adapts the existing Yandex Disk API implementation.
- `S3Storage` supports AWS S3 and compatible services such as MinIO through an optional
  `boto3` installation.

The contract exposes `exists`, `put_bytes`, `put_file`, and `upload_tree`.

```python
from doc_harvester.storage import create_storage

storage = create_storage("local", root="storage")
result = storage.upload_tree("datasets/example", "examples/latest")
print(result.to_dict())
```

## Publishers

All documentation adapters implement `Publisher`. They accept a `PublishRequest`, return a
`PublishResult`, and use dry-run mode by default. Remote state changes require
`dry_run=False`; creation also requires `create_missing=True`.

```python
from pathlib import Path

from doc_harvester.publishers import PublishRequest, create_publisher

publisher = create_publisher("local", root="published")
preview = publisher.publish(PublishRequest(Path("README.md"), "docs/readme"))
```

Built-in publishers:

| Name | Destination | Behavior |
|---|---|---|
| `local` | Relative file path | Writes Markdown below the configured root |
| `yandex-wiki` | Wiki page slug | Updates by slug; optionally creates the slug |
| `confluence` | `page:<id>`, `title:<title>`, or `parent:<id>/<title>` | Uses Confluence Cloud v2 page APIs and storage-format HTML |
| `notion` | `page:<id>` or `parent:<id>` | Uses Notion's native Markdown create/replace endpoints |

A bare Confluence destination is treated as a title. A bare Notion destination is treated
as an existing page ID. `parent:` destinations are explicit creation targets and still
require `create_missing=True`.

Confluence Markdown conversion uses the optional `markdown` package:

```bash
python -m pip install -e '.[confluence]'
```

Notion full-page updates use `replace_content` without
`allow_deleting_content=true`. If a replacement would remove child pages or databases,
Notion rejects it instead of deleting them.

## Permissions

Publishers manage page content, not service permissions. They never make a page public or
change readers, groups, guests, or sharing links. A page created under a Confluence space
or Notion parent inherits that service's access model. Configure private access in the
target service before enabling apply mode.

## Third-party publishers

Applications can register a factory at runtime:

```python
from doc_harvester.publishers import register_publisher

register_publisher("outline", build_outline_publisher)
```

Installable packages can expose adapters without changing doc-harvester by declaring an
entry point:

```toml
[project.entry-points."doc_harvester.publishers"]
outline = "my_package.outline:build_publisher"
```

The entry point must resolve to a callable that accepts keyword overrides and returns a
`Publisher`. The CLI accepts installed publisher names without a hardcoded allowlist.

When adding a provider, keep credentials provider-specific, import optional vendor SDKs
lazily, preserve dry-run semantics, and add contract tests for lookup, create, update,
missing targets, and API errors.
