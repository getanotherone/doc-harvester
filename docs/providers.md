# Providers

Provider adapters keep extraction and chunking independent from infrastructure choices.
Credentials are read only when their provider is selected.

## Universal core

All pipeline extension points and portable data models are available from
`doc_harvester.core`:

```python
from doc_harvester.core import (
    Chunker,
    Crawler,
    DiscoveryProvider,
    Extractor,
    Fetcher,
    MetadataEnricher,
    Publisher,
    QualityGate,
    StorageBackend,
)
```

The core package has no provider SDK imports and performs no network or credential loading
at import time. Concrete implementations can target one stage without inheriting from a
Yandex-, cloud-, database-, or file-format-specific base class.

The initial interface release is synchronous. Existing standalone and DocProc
implementations will adopt the contracts incrementally; this phase does not replace their
working internal models or orchestration.

## Credential-free discovery and fetching

The first concrete discovery adapters accept manual resource locations or inspect sitemap
files. The first fetchers read bounded HTTP responses or root-confined local files. They
are available through both the Python API and the additive `source` CLI group.

```python
from doc_harvester.core import DiscoveryRequest
from doc_harvester.discovery import create_discovery_provider
from doc_harvester.fetchers import create_fetcher

discovery = create_discovery_provider("manual")
resources = discovery.discover(
    DiscoveryRequest(manual_uris=("docs/architecture.md",))
)

fetcher = create_fetcher("local-file", root=".")
artifact = fetcher.fetch(resources[0])
print(artifact.filename, len(artifact.content))
```

Built-in adapters:

| Stage | Name | Behavior |
|---|---|---|
| Discovery | `manual` | Ordered, deduplicated paths and `file`/`http`/`https` URIs |
| Discovery | `sitemap` | Conventional sitemaps, `robots.txt` declarations, indexes, and gzip |
| Fetch | `http` | Streaming HTTP(S) reads with timeout and byte limits |
| Fetch | `local-file` | Plain paths and local file URIs confined below a configured root |

Sitemap discovery is same-origin by default and bounds both sitemap count and decoded XML
size. The local fetcher resolves paths before enforcing its root boundary. HTTP failure
messages remove query strings and fragments; embedded URL credentials are rejected.

The adapters are available from the public CLI without changing the legacy discovery and
crawl commands:

```bash
doc-harvester source discover manual README.md docs/architecture.md
doc-harvester source discover sitemap https://example.com/sitemap.xml
doc-harvester source fetch README.md --root . --output /tmp/readme-copy.md
```

Discovery produces a manifest only; it never downloads every discovered page. Fetching
requires one selected resource and an explicit output file. See
[Configuration](configuration.md#credential-free-source-commands) for bounds, overwrite
behavior, and environment defaults.

## Credential-free extraction and chunking

Built-in processing adapters implement the universal core contracts:

| Stage | Name | Supported input / behavior |
|---|---|---|
| Extract | `text` | UTF-8-compatible plain text and Markdown paragraphs |
| Extract | `html-xml` | Neutral static HTML/XHTML/XML structural content |
| Extract | `pdf` | Embedded PDF text with page metadata; no OCR or source persistence |
| Extract | `docx` | OOXML headings, paragraphs, lists, and table rows; bounded expansion |
| Extract | `xlsx` | Sheet-scoped streamed rows and formulas; hidden sheets excluded by default |
| Chunk | `structure-aware` | Paragraph, section, table, and normative-aware token bounds |
| Enrich | `basic` | Neutral source type, language, structure, counts, and SHA-256 metadata |
| Quality | `basic` | Empty, tiny, duplicate, noisy, and oversized chunk ratios |

```python
from doc_harvester.chunkers import create_chunker
from doc_harvester.extractors import select_extractor
from doc_harvester.enrichers import create_enricher
from doc_harvester.quality import create_quality_gate
```

The `source process` command connects manifests, automatic HTTP/local fetching, extractor
selection, structure-aware chunking, neutral enrichment, and quality evaluation. It writes
normalized JSON locally and does not
persist original bytes, upload, publish, or silently treat unsupported binary formats as
text. Textless PDFs are reported as requiring OCR rather than invoking external binaries.
Quality findings are recorded for review by default. `--fail-on-quality` returns non-zero
after preserving the complete dataset when any processed document fails the configured gate.

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

For version-1 universal datasets, prefer the validated orchestration command:

```bash
doc-harvester source store /tmp/dataset --storage local \
  --local-root /tmp/storage --destination review/run-001
```

The destination is mandatory and provider-relative. Existing objects are protected by
default; `--overwrite` is explicit. S3-compatible endpoints use the same command after
installing the `s3` extra and configuring bucket, endpoint, region, and credentials.

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
