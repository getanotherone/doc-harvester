# Architecture

## Scope

The repository currently contains two related runtimes:

1. The standalone scraper downloads or extracts content, writes unit JSON, creates chunks,
   evaluates quality, and optionally uploads artifacts.
2. DocProc is an optional service for richer parsing, strategy selection, embeddings,
   queues, object storage, and database-backed retrieval.

They share concepts but remain independently deployable. The standalone runtime must work
without PostgreSQL, Redis, MinIO, an embedding provider, or Yandex credentials.

## Standalone flow

```text
profile/search
      |
      v
URL discovery -> bounded crawl -> fetch
                                |-- file -> page/unit extraction
                                `-- HTML -> content blocks
                                               |
                                               v
                                     token-aware chunking
                                               |
                                  metadata + quality gate
                                               |
                              local artifacts / optional upload
```

Runtime state is written under `data/`, generated datasets under `datasets/`, manifests
under `runs/`, and discovery output under `discovery/`. These directories are intentionally
excluded from Git.

## Package boundaries

- `doc_harvester.cli` is the stable public command entrypoint.
- Flat modules under `src/` are the existing implementation and compatibility surface.
- `api/` exposes asynchronous task endpoints around standalone operations.
- `services/doc_proc/` owns its database, queue, storage, embedding, and parsing concerns.
- `scripts/` contains advanced operations that are not yet part of the stable CLI.

## Provider boundaries

The standalone runtime selects storage through `doc_harvester.storage.StorageProvider`.
Local filesystem storage is the credential-free default; Yandex Disk and S3-compatible
stores are optional adapters. Publishing uses the independent
`doc_harvester.publishers.Publisher` contract with local Markdown, Yandex Wiki,
Confluence Cloud, Notion, and plugin-provided implementations.

Discovery profiles are validated by `doc_harvester.profiles.DiscoveryProfile` before use.
The current scoring implementation is still heuristic, but terminology now comes from
validated profile files rather than an implicit electrical fallback.

The legacy optimized Yandex batch uploader remains in `scraper.py` as a compatibility
surface. New integrations should use the public provider contracts.

## Reliability controls

- Streaming downloads avoid loading large responses into memory.
- PDF extraction works page by page with resumable unit files.
- Crawl delay, page limits, URL scoring, and consecutive-error thresholds bound traversal.
- Chunking preserves table rows and normative blocks where possible.
- Quality reports identify empty, tiny, duplicate, noisy, and oversized chunks.
- Credentials are loaded only from environment variables.
