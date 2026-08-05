# doc-harvester

`doc-harvester` is an alpha-stage ingestion pipeline for turning technical documents and
web pages into structured, RAG-ready JSON chunks. It combines discovery, crawling,
memory-safe PDF extraction, HTML cleanup, token-aware chunking, metadata enrichment,
quality checks, and optional publishing to Yandex services.

The project was initially tuned for Russian electrical-engineering material. The core is
being generalized through profiles and provider interfaces; it is not yet a universal
scraper for every website or document type.

## Capabilities

- Crawl HTML catalogues and follow relevant child pages.
- Discover explicit paths/URLs or sitemap resources without provider credentials.
- Fetch bounded HTTP responses and root-confined local files through universal adapters.
- Find linked PDF, DOCX, XLSX, HTML, and XML resources.
- Extract large PDFs page by page with OCR fallback and resumable unit files.
- Remove navigation, commercial boilerplate, malformed OCR, and CID garbage.
- Preserve tables and normative clauses during token-aware chunking.
- Add retrieval metadata such as document, page, section, vendor, standard, year,
  language, source type, and quality status.
- Store output locally, on Yandex Disk, or in S3-compatible object storage.
- Publish generated documentation locally, to Yandex Wiki, Confluence Cloud, Notion, or
  installed third-party services through provider adapters.
- Run a FastAPI service and an optional, independently deployable DocProc service.

## Quick Start

Requirements: Python 3.11+. Tesseract and Poppler are optional legacy-workflow dependencies
and are not required for the demo or universal digital-text PDF processing.

```bash
git clone https://github.com/getanotherone/doc-harvester.git
cd doc-harvester

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'

doc-harvester demo
```

The demo uses embedded HTML, requires no credentials or network access, and writes
`demo-output/chunks.json`.

To verify the complete review-gated workflow—from a synthetic local website through local
storage and publication preview—follow the [credential-free golden path](docs/golden-path.md).

The default installation contains the universal CLI and does not install browser or OCR
runtime libraries. Add only the capability you need:

```bash
python -m pip install -e '.[browser]'  # legacy --spa crawling
python -m pip install -e '.[ocr]'      # legacy PDF OCR helpers
python -m pip install -e '.[legacy]'   # both optional legacy capabilities
```

Browser mode also requires a Playwright browser installation. OCR requires system
Tesseract and Poppler binaries; see [configuration](docs/configuration.md).

## CLI

```bash
# Create a credential-free manifest from explicit resources
doc-harvester source discover manual README.md docs/architecture.md

# Discover resources from a sitemap without a search-provider account
doc-harvester source discover sitemap https://example.com/sitemap.xml \
  --output discovery.json

# Crawl one documentation site conservatively into the same manifest format
doc-harvester source crawl https://docs.example.com/ \
  --limit 25 --max-depth 2 --delay 1 --output crawl.json

# Fetch one selected resource into an explicit file
doc-harvester source fetch README.md --root . --output /tmp/readme-copy.md

# Process a reviewed manifest, enrich it, and write quality reports
doc-harvester source process discovery.json --root . --output /tmp/dataset

# Use the same review output, but return non-zero when quality checks fail
doc-harvester source process discovery.json --root . --output /tmp/strict-dataset \
  --fail-on-quality

# Validate and store a reviewed dataset locally without overwriting existing files
doc-harvester source store /tmp/dataset --storage local \
  --local-root /tmp/doc-harvester-storage --destination manual-test/run-001

# List selectable documents and quality results without printing content or source URIs
doc-harvester source inspect /tmp/dataset

# Render one selected dataset document into Markdown for human review
doc-harvester source render /tmp/dataset --document-index 0 \
  --output /tmp/review.md

# Crawl locally without uploading
doc-harvester crawl https://example.com/catalog/ --no-upload

# Crawl and copy generated artifacts into local provider storage
doc-harvester crawl https://example.com/catalog/ --storage local

# Discover URLs through Yandex Search API
doc-harvester discover example.com --term "technical catalogue" --output discovery.json

# Process linked files and store results locally (the safe default)
doc-harvester files https://example.com/downloads/ --storage local

# Store an already processed dataset with any configured adapter
doc-harvester upload electrical/example.com --storage local
doc-harvester upload electrical/example.com --storage yandex
doc-harvester upload electrical/example.com --storage s3

# Validate or list discovery profiles
doc-harvester profile validate electrical
doc-harvester profile list

# Preview or apply publication of one Markdown artifact
doc-harvester publish /tmp/review.md docs/review
doc-harvester publish /tmp/review.md docs/review --apply
# Replacing an existing destination requires both permissions
doc-harvester publish /tmp/review.md docs/review --apply --update-existing

# Run the optional API
python -m pip install -e '.[api]'
SCRAPPER_API_KEY=change-me doc-harvester api
```

`.env.example` documents safe standalone defaults and optional integrations. If you copy it
to `.env`, review it first and export its values in your shell; the public CLI does not
automatically load `.env`. Never commit the resulting file. DocProc uses the separate
`services/doc_proc/.env.example` template.

## Output Model

Chunks use a retrieval-oriented JSON model:

```json
{
  "document": "catalog.pdf",
  "page": 12,
  "section": "Automatic circuit breakers",
  "chunk_index": 4,
  "text": "...",
  "doc_type": "catalog",
  "vendor": "",
  "standard_id": "",
  "year": null,
  "lang": "en",
  "source_type": "pdf",
  "quality_status": "passed"
}
```

Not every extractor can populate every field. Missing values remain empty or `null`.

## Architecture

```text
discovery -> crawler/fetcher -> extractor -> unit JSON
         -> chunker -> metadata/quality -> storage -> publisher
```

- `src/`: standalone crawler, extractors, chunker, quality checks, and providers.
- `src/doc_harvester/`: public package and CLI.
- `api/`: optional FastAPI wrapper for scraper operations.
- `services/doc_proc/`: separate document-processing service with richer parsing,
  chunking strategies, embeddings, PostgreSQL, Redis, and MinIO.
- `config/profiles/`: domain discovery profiles.
- `scripts/`: advanced operational and Wiki automation commands.

Yandex Disk and documentation services are optional adapters, not requirements for
extraction and chunking. Public storage and publisher contracts are available under
`doc_harvester.storage` and `doc_harvester.publishers`. S3 support is installed with
`pip install -e '.[s3]'`; documentation automation uses `pip install -e '.[wiki]'`.

Provider-neutral contracts for the complete pipeline are available under
`doc_harvester.core`: `DiscoveryProvider`, `Crawler`, `Fetcher`, `Extractor`, `Chunker`,
`MetadataEnricher`, `QualityGate`, `StorageBackend`, and `Publisher`. Concrete Yandex and
other vendor adapters are not imported by this core package.

Credential-free manual/sitemap discovery and HTTP/local-file fetchers are available under
`doc_harvester.discovery` and `doc_harvester.fetchers`. The additive `source` CLI exposes
them without changing the legacy crawl and provider-search orchestration.

The provider-neutral `doc_harvester.crawlers.HTMLCrawler` and `source crawl` command add
bounded robots-aware HTML traversal. Defaults are exact seed-origin, robots enforced,
one-second delay, depth three, and at most 100 fetched pages/resources. Review generated
URLs before sharing or processing them.

Provider-neutral basic enrichment and quality adapters are available under
`doc_harvester.enrichers` and `doc_harvester.quality`. `source process` writes a
`quality.json` beside each processed document. Quality findings are review-only by default;
`--fail-on-quality` changes the command exit status without deleting the review dataset.

`source inspect` provides the read-only review checkpoint after processing. It lists indexes,
formats, block/chunk counts, and safe quality codes without printing bodies, raw errors,
absolute source directories, or source URIs by default.

The provider-neutral `source store` command validates version-1 dataset structure before
using a `StorageBackend`. It requires an explicit destination, rejects symbolic links, and
preserves existing objects unless `--overwrite` is supplied. Start with local storage before
testing an optional S3-compatible service.

`source render` connects one selected processed document to the publication workflow without
automatically publishing it. Source URIs are excluded by default, output is bounded and
atomic, and the result must be reviewed before the dry-run-first `publish` command. Applying
an update to an existing destination additionally requires `--update-existing`.

## Development

```bash
python -m pip install -e '.[dev,api]'
ruff check .
pytest -q
PYTHONPATH=services/doc_proc/backend/src pytest -q services/doc_proc/tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[documentation index](docs/README.md).

## Security And Responsible Crawling

- Respect website terms, robots policies, copyright, and applicable laws.
- Use conservative crawl delays and bounded page limits.
- Do not publish downloaded documents unless their licenses permit redistribution.
- Keep credentials in environment variables or a secret manager.
- Review generated chunks before using them in production retrieval systems.

## Status

Version `0.2.0` is the CLI-first open-source MVP. It remains an alpha-stage `0.x` release:
APIs, configuration, and output schemas may change.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
