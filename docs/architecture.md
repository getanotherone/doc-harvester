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
- `doc_harvester.core` owns provider-neutral contracts and shared data models for discovery,
  crawling, fetching, extraction, chunking, enrichment, quality, storage, and publishing.
- `doc_harvester.discovery` provides credential-free manual and sitemap implementations of
  the core discovery contract.
- `doc_harvester.fetchers` provides bounded HTTP and root-confined local-file
  implementations of the core fetch contract.
- `doc_harvester.extractors` provides neutral plain-text/Markdown, static HTML/XML,
  digital-text PDF, structure-aware DOCX, and bounded XLSX implementations of the core
  extraction contract.
- `doc_harvester.chunkers` provides the first structure-aware implementation of the core
  chunking contract.
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

The universal core intentionally contains no concrete provider imports. Existing storage
and publisher adapters implement its `StorageBackend` and `Publisher` contracts through
backward-compatible public aliases. Migration of the flat scraper and DocProc stages to
implement the remaining contracts directly is incremental follow-up work.

The credential-free discovery and fetch adapters are exposed through an additive `source`
CLI group. They do not replace the flat scraper's legacy crawl or search orchestration.
Sitemap discovery follows sitemap declarations and indexes; it is not an HTML crawler and
does not apply robots allow/disallow rules to later page requests.

`source process` is the first manifest-driven universal processing path. It stages a new
local dataset containing normalized blocks, chunks, and a per-resource report, then
publishes that directory atomically. It does not save originals. It supports embedded-text
PDFs without external OCR; textless PDFs are marked `ocr_required`. The legacy scraper and
DocProc retain their broader OCR/office capabilities. The universal DOCX adapter reads
bounded OOXML main-body content without extracting archives to disk or inventing pages.
The XLSX adapter streams visible worksheets, retains formulas without evaluation, and
requires explicit opt-in for hidden sheets.

After chunking, the pipeline applies the neutral `basic` metadata enricher and quality gate.
Enrichment adds source/language/structure/count/hash metadata without vendor or domain
classification. The gate records empty, tiny, duplicate, noisy, and oversized ratios in a
per-document `quality.json`. Findings remain visible in a successfully published dataset;
operators may opt into a non-zero exit status with `--fail-on-quality`.

`source inspect` reads the validated dataset as a separate, read-only review boundary. It
revalidates bounded document/chunk/quality structures and emits only operational inventory
fields. Content, raw failures, absolute source directories, and source URIs are excluded by
default. The resulting index is the explicit input to `source render`.

`source store` is the reviewed handoff from the atomic local dataset to a configured
`StorageBackend`. It validates the processing report and every processed resource's document,
chunk, and quality artifacts before writing. The default no-overwrite policy preflights all
target objects, and symbolic links are rejected. Generic remote backends cannot guarantee an
atomic multi-object commit, so failed remote uploads must be reviewed and cleaned by prefix.

`source render` is the separate publication handoff. It validates the same dataset, selects
one processed outcome by index, and atomically creates bounded Markdown outside the dataset.
Source URIs are private by default. An operator reviews this artifact before passing it to a
`Publisher`; CLI publication previews first, and replacing an existing destination requires
both apply and update authorization. No processing command automatically publishes content.

## Reliability controls

- Streaming downloads avoid loading large responses into memory.
- Universal digital-text PDF extraction preserves page identity and enforces a page limit.
- Legacy PDF/OCR extraction works page by page with resumable unit files.
- Crawl delay, page limits, URL scoring, and consecutive-error thresholds bound traversal.
- Chunking preserves table rows and normative blocks where possible.
- Quality reports identify empty, tiny, duplicate, noisy, and oversized chunks.
- Credentials are loaded only from environment variables.
